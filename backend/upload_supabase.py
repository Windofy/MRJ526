"""
upload_supabase.py — Supabase storage uploader for MRJ3.0
"""
import os
import uuid
from pathlib import Path
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

_client: Client | None = None


def _get_client() -> Client:
    global _client
    if _client is None:
        url = os.environ["SUPABASE_URL"] 
        key = os.environ["SUPABASE_SERVICE_KEY"]
        _client = create_client(url, key)
    return _client


def upload_image(local_path: str, session_id: str) -> dict:
    """
    Upload an image file to Supabase storage.

    Returns:
        dict with keys: storage_path, public_url
    """
    client = _get_client()
    bucket = "uploads"
    ext = Path(local_path).suffix.lower()
    storage_path = f"sessions/{session_id}/original{ext}"

    with open(local_path, "rb") as f:
        data = f.read()

    content_type_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                        ".png": "image/png", ".webp": "image/webp"}
    content_type = content_type_map.get(ext, "image/jpeg")

    client.storage.from_(bucket).upload(
        path=storage_path,
        file=data,
        file_options={"content-type": content_type, "upsert": "true"},
    )

    public_url = client.storage.from_(bucket).get_public_url(storage_path)
    return {"storage_path": storage_path, "public_url": public_url}


def upload_render(image_bytes: bytes, session_id: str, render_index: int = 0) -> dict:
    """
    Upload a rendered image (PNG bytes) to Supabase storage.

    Returns:
        dict with keys: storage_path, public_url
    """
    client = _get_client()
    bucket = "uploads"
    storage_path = f"sessions/{session_id}/render_{render_index}.png"

    client.storage.from_(bucket).upload(
        path=storage_path,
        file=image_bytes,
        file_options={"content-type": "image/png", "upsert": "true"},
    )

    public_url = client.storage.from_(bucket).get_public_url(storage_path)
    return {"storage_path": storage_path, "public_url": public_url}


def upsert_session(session_id: str, data: dict) -> None:
    """Insert or update a row in the sessions table."""
    client = _get_client()
    client.table("sessions").upsert({"id": session_id, **data}).execute()


def upsert_analysis(session_id: str, analysis_json: dict, render_instruction: dict) -> None:
    """Insert or update a row in the analyses table."""
    client = _get_client()
    client.table("analyses").upsert({
        "session_id": session_id,
        "analysis_json": analysis_json,
        "render_instruction": render_instruction,
    }).execute()


def insert_render(session_id: str, render_url: str, config_snapshot: dict, model_used: str) -> None:
    """Insert a row in the renders table."""
    client = _get_client()
    client.table("renders").insert({
        "session_id": session_id,
        "render_url": render_url,
        "config_snapshot": config_snapshot,
        "model_used": model_used,
    }).execute()
