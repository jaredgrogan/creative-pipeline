"""
MODULE: format_renderer
WHAT: Adapts a square hero image to each configured aspect ratio and overlays the
campaign message as text.
DECISION: One hero image adapted to three formats ensures visual consistency across
surfaces. Render mode is configurable via config.RENDER_MODE:
  fit_blur   -- hero fits inside frame, blurred hero fills background (default)
  fit_fill   -- hero fits inside frame, brand primary color fills background
  center_crop -- crop from center (risks losing product content at edges)
Default is fit_blur: preserves the complete product in every format, blurred fill
looks polished (same approach Instagram uses for mismatched ratios). Bottom-third
text placement is the safe default for social ad legibility across all ratios.
PRODUCTION ALTERNATIVE: Adobe Firefly Generative Fill to extend the background
naturally. Vision-model subject detection to inform crop anchor point. Per-format
text sizing computed from character count and safe-zone analysis.
"""

import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from config import (
    ASPECT_RATIOS, RENDER_MODE,
    FONT_SIZE_DEFAULT, FONT_SIZE_MIN,
    TEXT_FILL, TEXT_SHADOW_FILL, TEXT_SHADOW_OFFSET,
    TEXT_MARGIN_RATIO, TEXT_VERTICAL_POSITION,
    get_font_path,
)


def render_formats(hero_path, product, brief):
    """
    Adapt hero image to all configured aspect ratios and overlay campaign message.
    Accepts the full brief dict so it can access campaign_message, language, and brand.

    Optional brief fields:
      text_color  -- "white" (default) or "black"
      font_style  -- "sans" (default), "serif", or "mono"
      font_bold   -- True (default) or False
      font_italic -- False (default) or True
      font_underline -- False (default) or True
      font_size   -- integer, defaults to FONT_SIZE_DEFAULT

    Returns list of (PIL.Image, format_name) tuples.
    """
    hero = Image.open(str(hero_path)).convert("RGB")
    campaign_message = brief["campaign_message"]
    language = brief.get("language", "en")
    brand = brief.get("brand", {})

    font_style = brief.get("font_style", "sans")
    font_bold = brief.get("font_bold", True)
    font_italic = brief.get("font_italic", False)
    font_underline = brief.get("font_underline", False)
    font_size = brief.get("font_size", FONT_SIZE_DEFAULT)
    text_color = brief.get("text_color", "white")
    font_path = get_font_path(style=font_style, bold=font_bold, italic=font_italic)

    message = _maybe_translate(campaign_message, language)

    results = []
    for ratio in ASPECT_RATIOS:
        target_w = ratio["width"]
        target_h = ratio["height"]

        canvas = _apply_render_mode(hero, target_w, target_h, brand)
        canvas = _overlay_text(
            canvas, message, font_path,
            text_color=text_color,
            underline=font_underline,
            font_size_override=font_size,
        )
        results.append((canvas, ratio["name"]))

    return results


# ---------------------------------------------------------------------------
# Render mode strategies
# ---------------------------------------------------------------------------

def _apply_render_mode(hero, target_w, target_h, brand):
    """Dispatch to the configured render strategy."""
    if RENDER_MODE == "fit_fill":
        colors = brand.get("colors", [])
        color = _parse_hex_color(colors[0]) if colors else (26, 26, 46)
        return _fit_fill(hero, target_w, target_h, color)
    if RENDER_MODE == "center_crop":
        return _center_crop(hero, target_w, target_h)
    return _fit_blur(hero, target_w, target_h)


def _fit_blur(hero, target_w, target_h):
    """
    Scale hero to fit within the frame. Fill the remaining space with a blurred,
    cover-scaled version of the same image. No letterbox bars, full product visible.
    """
    # Background: scale to cover target dimensions, then blur
    scale = max(target_w / hero.width, target_h / hero.height)
    bg_w = int(hero.width * scale)
    bg_h = int(hero.height * scale)
    bg = hero.resize((bg_w, bg_h), Image.LANCZOS)
    left = (bg_w - target_w) // 2
    top = (bg_h - target_h) // 2
    bg = bg.crop((left, top, left + target_w, top + target_h))
    bg = bg.filter(ImageFilter.GaussianBlur(radius=20))

    # Foreground: scale to fit (contain), preserving all content
    fg = hero.copy()
    fg.thumbnail((target_w, target_h), Image.LANCZOS)

    # Paste centered on blurred background
    paste_x = (target_w - fg.width) // 2
    paste_y = (target_h - fg.height) // 2
    canvas = bg.copy()
    canvas.paste(fg, (paste_x, paste_y))
    return canvas


def _fit_fill(hero, target_w, target_h, brand_color):
    """
    Scale hero to fit within the frame. Fill remaining space with the brand
    primary color. Clean, on-brand, avoids arbitrary background content.
    """
    canvas = Image.new("RGB", (target_w, target_h), brand_color)
    fg = hero.copy()
    fg.thumbnail((target_w, target_h), Image.LANCZOS)
    paste_x = (target_w - fg.width) // 2
    paste_y = (target_h - fg.height) // 2
    canvas.paste(fg, (paste_x, paste_y))
    return canvas


def _center_crop(hero, target_w, target_h):
    """
    Crop from the center of the hero to match the target aspect ratio, then scale.
    NOTE: For 9:16 from a 1:1 source this loses ~44% of the width. Use only when
    the subject is known to be centered and the crop loss is acceptable.
    """
    src_w, src_h = hero.size
    target_ratio = target_w / target_h
    src_ratio = src_w / src_h

    if src_ratio > target_ratio:
        # Source is wider -- crop left and right
        crop_h = src_h
        crop_w = int(src_h * target_ratio)
    else:
        # Source is taller -- crop top and bottom
        crop_w = src_w
        crop_h = int(src_w / target_ratio)

    left = (src_w - crop_w) // 2
    top = (src_h - crop_h) // 2
    cropped = hero.crop((left, top, left + crop_w, top + crop_h))
    return cropped.resize((target_w, target_h), Image.LANCZOS)


# ---------------------------------------------------------------------------
# Text overlay
# ---------------------------------------------------------------------------

def _draw_scrim(image, scrim_top):
    """
    Draw a dark gradient scrim from scrim_top to the bottom of the image.
    Transparent at scrim_top, ~65% opaque black at the bottom edge.
    Guarantees text legibility regardless of the generated image content.
    """
    img_w, img_h = image.size
    scrim_h = img_h - scrim_top
    overlay = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for y in range(scrim_h):
        alpha = int(170 * (y / scrim_h))
        draw.line([(0, scrim_top + y), (img_w - 1, scrim_top + y)], fill=(0, 0, 0, alpha))
    return Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")


def _overlay_text(image, message, font_path, text_color="white", underline=False, font_size_override=None):
    """
    Overlay campaign message at bottom-third position.
    text_color: "white" (default) or "black". Shadow is always the opposite color.
    underline: draw a line beneath each text line.
    font_size_override: starting font size (falls back to FONT_SIZE_DEFAULT).
    Wraps long messages across multiple lines. Font size scales down to FONT_SIZE_MIN.
    """
    draw = ImageDraw.Draw(image)
    img_w, img_h = image.size
    margin = int(img_w * TEXT_MARGIN_RATIO)
    max_text_w = img_w - 2 * margin

    fill = TEXT_FILL if text_color == "white" else (0, 0, 0)
    shadow = TEXT_SHADOW_FILL if text_color == "white" else (255, 255, 255)

    font_size = int(font_size_override) if font_size_override else FONT_SIZE_DEFAULT
    font_size = max(font_size, FONT_SIZE_MIN)
    font = _load_font(font_path, font_size)
    while font_size > FONT_SIZE_MIN:
        test_bbox = draw.textbbox((0, 0), message, font=font)
        if (test_bbox[2] - test_bbox[0]) <= max_text_w:
            break
        font_size -= 4
        font = _load_font(font_path, font_size)

    lines = _wrap_text(draw, message, font, max_text_w)
    line_h = _get_line_height(draw, font)
    total_h = line_h * len(lines)

    start_y = int(img_h * TEXT_VERTICAL_POSITION) - total_h // 2
    scrim_top = max(0, start_y - int(img_h * 0.06))
    image = _draw_scrim(image, scrim_top)
    draw = ImageDraw.Draw(image)

    sx, sy = TEXT_SHADOW_OFFSET
    ul_thickness = max(2, font_size // 26)

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = (img_w - text_w) // 2
        y = start_y + i * line_h
        draw.text((x + sx, y + sy), line, font=font, fill=shadow)
        draw.text((x, y), line, font=font, fill=fill)
        if underline:
            ul_y = y + text_h + 3
            draw.line([(x + sx, ul_y + sy), (x + text_w + sx, ul_y + sy)], fill=shadow, width=ul_thickness)
            draw.line([(x, ul_y), (x + text_w, ul_y)], fill=fill, width=ul_thickness)

    return image


def _wrap_text(draw, text, font, max_width):
    """Break text into lines that fit within max_width pixels."""
    words = text.split()
    lines = []
    current = []
    for word in words:
        test = " ".join(current + [word])
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines if lines else [text]


def _get_line_height(draw, font):
    """Return line height in pixels including a small leading gap."""
    bbox = draw.textbbox((0, 0), "Ag", font=font)
    return int((bbox[3] - bbox[1]) * 1.25)


def _load_font(font_path, size):
    """Load TTF font at size. Falls back to Pillow default if no font file found."""
    if font_path and Path(font_path).exists():
        return ImageFont.truetype(str(font_path), size)
    return ImageFont.load_default()


def _parse_hex_color(hex_str):
    """Convert '#RRGGBB' to an (R, G, B) tuple for Pillow."""
    hex_str = hex_str.lstrip("#")
    return tuple(int(hex_str[i:i + 2], 16) for i in (0, 2, 4))


# ---------------------------------------------------------------------------
# Optional localization
# ---------------------------------------------------------------------------

def _maybe_translate(message, language):
    """
    Translate campaign_message if language is not English.
    Uses gpt-4o-mini -- cheap, fast, sufficient for short ad copy.
    Falls back silently to the original message on any error.
    """
    if language == "en":
        return message
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Translate the following marketing headline to language code '{lang}'. "
                        "Return only the translated text, no explanation or punctuation changes."
                    ).format(lang=language),
                },
                {"role": "user", "content": message},
            ],
            temperature=0.1,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return message
