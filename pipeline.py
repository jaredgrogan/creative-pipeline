"""
MODULE: pipeline
WHAT: Core orchestration logic shared by both the CLI (main.py) and the Streamlit UI
(app.py). Accepts a brief dict and an optional progress callback, runs all pipeline
stages, returns a results dict.
DECISION: Separating orchestration from interface means the pipeline logic is tested
and maintained in one place. Both interfaces are thin wrappers.
PRODUCTION ALTERNATIVE: Each stage becomes an async task in a job queue (Celery,
AWS Step Functions). The pipeline becomes a workflow definition, not a function call.
"""

import os
import time

from brief_parser import brief_summary
from legal_checker import check_message, format_result
from asset_resolver import resolve
from generators import get_generator, build_prompt
from format_renderer import render_formats
from output_writer import save_outputs, output_summary
from brand_checker import check_compliance, compliance_summary
from logger import get_logger, reset_logger, write_summary
from report_generator import generate_report
from campaign_store import save_campaign


def run_pipeline(brief, progress_callback=None, nl_parse_used=False):
    """
    Run the full pipeline for a given brief.

    progress_callback(stage, message) is called at each stage if provided.
    nl_parse_used -- True if the brief was produced by the NL parser (affects cost estimate).

    Returns dict:
      success             -- bool
      products_processed  -- int
      outputs_by_product  -- dict of {product_id: [Path, ...]}
      compliance_by_product -- dict of {product_id: compliance result dict}
      run_summary         -- dict matching logger.write_summary stats
      report_path         -- Path or None
      errors              -- list of error strings
    """
    reset_logger()
    logger = get_logger()
    start_time = time.time()

    def _progress(stage, message):
        logger.info("[{}] {}".format(stage, message))
        if progress_callback:
            progress_callback(stage, message)

    # ------------------------------------------------------------------
    # Environment check
    # ------------------------------------------------------------------
    provider = os.getenv("IMAGE_PROVIDER", "flux")
    _progress("INIT", "Checking environment")
    errors = _check_env(provider)
    if errors:
        for err in errors:
            logger.error(err)
        return {
            "success": False,
            "products_processed": 0,
            "outputs_by_product": {},
            "compliance_by_product": {},
            "run_summary": {},
            "report_path": None,
            "errors": errors,
        }

    # ------------------------------------------------------------------
    # Brief summary
    # ------------------------------------------------------------------
    _progress("BRIEF", brief_summary(brief))

    campaign_id = brief.get("campaign_id", "unknown")
    products = brief.get("products", [])
    brand = brief.get("brand", {})

    # ------------------------------------------------------------------
    # Legal check on campaign message
    # ------------------------------------------------------------------
    campaign_message = brief.get("message", "")
    if campaign_message:
        legal_result = check_message(campaign_message)
        _progress("LEGAL", format_result(legal_result))
        if not legal_result["passed"]:
            logger.warning("Legal check failed -- pipeline continuing but review required")

    # ------------------------------------------------------------------
    # Per-product loop
    # ------------------------------------------------------------------
    generator = get_generator()
    outputs_by_product = {}
    compliance_by_product = {}
    generated_count = 0
    reused_count = 0
    error_count = 0

    for product in products:
        product_id = product.get("id", "unknown")
        _progress("PRODUCT", "Processing: {}".format(product_id))

        # 1. Resolve asset
        _progress("RESOLVE", "Resolving asset for {}".format(product_id))
        hero_path, asset_status = resolve(product)

        if asset_status == "reused":
            _progress("RESOLVE", "Reusing existing asset: {}".format(hero_path))
            reused_count += 1
        else:
            # 2. Generate image
            _progress("GENERATE", "Generating hero image via {} for {}".format(provider, product_id))
            try:
                prompt = build_prompt(product, brief)
                _progress("PROMPT", prompt)
                logger.debug("Prompt: {}".format(prompt))
                hero_path = generator.generate(prompt, product_id)
                _progress("GENERATE", "Image saved: {}".format(hero_path))
                generated_count += 1
            except Exception as exc:
                logger.error("Image generation failed for {}: {}".format(product_id, exc))
                error_count += 1
                continue

        # 3. Render formats
        _progress("RENDER", "Rendering formats for {}".format(product_id))
        try:
            rendered = render_formats(hero_path, product, brief)
        except Exception as exc:
            logger.error("Render failed for {}: {}".format(product_id, exc))
            error_count += 1
            continue

        # 4. Save outputs
        _progress("SAVE", "Saving output files for {}".format(product_id))
        saved_paths = save_outputs(rendered, product_id)
        outputs_by_product[product_id] = saved_paths

        # 5. Brand compliance check
        _progress("COMPLIANCE", "Checking brand compliance for {}".format(product_id))
        product_compliance = {}
        for image_path in saved_paths:
            try:
                result = check_compliance(image_path, brand)
                product_compliance[str(image_path)] = result
                _progress("COMPLIANCE", "{} -- {}".format(
                    image_path.name, compliance_summary(result)
                ))
            except Exception as exc:
                logger.warning("Compliance check failed for {}: {}".format(image_path, exc))
        compliance_by_product[product_id] = product_compliance

    # ------------------------------------------------------------------
    # Finalize
    # ------------------------------------------------------------------
    duration = time.time() - start_time

    run_summary = {
        "campaign_id": campaign_id,
        "products_total": len(products),
        "generated": generated_count,
        "reused": reused_count,
        "errors": error_count,
        "provider": provider,
        "nl_parse_used": nl_parse_used,
        "duration_s": duration,
        "cost_estimate": _estimate_cost(provider, generated_count, nl_parse_used),
    }

    _progress("SUMMARY", "Run complete: {} generated, {} reused, {} errors".format(
        generated_count, reused_count, error_count
    ))
    write_summary(run_summary)

    # Generate HTML report
    report_path = None
    if outputs_by_product:
        _progress("REPORT", "Generating HTML report")
        try:
            report_path = generate_report(outputs_by_product, run_summary)
            _progress("REPORT", "Report saved: {}".format(report_path))
        except Exception as exc:
            logger.error("Report generation failed: {}".format(exc))
            error_count += 1

    # Persist campaign
    try:
        save_campaign(brief, run_summary)
    except Exception as exc:
        logger.warning("Campaign save failed: {}".format(exc))

    success = error_count == 0 and bool(outputs_by_product)

    return {
        "success": success,
        "products_processed": len(outputs_by_product),
        "outputs_by_product": outputs_by_product,
        "compliance_by_product": compliance_by_product,
        "run_summary": run_summary,
        "report_path": report_path,
        "errors": [],
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_env(provider):
    """Return list of error strings for missing env vars. Empty list = OK."""
    missing = []
    if provider == "flux":
        if not os.getenv("BFL_API_KEY"):
            missing.append("BFL_API_KEY not set in environment")
    else:
        if not os.getenv("OPENAI_API_KEY"):
            missing.append("OPENAI_API_KEY not set in environment")
    return missing


def _estimate_cost(provider, generated, nl_parse_used):
    cost_per_image = 0.05 if provider == "flux" else 0.04
    cost = generated * cost_per_image
    if nl_parse_used:
        cost += 0.01
    return cost
