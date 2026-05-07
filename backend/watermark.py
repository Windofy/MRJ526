"""
watermark.py — Resolution-aware PIL watermark for MRJ3.0
"""
import os
from PIL import Image
import io


WATERMARK_PATH = os.path.join(os.path.dirname(__file__), "..", "static", "watermark.png")
WATERMARK_SCALE = 0.18   # watermark width = 18% of image width
WATERMARK_OPACITY = 200  # 0–255
WATERMARK_MARGIN = 0.02  # 2% margin from edges


def apply_watermark(image_bytes: bytes) -> bytes:
    """
    Overlay the MRJ watermark onto image_bytes (PNG).
    Returns the watermarked image as PNG bytes.
    """
    base = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    bw, bh = base.size

    if not os.path.exists(WATERMARK_PATH):
        # No watermark asset yet — return original
        buf = io.BytesIO()
        base.convert("RGB").save(buf, format="PNG")
        return buf.getvalue()

    wm = Image.open(WATERMARK_PATH).convert("RGBA")

    # Scale watermark relative to base image
    target_w = int(bw * WATERMARK_SCALE)
    ratio = target_w / wm.width
    target_h = int(wm.height * ratio)
    wm = wm.resize((target_w, target_h), Image.LANCZOS)

    # Adjust opacity
    r, g, b, a = wm.split()
    a = a.point(lambda x: int(x * WATERMARK_OPACITY / 255))
    wm.putalpha(a)

    # Bottom-right position with margin
    margin_x = int(bw * WATERMARK_MARGIN)
    margin_y = int(bh * WATERMARK_MARGIN)
    pos = (bw - target_w - margin_x, bh - target_h - margin_y)

    composite = Image.new("RGBA", base.size)
    composite.paste(base, (0, 0))
    composite.paste(wm, pos, mask=wm)

    buf = io.BytesIO()
    composite.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()
