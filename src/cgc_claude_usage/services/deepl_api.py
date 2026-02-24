"""DeepL API client for usage/quota queries."""

from __future__ import annotations

import requests

USAGE_URL = "https://api-free.deepl.com/v2/usage"


class DeepLClient:
    """Fetches character usage from the DeepL Free API."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def fetch_usage(self) -> dict:
        """GET /v2/usage → {character_count, character_limit}."""
        r = requests.get(
            USAGE_URL,
            headers={"Authorization": f"DeepL-Auth-Key {self.api_key}"},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        return {
            "character_count": int(data.get("character_count", 0)),
            "character_limit": int(data.get("character_limit", 0)),
        }
