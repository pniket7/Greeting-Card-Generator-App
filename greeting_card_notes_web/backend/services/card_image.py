"""
Render a downloadable greeting-card PNG from note text + theme.
"""

import io
import os
import textwrap
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Cache downloaded fonts inside the backend folder
FONT_CACHE_DIR = Path(__file__).resolve().parent.parent / ".font_cache"

FONT_URLS = {
    "Warm Cursive": "https://github.com/google/fonts/raw/main/ofl/caveat/Caveat%5Bwght%5D.ttf",
    "Elegant Serif": "https://github.com/google/fonts/raw/main/ofl/lora/Lora%5Bwght%5D.ttf",
    "Modern Sans": "https://github.com/google/fonts/raw/main/ofl/inter/Inter%5Bopsz%2Cwght%5D.ttf",
}

FONT_FALLBACK_URLS = {
    "Warm Cursive": "https://github.com/google/fonts/raw/main/ofl/caveat/Caveat-Regular.ttf",
    "Elegant Serif": "https://github.com/google/fonts/raw/main/ofl/lora/Lora-Regular.ttf",
    "Modern Sans": "https://github.com/google/fonts/raw/main/ofl/inter/Inter-Regular.ttf",
}

FONT_SIZES = {
    "Warm Cursive": 42,
    "Elegant Serif": 30,
    "Modern Sans": 28,
}


def hex_to_rgb(hex_color):
    """
    Convert a hex color string to an RGB tuple.

    :param hex_color: Hex color like #fdfbf7.
    :return: RGB tuple.
    """
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def _ensure_font_file(font_name):
    """
    Download and cache a font file for the selected style.

    :param font_name: One of Warm Cursive / Elegant Serif / Modern Sans.
    :return: Path to a local TTF file, or None if unavailable.
    """
    FONT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = font_name.lower().replace(" ", "_")
    local_path = FONT_CACHE_DIR / f"{safe_name}.ttf"

    if local_path.exists() and local_path.stat().st_size > 1000:
        return str(local_path)

    urls = [
        FONT_FALLBACK_URLS.get(font_name),
        FONT_URLS.get(font_name),
    ]
    for url in urls:
        if not url:
            continue
        try:
            urllib.request.urlretrieve(url, local_path)
            if local_path.exists() and local_path.stat().st_size > 1000:
                return str(local_path)
        except Exception:
            continue
    return None


def _load_font(font_name, size):
    """
    Load a TrueType font, falling back to default if needed.

    :param font_name: Selected font style name.
    :param size: Font size in points.
    :return: PIL ImageFont instance.
    """
    font_path = _ensure_font_file(font_name)
    if font_path:
        try:
            return ImageFont.truetype(font_path, size=size)
        except Exception:
            pass

    # System fallbacks
    candidates = [
        "C:/Windows/Fonts/georgia.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Georgia.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                continue
    return ImageFont.load_default()


def _wrap_text(draw, text, font, max_width):
    """
    Wrap note text so it fits within the card width.

    :param draw: ImageDraw instance.
    :param text: Full note text.
    :param font: Font used for measuring.
    :param max_width: Max pixel width for a line.
    :return: List of wrapped lines.
    """
    lines = []
    for paragraph in text.splitlines() or [""]:
        if not paragraph.strip():
            lines.append("")
            continue
        rough = textwrap.wrap(paragraph, width=48) or [paragraph]
        for chunk in rough:
            words = chunk.split()
            current = ""
            for word in words:
                test = (current + " " + word).strip()
                bbox = draw.textbbox((0, 0), test, font=font)
                if bbox[2] - bbox[0] <= max_width:
                    current = test
                else:
                    if current:
                        lines.append(current)
                    current = word
            if current:
                lines.append(current)
    return lines if lines else [""]


def render_card_png(note_text, theme, font_name="Elegant Serif", width=1080, height=1350):
    """
    Render the greeting card as a PNG image in memory.

    :param note_text: The copy-ready note text.
    :param theme: Theme dict with bg/color/border/accent keys.
    :param font_name: Selected font style name.
    :param width: Image width in pixels.
    :param height: Image height in pixels.
    :return: Bytes containing PNG data.
    """
    img = Image.new("RGB", (width, height), color=hex_to_rgb(theme["bg"]))
    draw = ImageDraw.Draw(img)

    margin = 80
    border_color = hex_to_rgb(theme["border"])
    draw.rectangle([margin, margin, width - margin, height - margin], outline=border_color, width=4)

    inner_margin = margin + 12
    draw.rectangle([inner_margin, inner_margin, width - inner_margin, height - inner_margin], outline=border_color, width=1)

    size = FONT_SIZES.get(font_name, 30)
    font = _load_font(font_name, size)

    text_max_width = width - (inner_margin * 2) - 80
    wrapped_lines = _wrap_text(draw, note_text, font, text_max_width)

    total_text_height = sum(
        draw.textbbox((0, 0), line if line.strip() else "X", font=font)[3] -
        draw.textbbox((0, 0), line if line.strip() else "X", font=font)[1] + 12
        for line in wrapped_lines
    )

    y = (height - total_text_height) // 2
    text_color = hex_to_rgb(theme["color"])

    for line in wrapped_lines:
        if line.strip():
            bbox = draw.textbbox((0, 0), line, font=font)
            line_w = bbox[2] - bbox[0]
            x = (width - line_w) // 2
            draw.text((x, y), line, font=font, fill=text_color)
            line_h = bbox[3] - bbox[1]
        else:
            line_h = size

        y += line_h + 12

    accent_font = _load_font("Modern Sans", 18)
    accent_text = "CRAFTED WITH CARE"
    accent_bbox = draw.textbbox((0, 0), accent_text, font=accent_font)
    accent_w = accent_bbox[2] - accent_bbox[0]
    draw.text(((width - accent_w) // 2, height - margin - 50), accent_text, font=accent_font, fill=hex_to_rgb(theme["accent"]))

    output = io.BytesIO()
    img.save(output, format="PNG")
    return output.getvalue()


def note_as_text_bytes(note_text):
    """
    Convert plain note text to raw utf-8 bytes.

    :param note_text: The note content.
    :return: Bytes.
    """
    return note_text.encode("utf-8")
