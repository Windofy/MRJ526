"""
segment_sam2.py — SAM2 window segmentation via fal.ai for MRJ3.0
Returns a binary mask (white=window, black=rest) as PNG bytes.
"""
import os
import io
import base64
import httpx
import fal_client
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

# Min window area as fraction of total image area
MIN_WINDOW_AREA_RATIO = 0.02
MAX_WINDOW_AREA_RATIO = 0.80


def _upload_image_to_fal(image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
    """Upload image bytes to fal.ai and return a CDN URL."""
    url = fal_client.upload(image_bytes, content_type=mime_type)
    return url


def _pick_best_mask(masks: list, img_w: int, img_h: int) -> Image.Image | None:
    """
    From SAM2 output masks, pick the one that best represents a window:
    - Not too small (< 2% of image)
    - Not too large (> 80% = probably entire wall)
    - Prefer roughly rectangular shapes
    """
    total_area = img_w * img_h
    best = None
    best_score = -1

    for mask_data in masks:
        # mask_data is a dict with 'mask_image_url' or 'mask' key
        mask_url = mask_data.get("mask_image_url") or mask_data.get("url")
        if not mask_url:
            continue

        resp = httpx.get(mask_url, timeout=15)
        mask_img = Image.open(io.BytesIO(resp.content)).convert("L")
        mask_arr = mask_img.tobytes()

        # Count white pixels
        white_pixels = sum(1 for b in mask_arr if b > 128)
        ratio = white_pixels / total_area

        if ratio < MIN_WINDOW_AREA_RATIO or ratio > MAX_WINDOW_AREA_RATIO:
            continue

        # Score: prefer masks that are ~10–40% of image (typical window)
        ideal = 0.20
        score = 1.0 - abs(ratio - ideal)

        if score > best_score:
            best_score = score
            # Resize to original image dimensions if needed
            if mask_img.size != (img_w, img_h):
                mask_img = mask_img.resize((img_w, img_h), Image.NEAREST)
            best = mask_img

    return best


def segment_window(image_bytes: bytes) -> bytes | None:
    """
    Detect the window in the image using SAM2 via fal.ai.

    Args:
        image_bytes: Original room image bytes

    Returns:
        Binary mask PNG bytes (white=window area, black=rest),
        or None if no window could be detected.
    """
    fal_key = os.environ.get("FAL_KEY")
    if not fal_key:
        return None  # Graceful fallback — no SAM2 key configured

    os.environ["FAL_KEY"] = fal_key

    try:
        # Upload image to fal CDN
        img = Image.open(io.BytesIO(image_bytes))
        img_w, img_h = img.size
        cx, cy = img_w // 2, img_h // 2  # center point as initial window hint

        image_url = _upload_image_to_fal(image_bytes, "image/jpeg")

        # Run SAM2 with center-point prompt (windows are usually centered)
        # Also try upper-center and middle-left/right prompts
        prompt_points = [
            [cx, cy],           # center
            [cx, cy - img_h // 6],  # upper-center
        ]

        result = fal_client.run(
            "fal-ai/sam2",
            arguments={
                "image_url": image_url,
                "prompts": [
                    {
                        "type": "point",
                        "data": prompt_points,
                        "label": [1, 1],  # 1 = foreground
                    }
                ],
            },
        )

        masks = result.get("masks") or result.get("output") or []
        if not masks:
            return None

        best_mask = _pick_best_mask(masks, img_w, img_h)
        if best_mask is None:
            return None

        # Convert to clean binary (pure black/white)
        binary = best_mask.point(lambda x: 255 if x > 128 else 0)
        buf = io.BytesIO()
        binary.save(buf, format="PNG")
        return buf.getvalue()

    except Exception as e:
        # SAM2 failure is non-fatal — caller uses Gemini fallback
        print(f"[SAM2] Segmentation failed: {e}")
        return None


def mask_to_url(mask_bytes: bytes, session_id: str) -> str | None:
    """Upload mask PNG to fal.ai CDN and return URL (for inpainting call)."""
    try:
        return _upload_image_to_fal(mask_bytes, "image/png")
    except Exception:
        return None
