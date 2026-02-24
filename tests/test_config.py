"""Tests for AppConfig dual-source configuration."""

import json

from cgc_claude_usage.config import AppConfig


class TestAppConfig:
    def test_defaults(self):
        cfg = AppConfig()
        assert cfg.session_key == ""
        assert cfg.org_uuid == ""
        assert cfg.admin_api_key == ""
        assert cfg.openrouter_api_key == ""
        assert cfg.auto_refresh_minutes == 15
        assert cfg.retention_days == 90

    def test_save_and_load(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        monkeypatch.setattr("cgc_claude_usage.config.DATA_DIR", tmp_path)
        monkeypatch.setattr("cgc_claude_usage.config.CONFIG_FILE", config_file)

        cfg = AppConfig(session_key="sk-test", org_uuid="org-123")
        cfg.save()

        assert config_file.exists()
        data = json.loads(config_file.read_text())
        assert data["session_key"] == "sk-test"
        assert data["org_uuid"] == "org-123"

        loaded = AppConfig.load()
        assert loaded.session_key == "sk-test"
        assert loaded.org_uuid == "org-123"

    def test_load_ignores_unknown_fields(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        monkeypatch.setattr("cgc_claude_usage.config.DATA_DIR", tmp_path)
        monkeypatch.setattr("cgc_claude_usage.config.CONFIG_FILE", config_file)

        config_file.write_text(
            json.dumps({"session_key": "sk", "unknown_field": "value"})
        )
        cfg = AppConfig.load()
        assert cfg.session_key == "sk"
        assert not hasattr(cfg, "unknown_field")

    def test_load_returns_defaults_on_missing_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "cgc_claude_usage.config.CONFIG_FILE", tmp_path / "nonexistent.json"
        )
        cfg = AppConfig.load()
        assert cfg.session_key == ""

    def test_load_returns_defaults_on_corrupt_file(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        config_file.write_text("not json")
        monkeypatch.setattr("cgc_claude_usage.config.DATA_DIR", tmp_path)
        monkeypatch.setattr("cgc_claude_usage.config.CONFIG_FILE", config_file)

        cfg = AppConfig.load()
        assert cfg.session_key == ""

    def test_env_fallback(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "cgc_claude_usage.config.CONFIG_FILE", tmp_path / "nonexistent.json"
        )
        monkeypatch.setenv("SESSION_KEY", "sk-from-env")
        monkeypatch.setenv("ORG_UUID", "org-from-env")
        monkeypatch.setenv("AUTO_REFRESH_MINUTES", "5")

        cfg = AppConfig.load()
        assert cfg.session_key == "sk-from-env"
        assert cfg.org_uuid == "org-from-env"
        assert cfg.auto_refresh_minutes == 5

    def test_json_takes_priority_over_env(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        monkeypatch.setattr("cgc_claude_usage.config.DATA_DIR", tmp_path)
        monkeypatch.setattr("cgc_claude_usage.config.CONFIG_FILE", config_file)
        monkeypatch.setenv("SESSION_KEY", "sk-from-env")

        config_file.write_text(json.dumps({"session_key": "sk-from-json"}))
        cfg = AppConfig.load()
        assert cfg.session_key == "sk-from-json"
