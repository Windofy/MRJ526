"""
app.py — Flask API server for MRJ3.0
Routes: /upload, /status/<id>, /result/<id>, /preview, /health
"""
import os
import uuid
import threading
import json
import base64
import tempfile
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")
CORS(app)

# In-memory session store: session_id → state dict
_sessions: dict = {}
_lock = threading.Lock()

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def _get_session(session_id: str) -> dict | None:
    with _lock:
        return _sessions.get(session_id)


def _set_session(session_id: str, data: dict) -> None:
    with _lock:
        if session_id not in _sessions:
            _sessions[session_id] = {}
        _sessions[session_id].update(data)


# ── ROUTES ─────────────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/catalogus")
def catalogus():
    """Serve the full color catalog JSON from disk."""
    catalog_path = os.path.join(os.path.dirname(__file__), "data", "catalogus.json")
    try:
        with open(catalog_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data)
    except FileNotFoundError:
        return jsonify({"error": "Catalogus niet gevonden."}), 404


@app.route("/img-proxy")
def img_proxy():
    """
    Server-side proxy for Google Drive image URLs.
    Usage: /img-proxy?id=<gdrive_file_id>
    Fetches the image from GDrive server-side and streams it back,
    avoiding CORS/redirect blocking in the browser.
    """
    import httpx
    from flask import Response

    file_id = request.args.get("id", "").strip()
    if not file_id:
        return jsonify({"error": "Missing id parameter"}), 400

    gdrive_url = f"https://drive.google.com/uc?export=download&id={file_id}"

    try:
        with httpx.Client(follow_redirects=True, timeout=15) as client:
            upstream = client.get(
                gdrive_url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; MRJ-proxy/1.0)"},
            )
        content_type = upstream.headers.get("content-type", "image/jpeg")
        # GDrive sometimes returns a warning HTML page for large files
        if "text/html" in content_type:
            return jsonify({"error": "GDrive returned HTML — check file permissions or size"}), 502

        return Response(
            upstream.content,
            status=upstream.status_code,
            content_type=content_type,
            headers={
                "Cache-Control": "public, max-age=86400",
                "Access-Control-Allow-Origin": "*",
            },
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 502


@app.route("/")
def index():
    resp = send_from_directory(STATIC_DIR, "index.html")
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return resp


@app.after_request
def no_cache_static(response):
    """Disable caching for all static assets during development."""
    if request.path.startswith("/static") or request.path.endswith((".js", ".css", ".html")):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.route("/upload", methods=["POST"])
def upload():
    if "image" not in request.files:
        return jsonify({"error": "Geen afbeelding ontvangen."}), 400

    file = request.files["image"]
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": "Alleen PNG, JPG of WEBP bestanden zijn toegestaan."}), 400

    # Check size
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > MAX_FILE_SIZE:
        return jsonify({"error": "Bestand te groot. Maximaal 10MB toegestaan."}), 400

    session_id = str(uuid.uuid4())
    local_path = os.path.join(UPLOAD_DIR, f"{session_id}{ext}")
    file.save(local_path)

    # Initial session state
    _set_session(session_id, {
        "status": "uploading",
        "phase": 1,
        "step": 0,
        "image_local": local_path,
        "image_url": None,
        "render_url": None,
        "analysis": None,
        "render_instruction": None,
        "error": None,
    })

    # Launch analysis in background thread
    thread = threading.Thread(
        target=_run_analysis_thread,
        args=(session_id, local_path),
        daemon=True,
    )
    thread.start()

    return jsonify({"session_id": session_id})


@app.route("/status/<session_id>")
def status(session_id: str):
    state = _get_session(session_id)
    if state is None:
        return jsonify({"error": "Sessie niet gevonden."}), 404
    return jsonify({
        "status": state["status"],
        "phase": state["phase"],
        "step": state["step"],
        "error": state.get("error"),
    })


@app.route("/result/<session_id>")
def result(session_id: str):
    state = _get_session(session_id)
    if state is None:
        return jsonify({"error": "Sessie niet gevonden."}), 404
    if state["status"] not in ("done", "error"):
        return jsonify({"error": "Resultaat nog niet beschikbaar.", "status": state["status"]}), 202
    if state["status"] == "error":
        return jsonify({"error": state.get("error", "Onbekende fout.")}), 500
    return jsonify({
        "session_id": session_id,
        "image_url": state.get("image_url"),
        "render_url": state.get("render_url"),
        "analysis": state.get("analysis"),
        "render_instruction": state.get("render_instruction"),
    })


@app.route("/preview", methods=["POST"])
def preview():
    """Re-render with user config overrides."""
    body = request.get_json(silent=True) or {}
    session_id = body.get("session_id")
    config_override = body.get("config", {})

    if not session_id:
        return jsonify({"error": "session_id vereist."}), 400

    state = _get_session(session_id)
    if state is None:
        return jsonify({"error": "Sessie niet gevonden."}), 404

    render_instruction = state.get("render_instruction")
    if not render_instruction:
        # Analysis still in progress — tell the caller to retry later
        return jsonify({"error": "Analyse nog bezig. Probeer opnieuw als het resultaat klaar is.", "status": state.get("status")}), 503

    image_local = state.get("image_local")
    if not image_local or not os.path.exists(image_local):
        return jsonify({"error": "Originele afbeelding niet meer beschikbaar."}), 400

    # Run synchronously (previews are user-triggered, acceptable latency)
    try:
        from watermark import apply_watermark

        with open(image_local, "rb") as f:
            img_bytes = f.read()

        render_bytes, method = _render_with_fallback(
            img_bytes,
            render_instruction,
            state.get("mask_bytes"),
            config_override,
        )
        watermarked = apply_watermark(render_bytes)

        render_index = state.get("render_count", 0) + 1
        _set_session(session_id, {"render_count": render_index})

        try:
            from upload_supabase import upload_render as _up_render, insert_render as _ins_render
            upload_result = _up_render(watermarked, session_id, render_index)
            render_url = upload_result["public_url"]
            try:
                _ins_render(session_id, render_url, config_override, method)
            except Exception:
                pass
        except Exception as upload_err:
            print(f"[PREVIEW] Supabase upload failed ({upload_err}), using data URI fallback")
            b64 = base64.b64encode(watermarked).decode()
            render_url = f"data:image/png;base64,{b64}"

        _set_session(session_id, {"render_url": render_url})
        return jsonify({"render_url": render_url, "render_method": method})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── RENDER HELPER (SAM2 + inpainting → Gemini fallback) ───────────────────────

def _render_with_fallback(
    img_bytes: bytes,
    render_instruction: dict,
    mask_bytes: bytes | None = None,
    config_override: dict | None = None,
) -> tuple[bytes, str]:
    """
    Try SAM2 + FLUX inpainting first. Fall back to Gemini if:
    - FAL_KEY not set
    - No mask available
    - Inpainting fails
    """
    if mask_bytes and os.environ.get("FAL_KEY"):
        try:
            from inpaint import generate_inpaint
            render_bytes, model = generate_inpaint(
                img_bytes, mask_bytes, render_instruction, config_override
            )
            return render_bytes, f"flux:{model}"
        except Exception as e:
            print(f"[INPAINT] Failed, falling back to Gemini: {e}")

    # Gemini fallback
    from render_gemini import generate_render
    render_bytes = generate_render(img_bytes, render_instruction, config_override)
    return render_bytes, "gemini"


# ── BACKGROUND ANALYSIS THREAD ─────────────────────────────────────────────────

def _run_analysis_thread(session_id: str, local_path: str) -> None:
    try:
        # Phase 1: Upload to Supabase
        _set_session(session_id, {"status": "uploading", "phase": 1, "step": 0})
        try:
            from upload_supabase import upload_image, upsert_session, upsert_analysis
            upload_result = upload_image(local_path, session_id)
            image_url = upload_result["public_url"]
            _set_session(session_id, {"image_url": image_url})
            upsert_session(session_id, {
                "image_path": upload_result["storage_path"],
                "image_url": image_url,
                "status": "analysing",
                "phase": 2,
            })
        except Exception:
            image_url = None  # Supabase optional — continue anyway

        # Phases 2–9: Claude analysis
        _set_session(session_id, {"status": "analysing", "phase": 2, "step": 1})

        from analyse_claude import run_pipeline

        def _progress(phase: int, step: int):
            _set_session(session_id, {"phase": phase, "step": step})

        pipeline_result = run_pipeline(
            session_id=session_id,
            image_path=local_path,
            progress_callback=_progress,
        )

        analysis = pipeline_result["analysis"]
        render_instruction = pipeline_result["render_instruction"]
        _set_session(session_id, {
            "analysis": analysis,
            "render_instruction": render_instruction,
            "phase": 9,
            "step": 5,
        })

        try:
            upsert_analysis(session_id, analysis, render_instruction)
        except Exception:
            pass

        # Phase 9+: Rendering (SAM2 segmentation if available, else Gemini direct)
        _set_session(session_id, {"status": "rendering", "step": 5})
        from watermark import apply_watermark

        with open(local_path, "rb") as f:
            img_bytes = f.read()

        # SAM2: only attempt if FAL_KEY is configured AND fal_client is installed
        mask_bytes = None
        if os.environ.get("FAL_KEY"):
            try:
                from segment_sam2 import segment_window
                mask_bytes = segment_window(img_bytes)
                _set_session(session_id, {"mask_bytes": mask_bytes})
                if mask_bytes:
                    print(f"[{session_id}] SAM2 mask obtained ({len(mask_bytes)} bytes)")
                else:
                    print(f"[{session_id}] SAM2 returned no mask — using Gemini pipeline")
            except (ImportError, ModuleNotFoundError) as e:
                print(f"[{session_id}] SAM2 skipped (fal_client not installed: {e}) — using Gemini pipeline")
        else:
            print(f"[{session_id}] SAM2 skipped (no FAL_KEY) — using Gemini pipeline")

        render_bytes, method = _render_with_fallback(
            img_bytes, render_instruction, mask_bytes
        )
        watermarked = apply_watermark(render_bytes)

        # Upload render (non-fatal — fall back to data URI if Supabase is unavailable)
        render_url = None
        try:
            from upload_supabase import upload_render, insert_render
            upload_result = upload_render(watermarked, session_id, 0)
            render_url = upload_result["public_url"]
            try:
                insert_render(session_id, render_url, {}, method)
                upsert_session(session_id, {"status": "done"})
            except Exception:
                pass
        except Exception as upload_err:
            print(f"[{session_id}] Supabase upload failed ({upload_err}), using data URI fallback")
            b64 = base64.b64encode(watermarked).decode()
            render_url = f"data:image/png;base64,{b64}"

        _set_session(session_id, {
            "status": "done",
            "render_url": render_url,
            "render_count": 0,
        })

    except RuntimeError as e:
        err_str = str(e)
        if err_str.startswith("QUALITY_FAIL:"):
            # Extract the reason safely — don't re-parse potentially truncated JSON
            payload = err_str[len("QUALITY_FAIL:"):]
            try:
                error_data = json.loads(payload)
                reason = error_data.get("reason", "Foto voldoet niet aan de kwaliteitseisen.")
            except (json.JSONDecodeError, Exception):
                reason = payload if len(payload) < 300 else "Foto voldoet niet aan de kwaliteitseisen."
            _set_session(session_id, {"status": "error", "error": reason})
        else:
            print(f"[{session_id}] RuntimeError: {err_str[:200]}")
            _set_session(session_id, {"status": "error", "error": err_str[:500]})
    except Exception as e:
        print(f"[{session_id}] Unexpected error: {e}")
        _set_session(session_id, {"status": "error", "error": str(e)[:500]})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
