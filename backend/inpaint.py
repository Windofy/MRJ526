"""
inpaint.py — FLUX.1 Dev Inpainting via fal.ai for MRJ3.0
Places the jaloezie precisely within the SAM2 window mask.
"""
import os
import io
import httpx
import fal_client
from dotenv import load_dotenv

load_dotenv()

# FLUX inpainting endpoint on fal.ai
FLUX_INPAINT_MODEL = "fal-ai/flux/dev/image-to-image"
FLUX_INPAINT_DIRECT = "fal-ai/flux-pro/v1/inpainting"  # higher quality, paid

# Fallback to cheaper model if pro unavailable
INPAINT_MODELS = [
    "fal-ai/flux-pro/v1/inpainting",
    "fal-ai/flux/dev/image-to-image",
    "fal-ai/stable-diffusion-v3-medium/inpainting",
]


def _build_inpaint_prompt(render_instruction: dict, config_override: dict | None = None) -> tuple[str, str]:
    """
    Returns (positive_prompt, negative_prompt) for inpainting.
    Focused on the blind only — the mask handles placement.
    """
    ri = render_instruction.copy()
    if config_override:
        ri.update(config_override)

    product = ri.get("product_type", "Aluminum Venetian Blinds")
    color = ri.get("color_name", "")
    hex_code = ri.get("hex_code", "")
    mount = ri.get("mount_type", "inside mount")
    state = ri.get("state", "fully lowered")
    slat = ri.get("slat_width", "50mm")
    ladder = "ladder tape" if ri.get("ladder_tape") else "ladder cord"
    lighting = ri.get("lighting_condition", "natural daylight")

    positive = (
        f"Photorealistic {product}, color {color} (hex {hex_code}), "
        f"{state}, {slat} slats, {ladder}, {mount}. "
        f"Soft realistic {lighting} shadows through slats. "
        f"Interior architecture photography. 8K sharp detail. "
        f"Seamlessly integrated into window frame. "
        f"Physically accurate shadow striping on floor and wall."
    )

    negative = ri.get("negative_prompt") or (
        "cartoon, 3d render, plastic, floating, wrong color, distorted frame, "
        "blurry, low quality, artifacts, duplicate blinds, visible seams, "
        "watermark, text, oversaturated"
    )

    return positive, negative


def generate_inpaint(
    image_bytes: bytes,
    mask_bytes: bytes,
    render_instruction: dict,
    config_override: dict | None = None,
) -> tuple[bytes, str]:
    """
    Inpaint the blind into the window mask using FLUX via fal.ai.

    Returns:
        (image_bytes, model_used) tuple

    Raises:
        RuntimeError if all inpainting models fail.
    """
    fal_key = os.environ.get("FAL_KEY")
    if not fal_key:
        raise RuntimeError("FAL_KEY not configured")

    os.environ["FAL_KEY"] = fal_key

    positive_prompt, negative_prompt = _build_inpaint_prompt(render_instruction, config_override)

    # Upload both images to fal CDN
    image_url = fal_client.upload(image_bytes, content_type="image/jpeg")
    mask_url = fal_client.upload(mask_bytes, content_type="image/png")

    last_error = None

    for model in INPAINT_MODELS:
        try:
            result = fal_client.run(
                model,
                arguments={
                    "image_url": image_url,
                    "mask_url": mask_url,
                    "prompt": positive_prompt,
                    "negative_prompt": negative_prompt,
                    "strength": 0.90,          # high: fully replace masked area
                    "num_inference_steps": 28,
                    "guidance_scale": 7.5,
                    "num_images": 1,
                    "output_format": "png",
                },
            )

            # Extract output image URL
            images = result.get("images") or result.get("image") or []
            if isinstance(images, dict):
                images = [images]
            if not images:
                last_error = RuntimeError(f"Model {model} returned no images")
                continue

            output_url = images[0].get("url") or images[0]
            resp = httpx.get(output_url, timeout=60)
            resp.raise_for_status()
            return resp.content, model

        except Exception as e:
            last_error = e
            print(f"[INPAINT] Model {model} failed: {e}")
            continue

    raise RuntimeError(f"All inpainting models failed. Last: {last_error}")
