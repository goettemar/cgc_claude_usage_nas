"""Claude.ai Session-API client for Pro-Plan usage data."""

from __future__ import annotations

import requests

BASE_URL = "https://claude.ai/api"

_HEADERS_TEMPLATE = {
    "accept": "*/*",
    "content-type": "application/json",
    "anthropic-client-platform": "web_claude_ai",
    "anthropic-client-version": "1.0.0",
    "origin": "https://claude.ai",
    "referer": "https://claude.ai/settings/usage",
    "user-agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
    ),
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
}


class ClaudeWebClient:
    """Fetches usage data from claude.ai internal API."""

    def __init__(self, session_key: str, org_uuid: str = "", cookie_header: str = ""):
        self.session_key = session_key
        self.org_uuid = org_uuid
        self._cookie_header = cookie_header

    def _headers(self) -> dict:
        h = dict(_HEADERS_TEMPLATE)
        if self._cookie_header:
            h["cookie"] = self._cookie_header
        else:
            h["cookie"] = f"sessionKey={self.session_key}"
        return h

    def discover_org_uuid(self) -> str:
        """GET /api/organizations → return first org UUID."""
        r = requests.get(
            f"{BASE_URL}/organizations",
            headers=self._headers(),
            timeout=15,
        )
        r.raise_for_status()
        orgs = r.json()
        if not orgs:
            raise ValueError("No organizations found")
        self.org_uuid = orgs[0]["uuid"]
        return self.org_uuid

    def fetch_usage(self) -> dict:
        """GET /api/organizations/{org}/usage → session + weekly limits.

        Returns dict with keys: five_hour, seven_day, sonnet, opus.
        Each value is None or {utilization: float, resets_at: str}.
        """
        r = requests.get(
            f"{BASE_URL}/organizations/{self.org_uuid}/usage",
            headers=self._headers(),
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        return {
            "five_hour": data.get("five_hour"),
            "seven_day": data.get("seven_day"),
            "sonnet": data.get("seven_day_sonnet"),
            "opus": data.get("seven_day_opus"),
        }

    def fetch_overage(self) -> dict | None:
        """GET /api/organizations/{org}/overage_spend_limit.

        Returns dict with keys: currency, limit_cents, spent_cents, balance_cents.
        Returns None if overage is disabled.
        """
        r = requests.get(
            f"{BASE_URL}/organizations/{self.org_uuid}/overage_spend_limit",
            headers=self._headers(),
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        if not data.get("is_enabled"):
            return None
        limit = data.get("monthly_credit_limit", 0)
        spent = data.get("used_credits", 0)
        return {
            "currency": data.get("currency", "EUR"),
            "limit_cents": limit,
            "spent_cents": spent,
            "balance_cents": limit - spent,
        }
