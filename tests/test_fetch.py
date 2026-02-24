"""Tests for fetch_service with mocked API clients."""

from unittest.mock import MagicMock, patch

from cgc_claude_usage.config import AppConfig
from cgc_claude_usage.services.fetch_service import fetch_all


class TestFetchAll:
    def test_returns_empty_without_session(self):
        config = AppConfig()
        result = fetch_all(config)
        assert result.usage is None
        assert result.overage is None
        assert result.api_entries == []
        assert result.errors == []

    @patch("cgc_claude_usage.services.claude_web.ClaudeWebClient")
    def test_fetches_claude_usage(self, mock_cls):
        mock_client = MagicMock()
        mock_client.fetch_usage.return_value = {
            "five_hour": {"utilization": 42.0},
            "seven_day": {"utilization": 60.0},
            "sonnet": None,
            "opus": None,
        }
        mock_client.fetch_overage.return_value = None
        mock_cls.return_value = mock_client

        config = AppConfig(session_key="sk-test", org_uuid="org-123")
        result = fetch_all(config)

        assert result.usage is not None
        assert result.usage["five_hour"]["utilization"] == 42.0
        assert result.overage is None
        assert result.errors == []

    @patch("cgc_claude_usage.services.claude_web.ClaudeWebClient")
    def test_handles_claude_error(self, mock_cls):
        mock_cls.side_effect = Exception("connection refused")

        config = AppConfig(session_key="sk-test", org_uuid="org-123")
        result = fetch_all(config)

        assert result.usage is None
        assert len(result.errors) == 1
        assert "Pro-Plan" in result.errors[0]

    @patch("cgc_claude_usage.services.openrouter_api.OpenRouterClient")
    def test_fetches_openrouter(self, mock_cls):
        mock_client = MagicMock()
        mock_client.fetch_credits.return_value = {
            "total_credits": 10.0,
            "total_usage": 3.5,
        }
        mock_cls.return_value = mock_client

        config = AppConfig(openrouter_api_key="sk-or-test")
        result = fetch_all(config)

        assert result.openrouter is not None
        assert result.openrouter["total_credits"] == 10.0

    @patch("cgc_claude_usage.services.deepl_api.DeepLClient")
    def test_fetches_deepl(self, mock_cls):
        mock_client = MagicMock()
        mock_client.fetch_usage.return_value = {
            "character_count": 5000,
            "character_limit": 500000,
        }
        mock_cls.return_value = mock_client

        config = AppConfig(deepl_api_key="test-key:fx")
        result = fetch_all(config)

        assert result.deepl is not None
        assert result.deepl["character_count"] == 5000

    @patch("cgc_claude_usage.services.admin_api.AdminAPIClient")
    def test_fetches_admin_api(self, mock_cls):
        mock_client = MagicMock()
        mock_client.fetch_costs.return_value = [
            {"date": "2026-02-24", "model": "opus", "cost_usd": 1.5}
        ]
        mock_client.fetch_usage.return_value = [
            {"date": "2026-02-24", "model": "opus", "input_tokens": 1000, "output_tokens": 500}
        ]
        mock_cls.return_value = mock_client

        config = AppConfig(admin_api_key="sk-ant-admin-test")
        result = fetch_all(config)

        assert len(result.api_entries) == 1
        assert result.api_entries[0]["cost_usd"] == 1.5
        assert result.api_entries[0]["input_tokens"] == 1000
