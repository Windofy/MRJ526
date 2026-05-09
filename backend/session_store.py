"""
session_store.py — Cross-instance persistent session store for Cloud Run.

Architecture:
  • Primary store : Supabase `sessions` table  (shared across all instances)
  • Local cache   : in-process dict             (speed buffer, write-through)
  • mask_bytes    : local-only (large binary, stored separately via _mask_cache)

The Supabase sessions table is expected to have at minimum these columns:
    id              text  PRIMARY KEY
    status          text
    phase           int
    step            int
    image_url       text
    render_url      text
    analysis        jsonb
    render_instruction jsonb
    error           text
    render_count    int
    image_local     text   (local filesystem path on the current instance)

If Supabase is unavailable the store falls back to the in-process dict silently,
which works fine for single-instance local development.
"""

import json
import threading
import os
from typing import Any

# ── Local caches ────────────────────────────────────────────────────────────────
_local: dict[str, dict] = {}        # fast in-process cache
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


# ── Public API ──────────────────────────────────────────────────────────────────

def set_session(session_id: str, data: dict) -> None:
    """Update session data (local + Supabase)."""
    with _lock:
        if session_id not in _local:
            _local[session_id] = {}
        _local[session_id].update(data)

    # Store mask_bytes locally only
    if "mask_bytes" in data:
        _mask_cache[session_id] = data["mask_bytes"]

    _push(session_id, data)


def get_session(session_id: str) -> dict | None:
    """
    Get session data. Checks local cache first; falls back to Supabase.
    Rehydrates the local cache when a remote session is found.
    """
    with _lock:
        local = _local.get(session_id)

    if local is not None:
        # Inject mask_bytes from local cache if available
        mask = _mask_cache.get(session_id)
        if mask:
            return {**local, "mask_bytes": mask}
        return local

    # Cache miss — try Supabase (this instance may not have seen this session)
    remote = _pull(session_id)
    if remote:
        with _lock:
            _local[session_id] = remote
        mask = _mask_cache.get(session_id)
        if mask:
            return {**remote, "mask_bytes": mask}
        return remote

    return None


def init_session(session_id: str, data: dict) -> None:
    """Create a brand-new session (local + Supabase)."""
    set_session(session_id, data)
