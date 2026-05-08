"""
analyse_claude.py — Optimised 3-call Claude Vision pipeline for MRJ3.0
Consolidated from 8 sequential calls → 3 calls:
  Call 1: Quality check (fast gate)
  Call 2: Vision analysis — phases 3+4+5 merged (single image send)
  Call 3: Text reasoning — phases 6+7+8+9 merged (no image needed)
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
PHASE_TO_STEP = {2: 1, 3: 2, 4: 2, 5: 3, 6: 3, 7: 3, 8: 4, 9: 5}

# Single model for all calls — Sonnet is fast enough at 3 consolidated calls
# Quality check is only 256 tokens so speed difference with Haiku is negligible
MODEL_FAST = "claude-sonnet-4-5"
MODEL_ANALYSIS = "claude-sonnet-4-5"

MAX_RETRIES = 2
RETRY_DELAY = 1.5


def _encode_image(image_path: str) -> tuple[str, str]:
    """Return (base64_data, media_type) for the image file."""
    ext = os.path.splitext(image_path)[1].lower()
    media_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                 ".png": "image/png", ".webp": "image/webp"}
    media_type = media_map.get(ext, "image/jpeg")
    with open(image_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8"), media_type


def _call_claude(system_prompt: str, user_content: list, model: str = MODEL_ANALYSIS, max_tokens: int = 4096) -> str:
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

    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json) and last line (```) if present
        if lines[-1].strip() == "```":
            text = "\n".join(lines[1:-1])
        else:
            text = "\n".join(lines[1:])
        text = text.strip()

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object in text (handles extra text before/after)
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Handle truncated JSON: try to close open braces/brackets
    # Count unclosed braces
    if '{' in text:
        json_start = text.index('{')
        fragment = text[json_start:]
        open_braces = fragment.count('{') - fragment.count('}')
        open_brackets = fragment.count('[') - fragment.count(']')

        # Remove trailing incomplete string (cut at last complete value)
        # Find last complete key-value pair
        fixed = fragment.rstrip()
        if fixed.endswith(','):
            fixed = fixed[:-1]

        # Close any unclosed strings
        if fixed.count('"') % 2 != 0:
            fixed += '"'

        # Close brackets and braces
        fixed += ']' * max(0, open_brackets) + '}' * max(0, open_braces)

        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass

    raise json.JSONDecodeError(f"Could not extract JSON from response", text, 0)


# ── CONSOLIDATED PROMPTS ───────────────────────────────────────────────────────

def _quality_prompt() -> str:
    """Phase 2: Quick quality gate."""
    return (
        "You are a quality-check agent for interior room photos.\n"
        "Check: alignment, framing (window visible), lighting, focus, resolution, angle.\n"
        "If ALL pass: return {\"quality_pass\": true}\n"
        "If ANY fail: return {\"quality_pass\": false, \"reason\": \"<specific Dutch feedback>\"}\n"
        "Return ONLY valid JSON. No explanation."
    )


def _vision_analysis_prompt() -> str:
    """Phases 3+4+5 merged: extract style, colors, and window architecture in ONE call."""
    catalog_text = core.get_catalog_as_text()
    return f"""You are a World-Class Interior Vision Architect for Mr. Jealousy venetian blinds.
Analyse the uploaded room photo and return ONE JSON object with ALL of the following sections:

SECTION 1 — INTERIOR STYLE:
- "style": single style label (e.g. "Japandi", "Industrial", "Scandinavisch")
- "styleSummary": max 2 sentences in Dutch
- "styleDescription": 3-5 sentences in Dutch describing the interior character
- "roomMood": mood description in Dutch

SECTION 2 — COLOR DNA:
- "colour_palette": array of exactly 5 objects, each with:
  - "hex_code": actual hex of a visible color in the room
  - "extracted_source": where in the room this color comes from (Dutch)
  - "matched_catalog_color": closest match from the Mr. Jealousy catalog below

SECTION 3 — WINDOW ARCHITECTURE:
- "windowCheck": object with:
  - "windowType": type classification (Dutch)
  - "detectedWindowCount": integer number of glass sections
  - "recommendation": mounting recommendation ("in de dag" or "op de dag") (Dutch)
  - "reasoning": why this mounting (Dutch, max 2 sentences)
  - "specialConsiderations": any obstacles, handles, vents (Dutch)
  - "obstacles": boolean
  - "recess_depth_cm": estimated depth in cm
  - "frame_material": detected material

{catalog_text}

Return ONLY valid JSON. No markdown. No code fences. All text values in Dutch."""


def _text_reasoning_prompt() -> str:
    """Phases 6+7+8+9 merged: mounting, lighting, catalog match, render planning."""
    catalog_text = core.get_catalog_as_text()
    return f"""You are a Window Treatment Configurator and Render Planner for Mr. Jealousy.
Based on the analysis provided, determine the final configuration and render instructions.

Return ONE JSON object with ALL of the following sections:

SECTION 1 — MOUNTING STRATEGY:
- "mountingStrategy": object with:
  - "mount_type": "in de dag" or "op de dag"
  - "reasoning": Dutch explanation

SECTION 2 — LIGHTING CONDITIONS:
- "lightingConditions": description of detected lighting (Dutch)

SECTION 3 — PRODUCT SUGGESTIONS:
- "suggestions": array of exactly 3 objects, each with:
  - "productType": "Aluminium Jaloezieën" or "Houten Jaloezieën"
  - "material": "Aluminium" or "Hout"
  - "colorName": exact name from catalog
  - "colorHex": exact hex from catalog
  - "suitabilityScore": 1-100
  - "reasoning": why this color fits (Dutch, max 2 sentences)
- "materialSuggestions": array of recommended material types

SECTION 4 — RENDER INSTRUCTION (most important):
- "render_instruction": object conforming to RenderInstruction schema:
  - "product_type": selected product type
  - "color_name": exact catalog color name
  - "hex_code": exact hex from catalog
  - "mount_type": "inside mount" or "outside mount"
  - "window_sections": integer
  - "lighting_condition": detected lighting condition
  - "state": "fully lowered" or "half lowered"
  - "slat_width": "25mm" or "50mm"
  - "ladder_tape": boolean
  - "scene_description": 3-5 sentences describing the scene (Dutch)
  - "negative_prompt": things to avoid in rendering
  - "camera_angle": perspective description
  - "room_context": brief room context (Dutch)

ABSOLUTE PRODUCT LOCK — ONLY catalog colors allowed:
{catalog_text}

Return ONLY valid JSON. No markdown. No code fences. All text in Dutch where specified."""


# ── MAIN PIPELINE ──────────────────────────────────────────────────────────────

def run_pipeline(
    session_id: str,
    image_path: str,
    progress_callback=None,
) -> dict:
    """
    Run consolidated 3-call pipeline. Returns dict with keys:
      - analysis: AnalysisResult dict
      - render_instruction: RenderInstruction dict
    Raises RuntimeError on quality check failure.
    """
    img_b64, img_media = _encode_image(image_path)

    def _report(phase: int):
        if progress_callback:
            step = PHASE_TO_STEP.get(phase, phase)
            progress_callback(phase=phase, step=step)

    image_block = {"type": "image", "source": {"type": "base64", "media_type": img_media, "data": img_b64}}

    # ── CALL 1: Quality check (fast — small prompt, small output) ──────────
    _report(2)
    print(f"[{session_id}] Call 1/3: Quality check...")
    t0 = time.time()

    raw_quality = _call_claude(
        _quality_prompt(),
        [image_block, {"type": "text", "text": "Voer de kwaliteitscheck uit."}],
        model=MODEL_FAST,
        max_tokens=256,
    )
    quality_result = _extract_json(raw_quality)
    print(f"[{session_id}] Call 1/3 done in {time.time()-t0:.1f}s")

    if not quality_result.get("quality_pass", False):
        raise RuntimeError(f"QUALITY_FAIL:{json.dumps(quality_result)}")

    # ── CALL 2: Vision analysis (phases 3+4+5 merged) ─────────────────────
    _report(3)
    print(f"[{session_id}] Call 2/3: Vision analysis (style + colors + window)...")
    t1 = time.time()

    raw_vision = _call_claude(
        _vision_analysis_prompt(),
        [image_block, {"type": "text", "text": "Analyseer deze foto volledig. Retourneer ALLEEN geldige JSON."}],
        model=MODEL_ANALYSIS,
        max_tokens=4096,
    )
    vision_result = _extract_json(raw_vision)
    _report(5)
    print(f"[{session_id}] Call 2/3 done in {time.time()-t1:.1f}s")

    # ── CALL 3: Text reasoning (phases 6+7+8+9 merged) ────────────────────
    _report(7)
    print(f"[{session_id}] Call 3/3: Config + render planning...")
    t2 = time.time()

    context_text = (
        f"VISION ANALYSIS RESULTS:\n{json.dumps(vision_result, ensure_ascii=False, indent=2)}\n\n"
        "Based on this analysis, determine mounting, lighting, product suggestions, "
        "and render instructions. Retourneer ALLEEN geldige JSON."
    )

    raw_text = _call_claude(
        _text_reasoning_prompt(),
        [{"type": "text", "text": context_text}],
        model=MODEL_ANALYSIS,
        max_tokens=4096,
    )
    text_result = _extract_json(raw_text)
    _report(9)
    print(f"[{session_id}] Call 3/3 done in {time.time()-t2:.1f}s")

    # ── Assemble output ────────────────────────────────────────────────────
    analysis = {}
    # From vision call
    for key in ("style", "styleSummary", "styleDescription", "roomMood",
                "colour_palette", "windowCheck"):
        if key in vision_result:
            analysis[key] = vision_result[key]

    # From text call
    for key in ("suggestions", "materialSuggestions", "lightingConditions"):
        if key in text_result:
            analysis[key] = text_result[key]

    render_instruction = text_result.get("render_instruction", {})

    # Merge mounting info into render_instruction if missing
    if "mount_type" not in render_instruction and "mountingStrategy" in text_result:
        ms = text_result["mountingStrategy"]
        mount = ms.get("mount_type", "in de dag")
        render_instruction["mount_type"] = "inside mount" if "in" in mount else "outside mount"

    total = time.time() - t0
    print(f"[{session_id}] Pipeline complete in {total:.1f}s (3 API calls)")

    # Cache to disk
    accumulated = {2: quality_result, "vision": vision_result, "text": text_result}
    os.makedirs("data", exist_ok=True)
    with open(core.JSON_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(accumulated, f, ensure_ascii=False, indent=2)
    with open(core.ANALYSE_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump({"analysis": analysis, "render_instruction": render_instruction}, f, ensure_ascii=False, indent=2)

    return {"analysis": analysis, "render_instruction": render_instruction}
