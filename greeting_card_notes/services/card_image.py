"""
Render a downloadable greeting-card PNG from note text + theme.
"""

import io
import os
import textwrap
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Cache downloaded fonts inside the app folder
FONT_CACHE_DIR = Path(__file__).resolve().parent.parent / ".font_cache"

FONT_URLS = {
    "Warm Cursive": "https://github.com/google/fonts/raw/main/ofl/caveat/Caveat%5Bwght%5D.ttf",
    "Elegant Serif": "https://github.com/google/fonts/raw/main/ofl/lora/Lora%5Bwght%5D.ttf",
    "Modern Sans": "https://github.com/google/fonts/raw/main/ofl/inter/Inter%5Bopsz%2Cwght%5D.ttf",
}

# Static single-weight fallbacks if variable fonts fail
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
        # Start with character-ish wrap, then tighten by measured width
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
    :return: PNG bytes.
    """
    bg = hex_to_rgb(theme["bg"])
    text_color = hex_to_rgb(theme["color"])
    border = hex_to_rgb(theme["border"])
    accent = hex_to_rgb(theme["accent"])

    image = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(image)

    # Outer border
    margin = 48
    draw.rounded_rectangle(
        [margin, margin, width - margin, height - margin],
        radius=36,
        outline=border,
        width=4,
    )

    # Inner dashed-style rectangle (approximate with solid lighter border)
    inner = margin + 36
    draw.rounded_rectangle(
        [inner, inner, width - inner, height - inner],
        radius=24,
        outline=border,
        width=2,
    )

    # Soft dotted texture
    dot = tuple(min(255, c + 12) if sum(bg) > 400 else max(0, c + 18) for c in bg)
    for y in range(inner + 20, height - inner - 20, 18):
        for x in range(inner + 20, width - inner - 20, 22):
            draw.ellipse([x, y, x + 2, y + 2], fill=dot)

    body_size = FONT_SIZES.get(font_name, 30)
    body_font = _load_font(font_name, body_size)
    footer_font = _load_font("Elegant Serif", 18)

    text_area_width = width - (inner + 50) * 2
    lines = _wrap_text(draw, note_text.strip(), body_font, text_area_width)

    line_height = int(body_size * 1.45)
    text_block_height = len(lines) * line_height
    max_text_bottom = height - inner - 90
    start_y = inner + 70

    # If text is too tall, shrink font once
    if start_y + text_block_height > max_text_bottom:
        body_size = max(22, body_size - 8)
        body_font = _load_font(font_name, body_size)
        line_height = int(body_size * 1.45)
        lines = _wrap_text(draw, note_text.strip(), body_font, text_area_width)
        text_block_height = len(lines) * line_height

    y = start_y
    x = inner + 50
    for line in lines:
        if y + line_height > max_text_bottom:
            break
        draw.text((x, y), line, font=body_font, fill=text_color)
        y += line_height

    footer = "CRAFTED WITH CARE"
    footer_bbox = draw.textbbox((0, 0), footer, font=footer_font)
    footer_w = footer_bbox[2] - footer_bbox[0]
    draw.text(
        (width - inner - 50 - footer_w, height - inner - 55),
        footer,
        font=footer_font,
        fill=accent,
    )

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def note_as_text_bytes(note_text):
    """
    Encode the note as UTF-8 text bytes for download.

    :param note_text: The copy-ready note text.
    :return: UTF-8 encoded bytes.
    """
    return (note_text or "").encode("utf-8")
