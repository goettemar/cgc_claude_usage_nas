"""Synchronous fetch orchestrator — replaces QThread FetchWorker."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from cgc_claude_usage.config import AppConfig

logger = logging.getLogger(__name__)


@dataclass
class FetchResult:
    usage: dict | None = None
    overage: dict | None = None
    api_entries: list[dict] = field(default_factory=list)
    openrouter: dict | None = None
    deepl: dict | None = None
    errors: list[str] = field(default_factory=list)


def fetch_all(config: AppConfig) -> FetchResult:
    """Fetch data from all configured APIs synchronously."""
    result = FetchResult()

    # Claude Pro-Plan usage
    if config.session_key:
        try:
            from cgc_claude_usage.services.claude_web import ClaudeWebClient

            client = ClaudeWebClient(config.session_key, config.org_uuid)

            # Auto-discover org UUID if missing (e.g. Max plan)
            if not config.org_uuid:
                discovered = client.discover_org_uuid()
                config.org_uuid = discovered
                logger.info("Auto-discovered org_uuid: %s", discovered)
                config.save()

            result.usage = client.fetch_usage()
            result.overage = client.fetch_overage()
        except Exception as e:
            result.errors.append(f"Pro-Plan: {e}")

    # Admin API
    if config.admin_api_key:
        try:
            from cgc_claude_usage.services.admin_api import AdminAPIClient

            admin = AdminAPIClient(config.admin_api_key)
            costs = admin.fetch_costs(days=30)
            usage_data = admin.fetch_usage(days=30)
            cost_map = {}
            for c in costs:
                key = (c["date"], c["model"])
                cost_map[key] = c["cost_usd"]
            merged = []
            for u in usage_data:
                entry = dict(u)
                entry["cost_usd"] = cost_map.get((u["date"], u["model"]), 0.0)
                merged.append(entry)
            result.api_entries = merged
        except Exception as e:
            result.errors.append(f"Admin API: {e}")

    # OpenRouter
    if config.openrouter_api_key:
        try:
            from cgc_claude_usage.services.openrouter_api import OpenRouterClient

            client = OpenRouterClient(config.openrouter_api_key)
            result.openrouter = client.fetch_credits()
        except Exception as e:
            result.errors.append(f"OpenRouter: {e}")

    # DeepL
    if config.deepl_api_key:
        try:
            from cgc_claude_usage.services.deepl_api import DeepLClient

            client = DeepLClient(config.deepl_api_key)
            result.deepl = client.fetch_usage()
        except Exception as e:
            result.errors.append(f"DeepL: {e}")

    return result
