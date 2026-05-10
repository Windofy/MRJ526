"""
analyse_claude.py — Streamlined 2-call Claude Vision pipeline for MRJ526
Call 1: Quality check — claude-haiku-4-5 (instant, ~1s)
Call 2: Color extraction + catalog match + render planning — haiku-4-5 first,
        fallback to sonnet-4-5 only when JSON parsing fails (~3-6s total)
"""
import os
import re
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
PHASE_TO_STEP = {2: 1, 3: 2, 5: 3, 9: 5}

MODEL_FAST     = "claude-haiku-4-5"   # Call 1 (always) + Call 2 first attempt
MODEL_FALLBACK = "claude-sonnet-4-5"  # Call 2 fallback on JSON-parse failure

MAX_RETRIES = 2
RETRY_DELAY = 1.5


def _encode_image(image_path: str) -> tuple[str, str]:
    """Return (base64_data, media_type) for the image file.

    Two-stage pipeline:
      1. Cap longest edge to MAX_EDGE (1568 px — Claude's internal max).
         This alone eliminates most oversized uploads and cuts transfer time.
      2. Progressive JPEG quality/scale reduction until the result is under
         CLAUDE_MAX_BYTES (API hard limit).

    Falls back to raw encoding when Pillow is not installed.
    """
    CLAUDE_MAX_BYTES = 3_900_000
    MAX_EDGE = 1568  # Claude's internal max resolution — no benefit going higher

    ext = os.path.splitext(image_path)[1].lower()
    media_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                 ".png": "image/png", ".webp": "image/webp"}
    media_type = media_map.get(ext, "image/jpeg")

    try:
        from PIL import Image
        import io

        img = Image.open(image_path)
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")

        # ── Stage 1: cap longest edge to MAX_EDGE ──────────────────────────
        w, h = img.size
        if max(w, h) > MAX_EDGE:
            if w >= h:
                new_w, new_h = MAX_EDGE, max(1, int(h * MAX_EDGE / w))
            else:
                new_w, new_h = max(1, int(w * MAX_EDGE / h)), MAX_EDGE
            img = img.resize((new_w, new_h), Image.LANCZOS)

        # ── Stage 2: compress until under byte limit ────────────────────────
        output_media = "image/jpeg"
        quality = 85
        scale = 1.0

        for _attempt in range(8):
            buf = io.BytesIO()
            cw = int(img.width * scale)
            ch = int(img.height * scale)
            resized = img.resize((cw, ch), Image.LANCZOS) if scale < 1.0 else img
            resized.save(buf, format="JPEG", quality=quality, optimize=True)
            data = buf.getvalue()

            if len(data) <= CLAUDE_MAX_BYTES:
                return base64.standard_b64encode(data).decode("utf-8"), output_media

            if quality > 60:
                quality -= 10
            else:
                scale *= 0.75

        return base64.standard_b64encode(data).decode("utf-8"), output_media

    except ImportError:
        with open(image_path, "rb") as f:
            return base64.standard_b64encode(f.read()).decode("utf-8"), media_type


def _call_claude(
    system_prompt: str,
    user_content: list,
    max_tokens: int = 2048,
    model: str = MODEL_FAST,
) -> str:
    """Call Claude with retry logic. Returns raw text response."""
    client = anthropic.Anthropic(
        api_key=os.environ["ANTHROPIC_API_KEY"],
        timeout=120.0,
    )
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
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


def _extract_json(text: str) -> dict:
    """Robustly extract JSON from Claude response, handling truncation and markdown."""
    text = text.strip()

    if text.startswith("```"):
        lines = text.split("\n")
        if lines[-1].strip() == "```":
            text = "\n".join(lines[1:-1])
        else:
            text = "\n".join(lines[1:])
        text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    if '{' in text:
        json_start = text.index('{')
        fragment = text[json_start:]
        open_braces = fragment.count('{') - fragment.count('}')
        open_brackets = fragment.count('[') - fragment.count(']')

        fixed = fragment.rstrip()
        if fixed.endswith(','):
            fixed = fixed[:-1]
        if fixed.count('"') % 2 != 0:
            fixed += '"'
        fixed += ']' * max(0, open_brackets) + '}' * max(0, open_braces)

        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass

    raise json.JSONDecodeError("Could not extract JSON from response", text, 0)


# ── PROMPTS ────────────────────────────────────────────────────────────────────

def _quality_prompt() -> str:
    """Call 1: Quick quality gate — minimal tokens, fastest possible."""
    return (
        "Quality-check agent for interior room photos.\n"
        "PASS criteria: window visible, room recognisable, not blurry/dark/extreme angle.\n"
        "Return ONLY: {\"quality_pass\": true}  OR  "
        "{\"quality_pass\": false, \"reason\": \"<Dutch feedback, max 10 words>\"}\n"
        "No other output."
    )


def _color_config_prompt() -> str:
    """Call 2: Extract room colors, match to catalog, produce render instruction.
    Single image call — no style analysis, no mood, no descriptions.
    """
    catalog_text = core.get_catalog_as_text()
    return f"""You are a Color Matcher for Mr. Jealousy venetian blinds.

TASK: Look at the room photo and do TWO things:

1. EXTRACT exactly 5 dominant colors visible in the room (walls, furniture, floor, accents).
2. SELECT exactly 4 products from the catalog below that best complement those room colors.
3. DETERMINE window configuration for the render.

Return ONE JSON object — nothing else:

{{
  "colour_palette": [
    {{"hex_code": "#xxxxxx", "extracted_source": "muur / vloer / meubel / etc"}},
    ... (5 items)
  ],
  "suggestions": [
    {{
      "productType": "Aluminium Jaloezieën" or "Houten Jaloezieën",
      "material": "Aluminium" or "Hout",
      "colorName": "<exact name from catalog>",
      "colorHex": "<exact hex from catalog>",
      "suitabilityScore": 1-100,
      "reasoning": "<max 1 Dutch sentence why this color fits>"
    }},
    ... (exactly 4 items)
  ],
  "windowCheck": {{
    "detectedWindowCount": <integer>,
    "recommendation": "in de dag" or "op de dag",
    "recess_depth_cm": <integer or null>
  }},
  "render_instruction": {{
    "product_type": "<productType of top suggestion>",
    "color_name": "<colorName of top suggestion>",
    "hex_code": "<colorHex of top suggestion>",
    "mount_type": "inside mount" or "outside mount",
    "window_sections": <integer>,
    "slat_width": "25mm" or "50mm",
    "ladder_tape": false,
    "scene_description": "<2 sentences max, Dutch, describe window + light>",
    "negative_prompt": "distorted blinds, wrong color, floating slats, gaps in slats",
    "camera_angle": "straight-on eye level"
  }}
}}

CATALOG (use ONLY these color names and hex codes):
{catalog_text}

Return ONLY valid JSON. No markdown. No explanation."""


# ── MAIN PIPELINE ──────────────────────────────────────────────────────────────

def run_pipeline(
    session_id: str,
    image_path: str,
    progress_callback=None,
) -> dict:
    """
    2-call pipeline: quality check + color/config analysis.
    Returns dict with keys: analysis, render_instruction
    Raises RuntimeError on quality check failure.
    """
    img_b64, img_media = _encode_image(image_path)

    def _report(phase: int):
        if progress_callback:
            step = PHASE_TO_STEP.get(phase, phase)
            progress_callback(phase=phase, step=step)

    image_block = {"type": "image", "source": {"type": "base64", "media_type": img_media, "data": img_b64}}

    # ── CALL 1: Quality check (Haiku — tiny prompt, tiny output) ──────────
    _report(2)
    print(f"[{session_id}] Call 1/2: Quality check ({MODEL_FAST})...")
    t0 = time.time()

    raw_quality = _call_claude(
        _quality_prompt(),
        [image_block, {"type": "text", "text": "Check quality."}],
        max_tokens=64,
        model=MODEL_FAST,
    )
    quality_result = _extract_json(raw_quality)
    print(f"[{session_id}] Call 1/2 done in {time.time()-t0:.1f}s")

    if not quality_result.get("quality_pass", False):
        raise RuntimeError(f"QUALITY_FAIL:{json.dumps(quality_result)}")

    # ── CALL 2: Color match + config — Haiku first, Sonnet fallback ───────
    _report(3)
    print(f"[{session_id}] Call 2/2: Color match + config ({MODEL_FAST})...")
    t1 = time.time()

    _call2_prompt = _color_config_prompt()
    _call2_content = [image_block, {"type": "text", "text": "Analyseer de kamer. Retourneer ALLEEN geldige JSON."}]

    result = None
    for _model in (MODEL_FAST, MODEL_FALLBACK):
        raw_result = _call_claude(
            _call2_prompt,
            _call2_content,
            max_tokens=2048,
            model=_model,
        )
        try:
            result = _extract_json(raw_result)
            if _model == MODEL_FALLBACK:
                print(f"[{session_id}] Call 2/2 JSON parsed with fallback model ({MODEL_FALLBACK})")
            break
        except json.JSONDecodeError:
            if _model == MODEL_FAST:
                print(f"[{session_id}] Call 2/2 Haiku JSON parse failed — retrying with {MODEL_FALLBACK}...")
            else:
                raise RuntimeError("Call 2: JSON parsing failed on both Haiku and Sonnet")

    _report(9)
    print(f"[{session_id}] Call 2/2 done in {time.time()-t1:.1f}s")

    # ── Assemble output ────────────────────────────────────────────────────
    analysis = {
        "colour_palette": result.get("colour_palette", []),
        "suggestions": result.get("suggestions", []),
        "windowCheck": result.get("windowCheck", {}),
    }

    render_instruction = result.get("render_instruction", {})

    # Derive mount_type from windowCheck if render_instruction missing it
    if "mount_type" not in render_instruction:
        rec = result.get("windowCheck", {}).get("recommendation", "in de dag")
        render_instruction["mount_type"] = "inside mount" if "in" in rec else "outside mount"

    total = time.time() - t0
    print(f"[{session_id}] Pipeline complete in {total:.1f}s (2 API calls)")

    # Cache to disk
    os.makedirs("data", exist_ok=True)
    with open(core.JSON_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump({"quality": quality_result, "result": result}, f, ensure_ascii=False, indent=2)
    with open(core.ANALYSE_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump({"analysis": analysis, "render_instruction": render_instruction}, f, ensure_ascii=False, indent=2)

    return {"analysis": analysis, "render_instruction": render_instruction}
