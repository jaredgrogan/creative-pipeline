"""
MODULE: campaign_store
WHAT: Persists campaign runs to the campaigns/ directory -- brief, summary, and
metadata -- so the Streamlit UI can list and reload previous runs.
DECISION: Campaign history is useful for demonstrating the pipeline across multiple
briefs. Each run is stored as a timestamped folder with brief.json and summary.json.
Outputs stay in outputs/ and are not duplicated here to save disk space.
PRODUCTION ALTERNATIVE: Campaign history stored in a database (Postgres, Dynamo)
with full audit trail, run versioning, and cost tracking per campaign over time.
"""

import json
from datetime import datetime
from pathlib import Path
from config import CAMPAIGNS_DIR


def save_campaign(brief, run_summary):
    """
    Save brief and run summary for a completed campaign run.
    Returns the campaign directory Path.
    """
    CAMPAIGNS_DIR.mkdir(parents=True, exist_ok=True)

    campaign_id = brief.get("campaign_id", "unknown")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = "{}_{}".format(campaign_id, timestamp)
    campaign_dir = CAMPAIGNS_DIR / folder_name
    campaign_dir.mkdir(parents=True, exist_ok=True)

    brief_path = campaign_dir / "brief.json"
    brief_path.write_text(json.dumps(brief, indent=2), encoding="utf-8")

    summary_with_ts = dict(run_summary)
    summary_with_ts["saved_at"] = datetime.now().isoformat()
    summary_path = campaign_dir / "summary.json"
    summary_path.write_text(json.dumps(summary_with_ts, indent=2), encoding="utf-8")

    return campaign_dir


def list_campaigns():
    """
    Return list of past campaign dicts sorted newest first.
    Each dict contains: campaign_id, timestamp, summary, path.
    """
    if not CAMPAIGNS_DIR.exists():
        return []

    campaigns = []
    for campaign_dir in sorted(CAMPAIGNS_DIR.iterdir(), reverse=True):
        if not campaign_dir.is_dir():
            continue
        brief_path = campaign_dir / "brief.json"
        summary_path = campaign_dir / "summary.json"
        if not brief_path.exists() or not summary_path.exists():
            continue
        try:
            brief = json.loads(brief_path.read_text(encoding="utf-8"))
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            campaigns.append({
                "campaign_id": brief.get("campaign_id", "unknown"),
                "timestamp": summary.get("saved_at", ""),
                "summary": summary,
                "brief": brief,
                "path": campaign_dir,
            })
        except Exception:
            continue

    return campaigns


def load_campaign(campaign_dir):
    """
    Load brief and summary from a campaign directory.
    Returns (brief dict, summary dict).
    """
    campaign_dir = Path(campaign_dir)
    brief = json.loads((campaign_dir / "brief.json").read_text(encoding="utf-8"))
    summary = json.loads((campaign_dir / "summary.json").read_text(encoding="utf-8"))
    return brief, summary
