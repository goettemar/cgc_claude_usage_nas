"""OpenRouter API client for credit balance queries."""

from __future__ import annotations

import requests

CREDITS_URL = "https://openrouter.ai/api/v1/credits"


class OpenRouterClient:
    """Fetches credit balance from the OpenRouter API."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def fetch_credits(self) -> dict:
        """GET /api/v1/credits → {total_credits, total_usage}."""
        r = requests.get(
            CREDITS_URL,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json().get("data", {})
        return {
            "total_credits": float(data.get("total_credits", 0)),
            "total_usage": float(data.get("total_usage", 0)),
        }
