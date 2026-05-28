"""
MODULE: logger
WHAT: Structured run logger that records every pipeline event to a log file and
writes a run summary with API cost estimates at the end of each pipeline run.
DECISION: Every event is timestamped and labelled by stage. The summary includes
estimated API cost, mapping directly to the success metric of optimizing marketing
ROI. A single module-level logger is initialized once and reused -- no duplicate
handlers across imports.
PRODUCTION ALTERNATIVE: Structured JSON logging emitted to a centralized
observability platform (Datadog, Splunk, CloudWatch Logs). Cost data is tagged
with campaign_id and product_id for per-campaign spend dashboards. Alerts trigger
when a run exceeds a cost threshold.
"""

import logging
from datetime import datetime
from config import LOG_FILE

# Cost estimates per API call (USD)
COST_PER_FLUX_IMAGE = 0.05
COST_PER_OPENAI_IMAGE = 0.042
COST_PER_GPT4O_CALL = 0.01

_logger = None


def get_logger():
    """
    Return the configured logger instance. Creates it on first call.
    Writes to both campaign_run.log and stdout so terminal output mirrors the log.
    """
    global _logger
    if _logger is not None:
        return _logger

    logger = logging.getLogger("creative_pipeline")
    logger.setLevel(logging.DEBUG)

    # Prevent duplicate handlers if module is reloaded
    if logger.handlers:
        logger.handlers.clear()

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler
    file_handler = logging.FileHandler(str(LOG_FILE), encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler -- same format so terminal output mirrors the log
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    _logger = logger
    return _logger


def reset_logger():
    """Close and reset the logger. Used between runs in Streamlit to avoid handler accumulation."""
    global _logger
    if _logger is not None:
        for handler in _logger.handlers[:]:
            handler.close()
            _logger.removeHandler(handler)
        _logger = None


def write_summary(stats):
    """
    Write a structured run summary block to the log.

    stats dict keys:
      campaign_id     -- str
      products_total  -- int
      generated       -- int  (hero images generated via API)
      reused          -- int  (existing assets reused)
      errors          -- int
      provider        -- str  (flux or gpt-image-1)
      nl_parse_used   -- bool
      duration_s      -- float (total pipeline runtime in seconds)
    """
    logger = get_logger()
    cost = _estimate_cost(stats)

    lines = [
        "",
        "=" * 60,
        "PIPELINE RUN SUMMARY",
        "=" * 60,
        "Campaign    : {}".format(stats.get("campaign_id", "unknown")),
        "Products    : {}".format(stats.get("products_total", 0)),
        "Generated   : {} images ({})".format(
            stats.get("generated", 0), stats.get("provider", "unknown")
        ),
        "Reused      : {} images".format(stats.get("reused", 0)),
        "Errors      : {}".format(stats.get("errors", 0)),
        "Duration    : {:.1f}s".format(stats.get("duration_s", 0)),
        "Est. Cost   : ${:.4f}".format(cost),
        "=" * 60,
        "",
    ]

    for line in lines:
        logger.info(line)


def _estimate_cost(stats):
    """Calculate estimated API spend for this run."""
    provider = stats.get("provider", "flux")
    generated = stats.get("generated", 0)
    nl_parse = stats.get("nl_parse_used", False)

    cost_per_image = COST_PER_FLUX_IMAGE if provider == "flux" else COST_PER_OPENAI_IMAGE
    cost = generated * cost_per_image
    if nl_parse:
        cost += COST_PER_GPT4O_CALL
    return cost
