"""Gradio app assembly — build_app() + main()."""

from __future__ import annotations

import logging

import gradio as gr
from dotenv import load_dotenv

from cgc_claude_usage.config import AppConfig
from cgc_claude_usage.ui.dashboard_tab import build_dashboard_tab
from cgc_claude_usage.ui.trends_tab import build_trends_tab
from cgc_claude_usage.ui.settings_tab import build_settings_tab

logger = logging.getLogger(__name__)


def build_app(config: AppConfig) -> gr.Blocks:
    """Construct the Gradio Blocks app with 3 tabs."""
    with gr.Blocks(title="CGC Claude Usage") as app:
        gr.Markdown("# CGC Claude Usage Dashboard")

        with gr.Tab("Dashboard"):
            build_dashboard_tab(config)

        with gr.Tab("Trends"):
            build_trends_tab()

        with gr.Tab("Einstellungen"):
            build_settings_tab(config)

    return app


def main() -> None:
    """Load config, set up logging, launch Gradio."""
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    config = AppConfig.load()
    logger.info("Config loaded (session_key=%s)", "set" if config.session_key else "empty")

    app = build_app(config)
    app.launch(
        server_name="0.0.0.0",
        server_port=7863,
        theme=gr.themes.Soft(
            primary_hue="teal",
            secondary_hue="purple",
            neutral_hue="slate",
        ),
        css="footer {display: none !important}",
    )
