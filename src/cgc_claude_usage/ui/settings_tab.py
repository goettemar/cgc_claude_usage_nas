"""Settings tab — Token/Keys input, save, test connection."""

from __future__ import annotations

import gradio as gr

from cgc_claude_usage.config import AppConfig


def build_settings_tab(config: AppConfig) -> dict:
    """Build the settings tab. Returns dict of components."""
    gr.Markdown("### Claude.ai Session")
    session_key = gr.Textbox(
        label="Session Key",
        type="password",
        placeholder="sk-ant-sid...",
        value=config.session_key,
    )
    org_uuid = gr.Textbox(
        label="Org UUID",
        placeholder="Wird automatisch erkannt oder manuell einfügen",
        value=config.org_uuid,
    )

    gr.Markdown("### Anthropic Admin API (optional)")
    admin_key = gr.Textbox(
        label="Admin API Key",
        type="password",
        placeholder="sk-ant-admin... (leer lassen wenn nicht benötigt)",
        value=config.admin_api_key,
    )

    gr.Markdown("### OpenRouter (optional)")
    openrouter_key = gr.Textbox(
        label="API Key",
        type="password",
        placeholder="sk-or-... (leer lassen wenn nicht benötigt)",
        value=config.openrouter_api_key,
    )

    gr.Markdown("### DeepL (optional)")
    deepl_key = gr.Textbox(
        label="API Key",
        type="password",
        placeholder="xxxxxxxx-...:fx (leer lassen wenn nicht benötigt)",
        value=config.deepl_api_key,
    )

    gr.Markdown("### Einstellungen")
    refresh_interval = gr.Number(
        label="Auto-Refresh Intervall (Minuten)",
        value=config.auto_refresh_minutes,
        minimum=1,
        maximum=60,
        precision=0,
    )
    retention_days = gr.Number(
        label="History Aufbewahrung (Tage)",
        value=config.retention_days,
        minimum=7,
        maximum=365,
        precision=0,
    )

    with gr.Row():
        btn_save = gr.Button("Speichern", variant="primary")
        btn_test = gr.Button("Verbindung testen", variant="secondary")

    status = gr.Markdown("")

    def save(sk, org, admin, openrouter, deepl, refresh, retention):
        config.session_key = sk.strip()
        config.org_uuid = org.strip()
        config.admin_api_key = admin.strip()
        config.openrouter_api_key = openrouter.strip()
        config.deepl_api_key = deepl.strip()
        config.auto_refresh_minutes = int(refresh)
        config.retention_days = int(retention)
        config.save()
        return "Gespeichert."

    def test_connection(sk, org):
        sk = sk.strip()
        org = org.strip()
        if not sk:
            return "Session Key benötigt."
        try:
            from cgc_claude_usage.services.claude_web import ClaudeWebClient

            client = ClaudeWebClient(sk, org)
            if not org:
                org = client.discover_org_uuid()
                config.org_uuid = org
                config.save()
            usage = client.fetch_usage()
            five = usage.get("five_hour") or {}
            week = usage.get("seven_day") or {}
            return (
                f"Verbindung OK — Session: {five.get('utilization', '?')}%, "
                f"Woche: {week.get('utilization', '?')}%"
            )
        except Exception as e:
            return f"Fehler: {e}"

    inputs = [session_key, org_uuid, admin_key, openrouter_key, deepl_key,
              refresh_interval, retention_days]
    btn_save.click(fn=save, inputs=inputs, outputs=status)
    btn_test.click(fn=test_connection, inputs=[session_key, org_uuid], outputs=status)

    return {
        "session_key": session_key,
        "org_uuid": org_uuid,
        "admin_key": admin_key,
        "openrouter_key": openrouter_key,
        "deepl_key": deepl_key,
        "refresh_interval": refresh_interval,
        "retention_days": retention_days,
        "status": status,
    }
