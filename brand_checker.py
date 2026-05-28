"""
MODULE: brand_checker
WHAT: Checks generated creatives for brand compliance -- logo presence via template
matching and dominant color alignment against the brand palette.
DECISION: Bonus feature that maps directly to pain point #2 (inconsistent quality
and messaging). Implemented entirely with Pillow to avoid adding a vision model
API dependency. Template matching is pixel-level: it finds the logo if it appears
in the image at close-to-original scale. Color check extracts the N most dominant
colors and tests whether any fall within tolerance of the brand palette.
PRODUCTION ALTERNATIVE: A dedicated vision model (GPT-4o Vision, Gemini Vision)
for semantic brand compliance -- detecting not just logo presence but correct usage,
clear space violations, off-brand imagery, and tone mismatches. A full brand
compliance platform (Frontify, Bynder) integrates these checks into approval flows.
"""

from pathlib import Path
from PIL import Image
import colorsys

DEFAULT_COLOR_TOLERANCE = 40   # Euclidean RGB distance threshold
DOMINANT_COLOR_SAMPLE = 8      # Number of dominant colors to extract


def check_compliance(image_path, brand):
    """
    Check a saved creative for brand compliance.

    Args:
        image_path: path to the saved PNG (str or Path)
        brand: brand dict from the brief (name, logo_path, colors)

    Returns:
        dict with keys:
          logo_present     -- bool or None if no logo_path provided
          color_compliant  -- bool or None if no brand colors provided
          dominant_colors  -- list of '#RRGGBB' hex strings
          notes            -- list of human-readable compliance notes
    """
    result = {
        "logo_present": None,
        "color_compliant": None,
        "dominant_colors": [],
        "notes": [],
    }

    image = Image.open(str(image_path)).convert("RGB")
    dominant = _extract_dominant_colors(image, DOMINANT_COLOR_SAMPLE)
    result["dominant_colors"] = [_rgb_to_hex(c) for c in dominant]

    # Logo check
    logo_path = brand.get("logo_path")
    if logo_path and Path(logo_path).exists():
        result["logo_present"] = _check_logo_presence(image, logo_path)
        if not result["logo_present"]:
            result["notes"].append("Logo not detected in creative.")
    else:
        result["notes"].append("No logo_path provided -- logo check skipped.")

    # Color check
    brand_colors = brand.get("colors", [])
    if brand_colors:
        palette = [_hex_to_rgb(c) for c in brand_colors]
        result["color_compliant"] = _check_color_compliance(dominant, palette)
        if not result["color_compliant"]:
            result["notes"].append(
                "No dominant color within tolerance of brand palette."
            )
    else:
        result["notes"].append("No brand colors provided -- color check skipped.")

    return result


# ---------------------------------------------------------------------------
# Logo presence
# ---------------------------------------------------------------------------

def _check_logo_presence(image, logo_path, threshold=0.85):
    """
    Slide a scaled logo over the image and check for a close pixel match.
    Returns True if a region with similarity >= threshold is found.
    This is a lightweight alternative to OpenCV template matching.
    """
    try:
        logo = Image.open(str(logo_path)).convert("RGB")

        # Resize logo to at most 25% of image dimensions for realistic scale
        max_logo_w = image.width // 4
        max_logo_h = image.height // 4
        logo.thumbnail((max_logo_w, max_logo_h), Image.LANCZOS)

        logo_w, logo_h = logo.size
        img_w, img_h = image.size

        if logo_w > img_w or logo_h > img_h:
            return False

        logo_pixels = list(logo.getdata())

        # Sample positions across the image (stride to keep it fast)
        stride = max(logo_w // 2, 10)
        for y in range(0, img_h - logo_h, stride):
            for x in range(0, img_w - logo_w, stride):
                region = image.crop((x, y, x + logo_w, y + logo_h))
                similarity = _pixel_similarity(list(region.getdata()), logo_pixels)
                if similarity >= threshold:
                    return True
        return False

    except Exception:
        return False


def _pixel_similarity(pixels_a, pixels_b):
    """
    Compute normalized similarity between two equal-length pixel lists.
    Returns 0.0 (no match) to 1.0 (identical).
    """
    if len(pixels_a) != len(pixels_b) or not pixels_a:
        return 0.0
    total_diff = 0
    for (r1, g1, b1), (r2, g2, b2) in zip(pixels_a, pixels_b):
        total_diff += abs(r1 - r2) + abs(g1 - g2) + abs(b1 - b2)
    max_diff = len(pixels_a) * 3 * 255
    return 1.0 - (total_diff / max_diff)


# ---------------------------------------------------------------------------
# Color compliance
# ---------------------------------------------------------------------------

def _extract_dominant_colors(image, n):
    """
    Extract the N most dominant colors by quantizing the image to n colors.
    Returns list of (R, G, B) tuples.
    """
    # Resize for speed -- color distribution is stable at small sizes
    small = image.resize((100, 100), Image.LANCZOS)
    quantized = small.quantize(colors=n, method=Image.Quantize.MEDIANCUT)
    palette_data = quantized.getpalette()[:n * 3]
    colors = []
    for i in range(n):
        r = palette_data[i * 3]
        g = palette_data[i * 3 + 1]
        b = palette_data[i * 3 + 2]
        colors.append((r, g, b))
    return colors


def _check_color_compliance(dominant_colors, brand_palette, tolerance=DEFAULT_COLOR_TOLERANCE):
    """
    Return True if at least one dominant color is within tolerance of any brand color.
    Tolerance is Euclidean RGB distance.
    """
    for dom in dominant_colors:
        for brand_color in brand_palette:
            if _color_distance(dom, brand_color) <= tolerance:
                return True
    return False


def _color_distance(c1, c2):
    """Euclidean distance between two (R, G, B) tuples."""
    return (
        (c1[0] - c2[0]) ** 2 +
        (c1[1] - c2[1]) ** 2 +
        (c1[2] - c2[2]) ** 2
    ) ** 0.5


# ---------------------------------------------------------------------------
# Color format helpers
# ---------------------------------------------------------------------------

def _hex_to_rgb(hex_str):
    """Convert '#RRGGBB' to (R, G, B) tuple."""
    hex_str = hex_str.lstrip("#")
    return tuple(int(hex_str[i:i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb):
    """Convert (R, G, B) tuple to '#RRGGBB' string."""
    return "#{:02X}{:02X}{:02X}".format(rgb[0], rgb[1], rgb[2])


def compliance_summary(result):
    """Return a one-line human-readable compliance summary for logging."""
    parts = []
    if result["logo_present"] is True:
        parts.append("logo: OK")
    elif result["logo_present"] is False:
        parts.append("logo: MISSING")
    else:
        parts.append("logo: skipped")

    if result["color_compliant"] is True:
        parts.append("colors: OK")
    elif result["color_compliant"] is False:
        parts.append("colors: NON-COMPLIANT")
    else:
        parts.append("colors: skipped")

    return " | ".join(parts)
