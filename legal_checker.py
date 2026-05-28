"""
MODULE: legal_checker
WHAT: Scans the campaign message for prohibited words before any API calls are made.
Uses word-boundary matching so 'free' flags 'get it free' but not 'freedom'.
DECISION: Fail fast -- do not spend API credits generating images for a brief that
compliance will reject. This is cost protection as much as it is correctness.
Running before all API calls means zero wasted spend on a non-compliant brief.
PRODUCTION ALTERNATIVE: Integration with a legal review queue. NLP-based semantic
compliance checker -- keyword matching misses context (a classifier catches intent).
Could also flag generated image alt-text and metadata, not just the message.
"""

import re
from config import PROHIBITED_WORDS


def check_message(message):
    """
    Scan campaign_message for prohibited words.
    Returns dict: {passed: bool, flagged_words: list}
    Matching is case-insensitive and word-boundary aware.
    """
    flagged = []
    message_lower = message.lower()

    for word in PROHIBITED_WORDS:
        pattern = r"\b" + re.escape(word.lower()) + r"\b"
        if re.search(pattern, message_lower):
            flagged.append(word)

    return {
        "passed": len(flagged) == 0,
        "flagged_words": flagged,
    }


def format_result(result):
    """Return a human-readable string of the legal check result for logging."""
    if result["passed"]:
        return "Legal check passed."
    return "Legal check FAILED -- prohibited words found: {}".format(
        ", ".join(result["flagged_words"])
    )
