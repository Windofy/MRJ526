"""
watermark.py — "Windofy" text watermark for MRJ3.0
Renders bold black sans-serif text in the bottom-right corner.
No external PNG dependency — pure PIL text rendering.
"""
import os
import io
from PIL import Image, ImageDraw, ImageFont

# Configuration
WATERMARK_TEXT = "Windofy"
WATERMARK_SCALE = 0.03       # text height = 3% of image height (subtle)
WATERMARK_OPACITY = 153      # ~60% of 255
WATERMARK_MARGIN = 0.03      # 3% margin from edges
WATERMARK_COLOR = (26, 26, 26)  # #1A1A1A — dark black
LETTER_SPACING = -1          # tight letter spacing (pixels, applied per char)

# Try to load a bold TTF font for better rendering
_FONT_SEARCH_PATHS = [
    # Project local fonts
    os.path.join(os.path.dirname(__file__), "..", "static", "fonts", "font-poppins-700.ttf"),
    # Common system sans-serif bold fonts (Windows)
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/calibrib.ttf",
    # macOS / Linux
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def _get_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load the best available bold sans-serif font at the given pixel size."""
    for path in _FONT_SEARCH_PATHS:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    # Absolute fallback — PIL built-in bitmap font (small but functional)
    return ImageFont.load_default()


def _draw_text_with_spacing(
    draw: ImageDraw.ImageDraw,
    position: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: tuple,
    spacing: int = 0,
) -> int:
    """Draw text character by character with custom letter spacing. Returns total width."""
    x, y = position
    total_w = 0
    for i, char in enumerate(text):
        bbox = draw.textbbox((0, 0), char, font=font)
        char_w = bbox[2] - bbox[0]
        draw.text((x + total_w, y), char, font=font, fill=fill)
        total_w += char_w + (spacing if i < len(text) - 1 else 0)
    return total_w


def apply_watermark(image_bytes: bytes) -> bytes:
    """
    Overlay "Windofy" text watermark onto the image.
    Position: bottom-right corner, subtle but clearly visible.
    Returns watermarked image as PNG bytes.
    """
    base = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    bw, bh = base.size

    # Calculate font size relative to image
    font_size = max(int(bh * WATERMARK_SCALE), 14)  # minimum 14px
    font = _get_font(font_size)

    # Create transparent overlay for the watermark text
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Measure text width with spacing
    total_text_w = 0
    for i, char in enumerate(WATERMARK_TEXT):
        bbox = draw.textbbox((0, 0), char, font=font)
        total_text_w += (bbox[2] - bbox[0]) + (LETTER_SPACING if i < len(WATERMARK_TEXT) - 1 else 0)

    # Get text height
    bbox_full = draw.textbbox((0, 0), WATERMARK_TEXT, font=font)
    text_h = bbox_full[3] - bbox_full[1]

    # Position: bottom-right with margin
    margin_x = int(bw * WATERMARK_MARGIN)
    margin_y = int(bh * WATERMARK_MARGIN)
    x = bw - total_text_w - margin_x
    y = bh - text_h - margin_y

    # Draw with custom letter spacing and semi-transparency
    fill = (*WATERMARK_COLOR, WATERMARK_OPACITY)
    _draw_text_with_spacing(draw, (x, y), WATERMARK_TEXT, font, fill, LETTER_SPACING)

    # Composite and export
    composite = Image.alpha_composite(base, overlay)

    buf = io.BytesIO()
    composite.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()
