"""
MODULE: asset_resolver
WHAT: Checks whether an existing asset is available for a product before calling
the image generation API.
DECISION: Cache-first pattern. Generating the same product image on every run is
wasteful and produces inconsistent results. Reuse is the correct default at scale.
The resolver checks two locations: the explicit asset_path from the brief, then a
convention-based path (assets/{product_id}.png) as a fallback.
PRODUCTION ALTERNATIVE: Query a DAM system (Adobe AEM, S3-backed store) by product
ID and campaign context hash. Return a CDN URL rather than a local path. Asset
freshness is validated against a TTL, not just file existence.
"""

from pathlib import Path
from config import ASSETS_DIR

IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".webp"]


def resolve(product):
    """
    Check for an existing asset for the given product.

    Resolution order:
      1. product["asset_path"] -- explicit path from the brief
      2. assets/{product_id}.{ext} -- convention-based fallback

    Returns:
      (path_str, "reused")  if an asset was found
      (None,     "generate") if no asset exists
    """
    # 1. Explicit path from brief
    explicit = product.get("asset_path")
    if explicit:
        p = Path(explicit)
        if p.exists():
            return str(p), "reused"

    # 2. Convention-based lookup in assets/
    product_id = product["id"]
    for ext in IMAGE_EXTENSIONS:
        candidate = ASSETS_DIR / (product_id + ext)
        if candidate.exists():
            return str(candidate), "reused"

    return None, "generate"
