"""
render_gemini.py — Gemini image generation with multi-model fallback for MRJ3.0
Optimised for speed (flash-first) and quality (detailed prompt engineering).
"""
import os
import io
import time
import base64
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# Speed-optimised fallback order: fastest first, pro as last resort
RENDER_MODELS = [
    "gemini-2.5-flash-image",           # fastest — ~5-8s
    "gemini-3.1-flash-image-preview",   # newer flash — slightly slower
    "gemini-3-pro-image-preview",       # highest quality, slowest
]

TRANSIENT_CODES = {429, 500, 503}
FATAL_CODES = {400, 404}
MAX_RETRIES = 1       # reduced from 2 — one retry per model max
RETRY_DELAY = 1.5     # reduced from 3.0s


def _build_render_prompt(render_instruction: dict, config_override: dict | None = None) -> str:
    """Build a highly detailed image generation prompt for photorealistic blinds rendering."""
    ri = render_instruction.copy()
    if config_override:
        ri.update(config_override)

    product = ri.get("product_type", "Aluminum Venetian Blinds")
    color = ri.get("color_name", "")
    hex_code = ri.get("hex_code", "")
    mount = ri.get("mount_type", "inside mount")
    sections = ri.get("window_sections", 1)
    lighting = ri.get("lighting_condition", "daylight")
    state = ri.get("state", "fully lowered")
    slat = ri.get("slat_width", "50mm")
    has_ladder_tape = ri.get("ladder_tape", False)
    scene = ri.get("scene_description", "")
    camera = ri.get("camera_angle", "straight-on interior view")
    room_ctx = ri.get("room_context", "")
    negative = ri.get("negative_prompt", "")

    # Material-specific detail
    is_wood = "hout" in product.lower() or "wood" in product.lower() or "bamboe" in product.lower()
    material_detail = (
        "Each slat must show visible wood grain texture running horizontally along the slat length. "
        "The grain should have subtle natural variation — not uniform. "
        "Wood surface should have a satin matte finish with very slight specular sheen at glancing angles."
    ) if is_wood else (
        "Each slat must have a smooth, uniform matte aluminum finish. "
        "Show subtle metallic sheen — a faint specular highlight along the top edge of each slat. "
        "The surface should look powder-coated, not glossy or mirror-like."
    )

    # Ladder type detail
    ladder_detail = (
        "LADDER TAPE (ladderband): Wide fabric tape (~12mm) running vertically on both sides of the blind, "
        "connecting each slat. The tape must be visible as a continuous vertical fabric strip in the SAME color "
        f"as the slats ({color}, {hex_code}). The tape creates a cleaner, more premium appearance. "
        "Each slat rests in a horizontal notch of the tape."
    ) if has_ladder_tape else (
        "LADDER CORD (ladderkoord): Thin cords (~2mm) running vertically on both sides, "
        "connecting each slat with small horizontal rungs like a miniature ladder. "
        f"The cord should be in the SAME color family as the slats ({color}). "
        "Each slat is held between two thin horizontal cord rungs."
    )

    # Slat width proportions
    slat_mm = int(slat.replace("mm", "").strip()) if "mm" in slat else 50
    slat_proportion = (
        f"Slat width is {slat_mm}mm. "
        f"{'These are NARROW slats — approximately 1 inch wide. Many slats should be visible.' if slat_mm <= 25 else ''}"
        f"{'These are STANDARD/WIDE slats — approximately 2 inches wide. Fewer slats visible, each clearly distinct.' if slat_mm >= 50 else ''}"
    )

    prompt = f"""Photorealistic interior photograph of a room with {product} installed on the window.

CRITICAL INSTRUCTION: Keep the ENTIRE room, walls, furniture, floor, ceiling, and all existing elements
EXACTLY as they appear in the reference photo. ONLY add the venetian blind to the window area.
Do NOT change any colors, lighting, or objects in the room.

═══ BLIND SPECIFICATIONS ═══
• Product: {product}
• Color: {color} (exact hex: {hex_code}) — the slats MUST match this exact color
• Mount: {mount} — {"blind sits INSIDE the window recess, flush with the wall" if "inside" in mount.lower() else "blind sits OUTSIDE the window recess, mounted on the wall above the frame"}
• Window sections: {sections}
• Slat angle / state: {state}
• {slat_proportion}

═══ MATERIAL & TEXTURE ═══
{material_detail}

═══ LADDER SYSTEM ═══
{ladder_detail}

═══ LIGHTING & SHADOW PHYSICS ═══
Lighting condition: {lighting}
• Light passing THROUGH the slats must cast parallel horizontal shadow lines on the wall/floor behind the blind.
  The shadow lines must match the slat spacing and angle.
• The TOP edge of each slat facing the light catches a thin highlight.
• The UNDERSIDE of each slat is in soft shadow (ambient occlusion).
• Between the slats, thin strips of the window or outdoor scene may be visible depending on tilt angle.
• The blind casts a subtle soft shadow on the window frame/wall where it's mounted.
• Overall room lighting must remain consistent with the reference photo.

═══ RENDERING QUALITY ═══
• Professional interior photography quality — shot on a full-frame camera at f/4, ISO 200
• Natural depth of field: blind and window in sharp focus, background slightly softer
• Camera angle: {camera}
• No lens distortion, no vignetting
• Color-accurate: the blind color MUST precisely match hex {hex_code}
• Each individual slat must be clearly distinguishable with consistent spacing
• The pull cord / wand mechanism should be visible on one side

═══ SCENE ═══
Room context: {room_ctx}
Scene: {scene}

═══ AVOID ═══
{negative if negative else "Cartoon style, 3D render look, plastic appearance, incorrect slat angles, floating elements, distorted perspective, wrong blind color, blurry slats, missing ladder system, unrealistic shadows, oversaturated colors, visible AI artifacts"}
"""
    return prompt


def generate_render(
    image_bytes: bytes,
    render_instruction: dict,
    config_override: dict | None = None,
) -> bytes:
    """
    Generate a photorealistic render using Gemini.

    Args:
        image_bytes: Original room image as bytes
        render_instruction: RenderInstruction dict from Phase 9
        config_override: Optional user config overrides (slat_width, lighting_condition, etc.)

    Returns:
        PNG image bytes of the rendered result

    Raises:
        RuntimeError if all models fail
    """
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    prompt = _build_render_prompt(render_instruction, config_override)

    # Encode original image for multimodal input
    img_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")

    last_error = None

    for model_name in RENDER_MODELS:
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[prompt, img_part],
                    config=types.GenerateContentConfig(
                        response_modalities=["Text", "Image"],
                        temperature=0.8,  # slightly lower for more accurate color reproduction
                    ),
                )

                # Extract image from response
                for part in response.candidates[0].content.parts:
                    if part.inline_data is not None:
                        return part.inline_data.data  # raw PNG bytes

                # If no image in response, try next model
                last_error = RuntimeError(f"Model {model_name} returned no image")
                break

            except Exception as e:
                err_str = str(e)
                last_error = e

                # Check for fatal error codes — skip to next model immediately
                if any(f"{code}" in err_str for code in FATAL_CODES):
                    break

                # Transient error — retry with backoff
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                break  # exhausted retries for this model

    raise RuntimeError(f"All Gemini models failed. Last error: {last_error}")
