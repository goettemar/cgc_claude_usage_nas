"""Tests for SQLite storage module."""

import pytest

from cgc_claude_usage import storage


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    """Each test gets its own fresh database."""
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(storage, "_conn", None)
    yield
    if storage._conn:
        storage._conn.close()
        storage._conn = None


class TestGetDb:
    def test_creates_tables(self):
        db = storage.get_db()
        tables = {
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "usage_snapshots" in tables
        assert "api_usage" in tables

    def test_singleton(self):
        db1 = storage.get_db()
        db2 = storage.get_db()
        assert db1 is db2


class TestSaveSnapshot:
    def test_save_and_retrieve(self):
        usage = {
            "five_hour": {"utilization": 42.5, "resets_at": "2026-02-13T15:00:00Z"},
            "seven_day": {"utilization": 60.0, "resets_at": "2026-02-17T00:00:00Z"},
            "sonnet": {"utilization": 30.0, "resets_at": "2026-02-17T00:00:00Z"},
        }
        overage = {
            "spent_cents": 450,
            "limit_cents": 10000,
            "balance_cents": 9550,
        }
        storage.save_snapshot(usage, overage)

        history = storage.get_history(hours=1)
        assert len(history) == 1
        snap = history[0]
        assert snap["five_hour_pct"] == 42.5
        assert snap["seven_day_pct"] == 60.0
        assert snap["overage_spent_cents"] == 450

    def test_save_with_none_overage(self):
        storage.save_snapshot({}, None)
        history = storage.get_history(hours=1)
        assert len(history) == 1
        assert history[0]["overage_spent_cents"] is None


class TestApiUsage:
    def _today(self):
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def test_save_and_query(self):
        today = self._today()
        entries = [
            {
                "date": today,
                "model": "claude-3-opus",
                "input_tokens": 1000,
                "output_tokens": 500,
                "cost_usd": 0.05,
            },
            {
                "date": today,
                "model": "claude-3-sonnet",
                "input_tokens": 2000,
                "output_tokens": 1000,
                "cost_usd": 0.02,
            },
        ]
        storage.save_api_usage(entries)

        daily = storage.get_daily_api_usage(days=7)
        assert len(daily) == 2

    def test_upsert_updates_existing(self):
        today = self._today()
        entry = {
            "date": today,
            "model": "claude-3-opus",
            "input_tokens": 1000,
            "output_tokens": 500,
            "cost_usd": 0.05,
        }
        storage.save_api_usage([entry])

        entry["cost_usd"] = 0.10
        entry["input_tokens"] = 2000
        storage.save_api_usage([entry])

        daily = storage.get_daily_api_usage(days=7)
        assert len(daily) == 1
        assert daily[0]["cost_usd"] == 0.10
        assert daily[0]["input_tokens"] == 2000

    def test_cost_summary(self):
        from datetime import datetime, timezone

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        entries = [
            {"date": today, "model": "opus", "cost_usd": 1.50},
            {"date": today, "model": "sonnet", "cost_usd": 0.50},
        ]
        storage.save_api_usage(entries)

        summary = storage.get_api_cost_summary()
        assert summary["today"] == 2.0
        assert summary["week"] == 2.0
        assert summary["month"] == 2.0


class TestPurge:
    def test_purge_old_data(self):
        storage.save_snapshot({}, None)
        db = storage.get_db()
        db.execute("UPDATE usage_snapshots SET timestamp = '2020-01-01T00:00:00+00:00'")
        db.commit()

        storage.purge_old_data(retention_days=1)
        assert len(storage.get_history(hours=999999)) == 0
