"""Anthropic Admin API client for API token usage and costs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import requests

BASE_URL = "https://api.anthropic.com/v1/organizations"


class AdminAPIClient:
    """Fetches API usage/cost data from Anthropic Admin API (optional)."""

    def __init__(self, admin_key: str):
        self.admin_key = admin_key

    def _headers(self) -> dict:
        return {
            "x-api-key": self.admin_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    def fetch_usage(self, days: int = 7, group_by: str = "model") -> list[dict]:
        """GET usage_report/messages → token usage grouped by model/day."""
        now = datetime.now(timezone.utc)
        start = (now - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00Z")
        end = now.strftime("%Y-%m-%dT23:59:59Z")

        r = requests.get(
            f"{BASE_URL}/usage_report/messages",
            headers=self._headers(),
            params={
                "start_date": start,
                "end_date": end,
                "group_by": group_by,
                "bucket": "1d",
            },
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        results = []
        for item in data.get("data", []):
            results.append(
                {
                    "date": item.get("date", ""),
                    "model": item.get("model", "unknown"),
                    "input_tokens": item.get("input_tokens", 0),
                    "output_tokens": item.get("output_tokens", 0),
                }
            )
        return results

    def fetch_costs(self, days: int = 7) -> list[dict]:
        """GET cost_report → costs in USD by day."""
        now = datetime.now(timezone.utc)
        start = (now - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00Z")
        end = now.strftime("%Y-%m-%dT23:59:59Z")

        r = requests.get(
            f"{BASE_URL}/cost_report",
            headers=self._headers(),
            params={
                "start_date": start,
                "end_date": end,
                "bucket": "1d",
            },
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        results = []
        for item in data.get("data", []):
            results.append(
                {
                    "date": item.get("date", ""),
                    "model": item.get("model", "unknown"),
                    "cost_usd": item.get("cost_usd", 0.0),
                }
            )
        return results
