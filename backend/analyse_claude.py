"""
analyse_claude.py — 9-phase Claude Vision pipeline for MRJ3.0
Phases 2–5 use image vision; phases 6–9 use accumulated text context.
"""
import os
import json
import time
import base64
import anthropic
from dotenv import load_dotenv
import sys
sys.path.insert(0, os.path.dirname(__file__))
import core

load_dotenv()

# Phase → UI step mapping for progress tracking
PHASE_TO_STEP = {2: 1, 3: 2, 4: 2, 5: 3, 6: 3, 7: 3, 8: 4, 9: 5}

VISION_PHASES = {2, 3, 4, 5}  # phases that need the image

MAX_RETRIES = 3
RETRY_DELAY = 2.0


def _encode_image(image_path: str) -> tuple[str, str]:
    """Return (base64_data, media_type) for the image file."""
    ext = os.path.splitext(image_path)[1].lower()
    media_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                 ".png": "image/png", ".webp": "image/webp"}
    media_type = media_map.get(ext, "image/jpeg")
    with open(image_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8"), media_type


def _call_claude(system_prompt: str, user_content: list, model: str, timeout: float = 90.0) -> str:
    """Call Claude with retry logic. Returns raw text response."""
    client = anthropic.Anthropic(
        api_key=os.environ["ANTHROPIC_API_KEY"],
        timeout=timeout,
    )
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=2048,
                system=system_prompt,
                messages=[{"role": "user", "content": user_content}],
            )
            return response.content[0].text
        except anthropic.RateLimitError as e:
            last_error = e
            time.sleep(RETRY_DELAY * (attempt + 1))
        except anthropic.InternalServerError as e:
            last_error = e
            time.sleep(RETRY_DELAY)
        except Exception as e:
            raise RuntimeError(f"Claude call failed: {e}") from e
    raise RuntimeError(f"Claude call failed after {MAX_RETRIES} retries: {last_error}")


def _parse_json_response(text: str) -> dict:
    """Extract and parse JSON from a Claude response."""
    # Strip markdown code fences if present
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
    return json.loads(text.strip())


def run_pipeline(
    session_id: str,
    image_path: str,
    progress_callback=None,
) -> dict:
    """
    Run phases 2–9 sequentially. Returns dict with keys:
      - analysis: AnalysisResult dict (merged phases 3–8)
      - render_instruction: RenderInstruction dict (phase 9)
    Raises RuntimeError on quality check failure (phase 2).
    """
    model = core.ANALYSIS_MODEL
    fallback = core.FALLBACK_MODEL
    img_b64, img_media = _encode_image(image_path)

    accumulated: dict = {}  # phase number → parsed JSON

    def _report(phase: int):
        if progress_callback:
            step = PHASE_TO_STEP.get(phase, phase)
            progress_callback(phase=phase, step=step)

    # ── PHASE 2: Quality check ─────────────────────────────────────────────────
    _report(2)
    system2 = core.get_phase_prompt(2)
    content2 = [
        {"type": "image", "source": {"type": "base64", "media_type": img_media, "data": img_b64}},
        {"type": "text", "text": "Voer de kwaliteitscheck uit en retourneer alleen geldige JSON."},
    ]
    try:
        raw2 = _call_claude(system2, content2, model)
        result2 = _parse_json_response(raw2)
    except Exception:
        raw2 = _call_claude(system2, content2, fallback)
        result2 = _parse_json_response(raw2)

    if not result2.get("quality_pass", False):
        raise RuntimeError(f"QUALITY_FAIL:{json.dumps(result2)}")

    accumulated[2] = result2

    # ── PHASES 3–9: Analysis ───────────────────────────────────────────────────
    # Use faster sonnet for text-only phases (6-9) — 4x faster than opus
    TEXT_MODEL = core.FALLBACK_MODEL  # claude-sonnet-4-5

    for phase in range(3, 10):
        _report(phase)
        system_p = core.get_phase_prompt(phase)
        phase_model = model if phase in VISION_PHASES else TEXT_MODEL

        # Trim accumulated context: only send phase 2 + last 2 phases
        # Prevents token bloat that slows Claude on late phases
        keys = list(accumulated.keys())
        trimmed = {}
        if 2 in accumulated:
            trimmed[2] = accumulated[2]
        for k in keys[-2:]:
            trimmed[k] = accumulated[k]

        context_text = (
            f"ACCUMULATED ANALYSIS SO FAR:\n{json.dumps(trimmed, ensure_ascii=False, indent=2)}\n\n"
            "Voer deze fase uit en retourneer alleen geldige JSON."
        )

        if phase in VISION_PHASES:
            user_content = [
                {"type": "image", "source": {"type": "base64", "media_type": img_media, "data": img_b64}},
                {"type": "text", "text": context_text},
            ]
        else:
            user_content = [{"type": "text", "text": context_text}]

        try:
            raw = _call_claude(system_p, user_content, phase_model)
            result = _parse_json_response(raw)
        except json.JSONDecodeError:
            correction = user_content + [
                {"type": "text", "text": "Je vorige antwoord was geen geldige JSON. Geef ALLEEN geldige JSON terug."}
            ]
            raw = _call_claude(system_p, correction, core.FALLBACK_MODEL)
            result = _parse_json_response(raw)
        except Exception as e:
            # Phase failure is non-fatal: log and continue with empty result
            print(f"[analyse] Phase {phase} failed: {e}")
            result = {}

        accumulated[phase] = result

    # ── Assemble output ────────────────────────────────────────────────────────
    analysis = {}
    for phase in range(3, 9):
        analysis.update(accumulated.get(phase, {}))

    render_instruction = accumulated.get(9, {})

    # Cache to disk (as per core.py constants)
    os.makedirs("data", exist_ok=True)
    with open(core.JSON_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(accumulated, f, ensure_ascii=False, indent=2)
    with open(core.ANALYSE_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump({"analysis": analysis, "render_instruction": render_instruction}, f, ensure_ascii=False, indent=2)

    return {"analysis": analysis, "render_instruction": render_instruction}
