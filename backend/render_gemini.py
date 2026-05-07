"""
render_gemini.py — Gemini image generation with multi-model fallback for MRJ3.0
"""
import os
import io
import time
import base64
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# Ordered fallback list — primary first
RENDER_MODELS = [
    "gemini-2.5-flash-preview-05-20",
    "gemini-2.0-flash-preview-image-generation",
    "gemini-2.0-flash-exp",
]

TRANSIENT_CODES = {429, 500, 503}
FATAL_CODES = {400, 404}
MAX_RETRIES = 2
RETRY_DELAY = 3.0


def _build_render_prompt(render_instruction: dict, config_override: dict | None = None) -> str:
    """Build an English image generation prompt from the RenderInstruction dict."""
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
    ladder = "with ladder tape" if ri.get("ladder_tape") else "with ladder cord"
    scene = ri.get("scene_description", "")
    camera = ri.get("camera_angle", "straight-on interior view")
    room_ctx = ri.get("room_context", "")
    negative = ri.get("negative_prompt", "")

    prompt = f"""Photorealistic interior visualization of a room with {product} installed on the window.

BLIND SPECIFICATIONS:
- Product: {product}
- Color: {color} (hex: {hex_code})
- Mount type: {mount}
- Window sections: {sections}
- Slat width: {slat}
- Blind state: {state}
- Ladder type: {ladder}

LIGHTING: {lighting}
CAMERA ANGLE: {camera}
ROOM CONTEXT: {room_ctx}

SCENE DESCRIPTION:
{scene}

RENDERING REQUIREMENTS:
- Photorealistic, high quality interior photography style
- Physically accurate slat shadows and light interaction
- The blind must be correctly mounted ({mount})
- Maintain all existing room elements, furniture, and colors exactly
- Do not alter the room — only add the blind to the window
- Sharp focus on the blind and window area
- Natural depth of field

AVOID: {negative if negative else 'cartoon style, distortion, artifacts, floating elements, wrong colors'}
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
                        temperature=1.0,
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
