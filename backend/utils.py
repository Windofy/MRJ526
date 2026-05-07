"""
src/AI/utils.py — Shared utilities for MRJ4.15

Handles:
- Supabase image upload
- Local image upload
- Base64 helpers
"""

import os
import base64
import uuid
from pathlib import Path
from typing import Optional

# ── PATHS ───────────────────────────────────────────────────────

ROOT       = Path(__file__).resolve().parents[1]
UPLOAD_DIR = ROOT / "data" / "uploads"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ── BASE64 HELPERS ──────────────────────────────────────────────

def strip_data_url(data_url: str) -> tuple[str, str]:
    """
    Strip the data URI header from a base64 string.
    Returns (mime_type, raw_base64).

    The declared MIME in the header is overridden by actual byte-sniffing
    to prevent Claude API 400 errors when browsers mislabel JPEGs as PNG.
    """
    import base64 as _b64

    if data_url.startswith("data:"):
        header, b64 = data_url.split(",", 1)
        declared_mime = header.split(";")[0].replace("data:", "")
    else:
        declared_mime = "image/jpeg"
        b64 = data_url

    # Sniff actual type from magic bytes — overrides whatever the header says.
    try:
        raw = _b64.b64decode(b64[:16])  # only need first bytes for magic numbers
        if raw[:8] == b'\x89PNG\r\n\x1a\n':
            mime = "image/png"
        elif raw[:3] == b'\xff\xd8\xff':
            mime = "image/jpeg"
        elif raw[:4] == b'RIFF' and raw[8:12] == b'WEBP':
            mime = "image/webp"
        elif raw[:6] in (b'GIF87a', b'GIF89a'):
            mime = "image/gif"
        else:
            mime = declared_mime  # fall back to declared if unknown
    except Exception:
        mime = declared_mime

    return mime, b64


def base64_to_bytes(b64: str) -> bytes:
    return base64.b64decode(b64)


def bytes_to_base64(data: bytes, mime: str = "image/jpeg") -> str:
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


# ── LOCAL UPLOAD ────────────────────────────────────────────────

def save_upload_locally(data_url: str, ext: str = "jpg") -> Path:
    """
    Save a base64 image to data/uploads/<uuid>.<ext>.
    Returns the file path.
    """
    mime, b64 = strip_data_url(data_url)
    ext_map = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
    ext = ext_map.get(mime, "jpg")
    filename = f"{uuid.uuid4()}.{ext}"
    path = UPLOAD_DIR / filename
    path.write_bytes(base64_to_bytes(b64))
    return path


# ── SUPABASE UPLOAD ─────────────────────────────────────────────

def upload_to_supabase(data_url: str) -> Optional[str]:
    """
    Upload an image to Supabase Storage.
    Returns the public URL on success, None if Supabase is not configured.
    Requires SUPABASE_URL and SUPABASE_KEY environment variables.
    """
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        # Supabase not configured — fall back to local save only
        return None

    try:
        from supabase import create_client  # type: ignore
        from core import SUPABASE_BUCKET

        client = create_client(supabase_url, supabase_key)
        mime, b64 = strip_data_url(data_url)
        ext_map   = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
        ext       = ext_map.get(mime, "jpg")
        filename  = f"{uuid.uuid4()}.{ext}"

        response = client.storage.from_(SUPABASE_BUCKET).upload(
            path=filename,
            file=base64_to_bytes(b64),
            file_options={"content-type": mime},
        )
        public_url = client.storage.from_(SUPABASE_BUCKET).get_public_url(filename)
        return public_url
    except Exception:
        return None


