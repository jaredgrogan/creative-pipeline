"""
MODULE: brief_parser
WHAT: Loads and validates a campaign brief from a JSON file. Returns a structured
dict that all downstream modules consume.
DECISION: Validation happens at ingestion — fail fast with a clear error before
any API calls are made or money is spent. Required fields are checked explicitly
so errors name the missing field, not a generic KeyError.
PRODUCTION ALTERNATIVE: Brief arrives as a validated payload from a DAM system
or campaign management platform (Workfront, Airtable) via webhook or API call.
Schema validation would use JSON Schema or Pydantic rather than manual checks.
"""

import json
from pathlib import Path


REQUIRED_TOP_LEVEL = ["campaign_id", "region", "language", "target_audience",
                       "campaign_message", "brand", "products"]
REQUIRED_PRODUCT = ["id", "name", "description"]
REQUIRED_BRAND = ["name"]


def load_brief(path):
    """
    Load and validate a campaign brief JSON file.
    Returns a validated dict on success.
    Raises ValueError with a descriptive message on any validation failure.
    Raises FileNotFoundError if the path does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError("Brief file not found: {}".format(path))

    with open(path, "r", encoding="utf-8") as f:
        try:
            brief = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError("Brief file is not valid JSON: {}".format(e))

    _validate_brief(brief)
    return brief


def _validate_brief(brief):
    """Raise ValueError if any required field is missing or invalid."""
    for field in REQUIRED_TOP_LEVEL:
        if field not in brief or brief[field] is None:
            raise ValueError("Brief is missing required field: '{}'".format(field))

    # Brand validation
    brand = brief["brand"]
    if not isinstance(brand, dict):
        raise ValueError("'brand' must be an object, got: {}".format(type(brand).__name__))
    for field in REQUIRED_BRAND:
        if field not in brand or not brand[field]:
            raise ValueError("Brief brand is missing required field: '{}'".format(field))

    # Products validation
    products = brief["products"]
    if not isinstance(products, list):
        raise ValueError("'products' must be a list, got: {}".format(type(products).__name__))
    if len(products) < 2:
        raise ValueError(
            "Brief must contain at least 2 products, found: {}".format(len(products))
        )
    for i, product in enumerate(products):
        if not isinstance(product, dict):
            raise ValueError("products[{}] must be an object".format(i))
        for field in REQUIRED_PRODUCT:
            if field not in product or not product[field]:
                raise ValueError(
                    "products[{}] is missing required field: '{}'".format(i, field)
                )

    # Soft defaults for optional fields
    brief.setdefault("language", "en")
    brand.setdefault("colors", [])
    brand.setdefault("logo_path", None)
    for product in products:
        product.setdefault("asset_path", None)


def brief_summary(brief):
    """Return a short human-readable summary string for logging."""
    product_names = [p["name"] for p in brief["products"]]
    return "[{}] {} | {} products: {} | message: '{}'".format(
        brief["campaign_id"],
        brief["region"],
        len(product_names),
        ", ".join(product_names),
        brief["campaign_message"],
    )
