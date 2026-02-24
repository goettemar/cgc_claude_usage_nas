"""SQLite history storage for usage snapshots and API costs."""

from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.environ.get("DATA_DIR", "/app/data"))
DB_PATH = DATA_DIR / "history.db"

_conn: sqlite3.Connection | None = None


def get_db() -> sqlite3.Connection:
    """Singleton connection to history.db."""
    global _conn
    if _conn is None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(DB_PATH))
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _init_tables(_conn)
    return _conn


def _init_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS usage_snapshots (
            id INTEGER PRIMARY KEY,
            timestamp TEXT NOT NULL,
            five_hour_pct REAL,
            five_hour_resets TEXT,
            seven_day_pct REAL,
            seven_day_resets TEXT,
            sonnet_pct REAL,
            sonnet_resets TEXT,
            overage_spent_cents INTEGER,
            overage_limit_cents INTEGER,
            overage_balance_cents INTEGER
        );

        CREATE TABLE IF NOT EXISTS api_usage (
            id INTEGER PRIMARY KEY,
            date TEXT NOT NULL,
            model TEXT NOT NULL DEFAULT 'unknown',
            input_tokens INTEGER,
            output_tokens INTEGER,
            cost_usd REAL,
            UNIQUE(date, model)
        );

        CREATE INDEX IF NOT EXISTS idx_snapshots_ts ON usage_snapshots(timestamp);
        CREATE INDEX IF NOT EXISTS idx_api_date ON api_usage(date);
    """)


def save_snapshot(usage: dict, overage: dict | None) -> None:
    """Save a usage snapshot to the database."""
    db = get_db()
    ts = datetime.now(timezone.utc).isoformat()

    five = usage.get("five_hour") or {}
    week = usage.get("seven_day") or {}
    sonnet = usage.get("sonnet") or {}

    ov_spent = ov_limit = ov_balance = None
    if overage:
        ov_spent = overage.get("spent_cents")
        ov_limit = overage.get("limit_cents")
        ov_balance = overage.get("balance_cents")

    db.execute(
        """INSERT INTO usage_snapshots
           (timestamp, five_hour_pct, five_hour_resets,
            seven_day_pct, seven_day_resets,
            sonnet_pct, sonnet_resets,
            overage_spent_cents, overage_limit_cents, overage_balance_cents)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            ts,
            five.get("utilization"),
            five.get("resets_at"),
            week.get("utilization"),
            week.get("resets_at"),
            sonnet.get("utilization"),
            sonnet.get("resets_at"),
            ov_spent,
            ov_limit,
            ov_balance,
        ),
    )
    db.commit()


def get_history(hours: int = 168) -> list[dict]:
    """Get usage snapshots from the last N hours."""
    db = get_db()
    cutoff = datetime.now(timezone.utc).isoformat()
    rows = db.execute(
        """SELECT * FROM usage_snapshots
           WHERE timestamp >= datetime(?, '-' || ? || ' hours')
           ORDER BY timestamp ASC""",
        (cutoff, hours),
    ).fetchall()
    return [dict(r) for r in rows]


def save_api_usage(entries: list[dict]) -> None:
    """Save API usage entries (upsert by date+model)."""
    db = get_db()
    for entry in entries:
        db.execute(
            """INSERT INTO api_usage (date, model, input_tokens, output_tokens, cost_usd)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(date, model) DO UPDATE SET
                   input_tokens = excluded.input_tokens,
                   output_tokens = excluded.output_tokens,
                   cost_usd = excluded.cost_usd""",
            (
                entry["date"],
                entry.get("model", "unknown"),
                entry.get("input_tokens", 0),
                entry.get("output_tokens", 0),
                entry.get("cost_usd", 0.0),
            ),
        )
    db.commit()


def get_daily_api_usage(days: int = 30) -> list[dict]:
    """Get daily API usage for the last N days."""
    db = get_db()
    cutoff = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = db.execute(
        """SELECT date, model,
                  SUM(input_tokens) as input_tokens,
                  SUM(output_tokens) as output_tokens,
                  SUM(cost_usd) as cost_usd
           FROM api_usage
           WHERE date >= date(?, '-' || ? || ' days')
           GROUP BY date, model
           ORDER BY date ASC""",
        (cutoff, days),
    ).fetchall()
    return [dict(r) for r in rows]


def get_api_cost_summary() -> dict:
    """Get cost summary: today, this week, this month."""
    db = get_db()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _sum(query: str, params: tuple) -> float:
        row = db.execute(query, params).fetchone()
        return row["total"] if row else 0.0

    return {
        "today": _sum(
            "SELECT COALESCE(SUM(cost_usd), 0) as total FROM api_usage WHERE date = ?",
            (today,),
        ),
        "week": _sum(
            "SELECT COALESCE(SUM(cost_usd), 0) as total FROM api_usage WHERE date >= date(?, '-7 days')",
            (today,),
        ),
        "month": _sum(
            "SELECT COALESCE(SUM(cost_usd), 0) as total FROM api_usage WHERE date >= date(?, '-30 days')",
            (today,),
        ),
    }


def purge_old_data(retention_days: int = 90) -> None:
    """Delete snapshots older than retention_days."""
    db = get_db()
    cutoff = datetime.now(timezone.utc).isoformat()
    db.execute(
        "DELETE FROM usage_snapshots WHERE timestamp < datetime(?, '-' || ? || ' days')",
        (cutoff, retention_days),
    )
    db.execute(
        "DELETE FROM api_usage WHERE date < date(?, '-' || ? || ' days')",
        (cutoff, retention_days),
    )
    db.commit()
