"""
session_store.py — Cross-instance persistent session store for Cloud Run.

Architecture:
  • Primary store  : Supabase `sessions` table  (shared across all instances)
  • Local cache    : in-process dict, TTL-bounded (write-through)
  • mask_bytes     : local-only (large binary, stored separately via _mask_cache)

Cache coherence:
  Each cached entry has a `_synced_at` monotonic timestamp. Reads find a fresh
  entry only if it's younger than TTL_SECONDS — otherwise they re-pull from
  Supabase. The high-frequency `/status` poll path passes force_refresh=True
  to bypass the local cache entirely, so worker-thread updates on instance A
  propagate to polls hitting instances B, C, … without waiting for the TTL.

If Supabase is unavailable the store falls back to the in-process dict silently,
which works fine for single-instance local development.
"""

import os
import time
import threading
from typing import Any

# ── Configuration ──────────────────────────────────────────────────────────────
TTL_SECONDS = float(os.environ.get("SESSION_CACHE_TTL", "2.0"))

# ── Local caches ───────────────────────────────────────────────────────────────
_local: dict[str, dict] = {}        # session data
_local_ts: dict[str, float] = {}    # last-synced (monotonic) per session
_mask_cache: dict[str, bytes] = {}  # mask_bytes — never sent to Supabase
_lock = threading.Lock()

# Columns that exist in the Supabase sessions table and can be persisted
_PERSISTABLE = {
    "status", "phase", "step",
    "image_url", "render_url",
    "analysis", "render_instruction",
    "error", "render_count", "image_local",
}


def _supabase():
    """Return a Supabase client, or None if credentials are missing."""
    try:
        from supabase import create_client
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_SERVICE_KEY", "")
        if url and key:
            return create_client(url, key)
    except Exception:
        pass
    return None


def _push(session_id: str, data: dict) -> None:
    """Push persistable fields to Supabase (best-effort, never raises)."""
    persistable = {k: v for k, v in data.items() if k in _PERSISTABLE}
    if not persistable:
        return
    try:
        client = _supabase()
        if client:
            client.table("sessions").upsert(
                {"id": session_id, **persistable},
                on_conflict="id",
            ).execute()
    except Exception as e:
        print(f"[session_store] Supabase push failed (non-fatal): {e}")


def _pull(session_id: str) -> dict | None:
    """Fetch a session from Supabase. Returns None if not found or on error."""
    try:
        client = _supabase()
        if client:
            resp = client.table("sessions").select("*").eq("id", session_id).limit(1).execute()
            rows = resp.data if resp else []
            if rows:
                return rows[0]
    except Exception as e:
        print(f"[session_store] Supabase pull failed (non-fatal): {e}")
    return None


def _merge_mask(session_id: str, data: dict) -> dict:
    """Inject mask_bytes from local-only cache into a returned session dict."""
    mask = _mask_cache.get(session_id)
    if mask:
        return {**data, "mask_bytes": mask}
    return dict(data)


def _is_fresh(session_id: str, now: float) -> bool:
    ts = _local_ts.get(session_id)
    return ts is not None and (now - ts) < TTL_SECONDS


# ── Public API ─────────────────────────────────────────────────────────────────

def set_session(session_id: str, data: dict) -> None:
    """Update session data (local + Supabase). Refreshes local sync timestamp."""
    now = time.monotonic()
    with _lock:
        if session_id not in _local:
            _local[session_id] = {}
        _local[session_id].update(data)
        _local_ts[session_id] = now

    # Mask bytes stay local
    if "mask_bytes" in data:
        _mask_cache[session_id] = data["mask_bytes"]

    _push(session_id, data)


def get_session(session_id: str, force_refresh: bool = False) -> dict | None:
    """
    Get session data.

    Behaviour:
      • force_refresh=True       → skip local cache, pull from Supabase.
      • Local cache <TTL old     → return cached.
      • Local cache stale/empty  → pull from Supabase, refresh cache + timestamp.
      • Supabase unavailable     → fall back to local cache if any (better than
                                   showing the user a "session not found" mid-flow).

    Always returns a fresh dict copy, never the cached object itself.
    """
    now = time.monotonic()

    if not force_refresh:
        with _lock:
            if session_id in _local and _is_fresh(session_id, now):
                return _merge_mask(session_id, _local[session_id])

    # Need to refresh from authoritative store
    remote = _pull(session_id)
    if remote is not None:
        with _lock:
            _local[session_id] = remote
            _local_ts[session_id] = now
        return _merge_mask(session_id, remote)

    # Supabase miss / failure — return whatever local has, else None
    with _lock:
        local = _local.get(session_id)
        if local is not None:
            print(f"[session_store] Supabase unreachable, serving stale local for {session_id}")
            return _merge_mask(session_id, local)
    return None


def init_session(session_id: str, data: dict) -> None:
    """Create a brand-new session (local + Supabase)."""
    set_session(session_id, data)