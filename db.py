"""
MODULE: db
WHAT: SQLite-backed campaign history store. Runs alongside the file-based
campaign_store.py -- both are written on each pipeline run so the CLI and
web UI share a common history source.
DECISION: sqlite3 is Python stdlib -- zero extra dependencies. Single campaigns.db
file is easy to inspect, ship with a demo, and query for the history sidebar.
PRODUCTION ALTERNATIVE: Postgres with SQLAlchemy ORM, campaign rows linked to
asset records, approval states, and per-campaign cost tracking over time.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from config import BASE_DIR

DB_PATH = BASE_DIR / "campaigns.db"


def _conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS campaigns (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id       TEXT    NOT NULL,
                created_at        TEXT    NOT NULL,
                provider          TEXT,
                brief_json        TEXT    NOT NULL,
                summary_json      TEXT    NOT NULL,
                output_paths_json TEXT    NOT NULL DEFAULT '{}'
            )
        """)
        c.commit()


def save_campaign(brief, summary, output_paths_by_product=None):
    paths = {
        k: [str(p) for p in v]
        for k, v in (output_paths_by_product or {}).items()
    }
    with _conn() as c:
        c.execute(
            """INSERT INTO campaigns
               (campaign_id, created_at, provider, brief_json, summary_json, output_paths_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                brief.get("campaign_id", "unknown"),
                datetime.now().isoformat(),
                summary.get("provider", "flux"),
                json.dumps(brief),
                json.dumps(summary),
                json.dumps(paths),
            ),
        )
        c.commit()


def list_campaigns(limit=25):
    with _conn() as c:
        rows = c.execute(
            "SELECT id, campaign_id, created_at, provider, summary_json "
            "FROM campaigns ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_campaign(row_id):
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM campaigns WHERE id = ?", (row_id,)
        ).fetchone()
    return dict(row) if row else None
