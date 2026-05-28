"""
MODULE: config
WHAT: Central configuration — all constants, paths, and provider settings live here.
DECISION: Nothing is hardcoded in logic modules. Every tunable value is one place.
PRODUCTION ALTERNATIVE: Environment-specific config files (dev/staging/prod) backed
by a secrets manager (AWS Secrets Manager, Azure Key Vault).
"""

import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).parent
ASSETS_DIR = BASE_DIR / "assets"
GENERATED_ASSETS_DIR = ASSETS_DIR / "generated"
OUTPUT_DIR = BASE_DIR / "outputs"
CAMPAIGNS_DIR = BASE_DIR / "campaigns"
LOG_FILE = BASE_DIR / "campaign_run.log"


def get_font_path(style="sans", bold=True, italic=False):
    """
    Resolve a usable TTF font path.
    style:  "sans" | "serif" | "mono"
    bold:   True (default) or False
    italic: True or False (default)
    Priority: bundled -> platform system font -> None (Pillow bitmap default).
    """
    if style == "serif":
        return _get_serif_font_path(bold=bold, italic=italic)
    if style == "mono":
        return _get_mono_font_path(bold=bold, italic=italic)
    return _get_sans_font_path(bold=bold, italic=italic)


def _get_sans_font_path(bold=True, italic=False):
    bundled = ASSETS_DIR / "fonts" / "Roboto-Bold.ttf"
    if bundled.exists() and not italic:
        return bundled

    if sys.platform == "win32":
        if bold and italic:
            candidates = [Path("C:/Windows/Fonts/arialbdi.ttf")]
        elif italic:
            candidates = [Path("C:/Windows/Fonts/ariali.ttf")]
        elif bold:
            candidates = [Path("C:/Windows/Fonts/arialbd.ttf"), Path("C:/Windows/Fonts/tahomabd.ttf")]
        else:
            candidates = [Path("C:/Windows/Fonts/arial.ttf"), Path("C:/Windows/Fonts/tahoma.ttf")]
    elif sys.platform == "darwin":
        candidates = [Path("/System/Library/Fonts/Helvetica.ttc")]
    else:
        if bold and italic:
            candidates = [Path("/usr/share/fonts/truetype/liberation/LiberationSans-BoldItalic.ttf")]
        elif italic:
            candidates = [Path("/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf"),
                          Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf")]
        elif bold:
            candidates = [Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
                          Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")]
        else:
            candidates = [Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
                          Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")]

    for path in candidates:
        if path.exists():
            return path
    return None


def _get_serif_font_path(bold=True, italic=False):
    if sys.platform == "win32":
        if bold and italic:
            candidates = [Path("C:/Windows/Fonts/timesbi.ttf"), Path("C:/Windows/Fonts/georgiaz.ttf")]
        elif italic:
            candidates = [Path("C:/Windows/Fonts/timesi.ttf"), Path("C:/Windows/Fonts/georgiai.ttf")]
        elif bold:
            candidates = [Path("C:/Windows/Fonts/timesbd.ttf"), Path("C:/Windows/Fonts/georgiab.ttf")]
        else:
            candidates = [Path("C:/Windows/Fonts/times.ttf"), Path("C:/Windows/Fonts/georgia.ttf")]
    elif sys.platform == "darwin":
        candidates = [
            Path("/Library/Fonts/Times New Roman Bold.ttf"),
            Path("/System/Library/Fonts/Times.ttc"),
        ]
    else:
        if bold and italic:
            candidates = [Path("/usr/share/fonts/truetype/liberation/LiberationSerif-BoldItalic.ttf")]
        elif italic:
            candidates = [Path("/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf"),
                          Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf")]
        elif bold:
            candidates = [Path("/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf"),
                          Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf")]
        else:
            candidates = [Path("/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf"),
                          Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf")]

    for path in candidates:
        if path.exists():
            return path
    return _get_sans_font_path(bold=bold, italic=italic)


def _get_mono_font_path(bold=True, italic=False):
    if sys.platform == "win32":
        if bold and italic:
            candidates = [Path("C:/Windows/Fonts/courbi.ttf")]
        elif italic:
            candidates = [Path("C:/Windows/Fonts/couri.ttf")]
        elif bold:
            candidates = [Path("C:/Windows/Fonts/consolab.ttf"), Path("C:/Windows/Fonts/courbd.ttf")]
        else:
            candidates = [Path("C:/Windows/Fonts/consola.ttf"), Path("C:/Windows/Fonts/cour.ttf")]
    elif sys.platform == "darwin":
        candidates = [
            Path("/Library/Fonts/Courier New Bold.ttf"),
            Path("/Library/Fonts/Courier New.ttf"),
        ]
    else:
        if bold and italic:
            candidates = [Path("/usr/share/fonts/truetype/liberation/LiberationMono-BoldItalic.ttf")]
        elif italic:
            candidates = [Path("/usr/share/fonts/truetype/liberation/LiberationMono-Italic.ttf"),
                          Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Oblique.ttf")]
        elif bold:
            candidates = [Path("/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf"),
                          Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf")]
        else:
            candidates = [Path("/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf"),
                          Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")]

    for path in candidates:
        if path.exists():
            return path
    return _get_sans_font_path(bold=bold, italic=italic)

# ---------------------------------------------------------------------------
# Aspect ratios
# ---------------------------------------------------------------------------

ASPECT_RATIOS = [
    {"name": "1x1",  "width": 1080, "height": 1080, "label": "Instagram Feed (1:1)"},
    {"name": "9x16", "width": 1080, "height": 1920, "label": "Stories / Reels (9:16)"},
    {"name": "16x9", "width": 1920, "height": 1080, "label": "Facebook / YouTube (16:9)"},
]

# ---------------------------------------------------------------------------
# Legal compliance
# ---------------------------------------------------------------------------

PROHIBITED_WORDS = [
    "guaranteed",
    "free",
    "miracle",
    "cure",
    "unlimited",
    "instant",
    "risk-free",
]

# ---------------------------------------------------------------------------
# Text overlay
# ---------------------------------------------------------------------------

FONT_SIZE_DEFAULT = 80
FONT_SIZE_MIN = 40
TEXT_FILL = (255, 255, 255)          # white
TEXT_SHADOW_FILL = (0, 0, 0)         # black drop shadow
TEXT_SHADOW_OFFSET = (3, 3)          # pixels
TEXT_MARGIN_RATIO = 0.05             # padding from edges as fraction of width
TEXT_VERTICAL_POSITION = 0.78        # fraction from top (bottom-third start)

# ---------------------------------------------------------------------------
# Image generation
# ---------------------------------------------------------------------------

# Provider selected via IMAGE_PROVIDER env var; falls back to flux
IMAGE_PROVIDER = os.getenv("IMAGE_PROVIDER", "flux")

# Flux (Black Forest Labs direct API)
BFL_API_BASE = "https://api.bfl.ai/v1"
BFL_MODEL = "flux-pro-1.1"
BFL_IMAGE_WIDTH = 1024
BFL_IMAGE_HEIGHT = 1024

# gpt-image-1 (OpenAI fallback)
OPENAI_IMAGE_MODEL = "gpt-image-1"
OPENAI_IMAGE_SIZE = "1024x1024"

# Retry
MAX_RETRY_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = [2, 4, 8]

# ---------------------------------------------------------------------------
# Render strategy
# ---------------------------------------------------------------------------

# How to adapt a square hero image to non-square aspect ratios.
# fit_blur   : fit hero within frame, fill remainder with blurred version of image (best visual quality)
# fit_fill   : fit hero within frame, fill remainder with primary brand color
# center_crop: crop from center to target ratio (loses content on edges)
RENDER_MODE = "fit_blur"

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

REPORT_FILENAME = "report.html"
REPORT_AUTO_OPEN = True
