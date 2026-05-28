"""
MODULE: output_writer
WHAT: Saves rendered images to an organized directory structure on disk.
DECISION: outputs/{product_id}/{format_name}.png -- organized by product then format.
This mirrors how a creative team or DAM system would expect to find assets: find
the product first, then choose the format. Using pathlib.Path throughout ensures
correct behavior on Windows, macOS, and Linux without manual separator handling.
PRODUCTION ALTERNATIVE: Upload directly to S3, Azure Blob Storage, or a DAM system
via their SDK. Return CDN URLs rather than local paths. Tag each asset with campaign
metadata (campaign_id, product_id, format, run timestamp) for DAM discoverability.
"""

from pathlib import Path
from config import OUTPUT_DIR


def save_outputs(rendered_images, product_id):
    """
    Save a list of (PIL.Image, format_name) tuples for one product.
    Creates outputs/{product_id}/ if it does not exist.
    Returns a list of saved file paths as pathlib.Path objects.
    """
    product_dir = OUTPUT_DIR / product_id
    product_dir.mkdir(parents=True, exist_ok=True)

    saved_paths = []
    for image, format_name in rendered_images:
        dest = product_dir / "{}.png".format(format_name)
        image.save(str(dest), "PNG")
        saved_paths.append(dest)

    return saved_paths


def output_summary(saved_paths_by_product):
    """
    Return a human-readable summary of saved outputs for logging.
    saved_paths_by_product: dict of {product_id: [Path, ...]}
    """
    lines = []
    total = 0
    for product_id, paths in saved_paths_by_product.items():
        lines.append("  {} -- {} files".format(product_id, len(paths)))
        total += len(paths)
    lines.append("  Total: {} creatives saved".format(total))
    return "\n".join(lines)
