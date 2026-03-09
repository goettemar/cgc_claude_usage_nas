"""Dashboard tab — current limits, overage, API costs as Markdown bars."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import gradio as gr

from cgc_claude_usage import storage
from cgc_claude_usage.config import AppConfig
from cgc_claude_usage.services.fetch_service import FetchResult, fetch_all

logger = logging.getLogger(__name__)


def _bar(pct: float, width: int = 20) -> str:
    """Unicode bar: █░ style."""
    filled = int(pct / 100 * width)
    filled = max(0, min(filled, width))
    empty = width - filled
    if pct < 50:
        color = "green"
    elif pct < 80:
        color = "orange"
    else:
        color = "red"
    bar = "█" * filled + "░" * empty
    return f'<span style="color:{color};font-family:monospace">{bar}</span> {pct:.0f}%'


def _format_reset(resets_at: str | None) -> str:
    """Format reset time as human-readable relative string."""
    if not resets_at:
        return ""
    try:
        reset = datetime.fromisoformat(resets_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = reset - now
        total_sec = int(delta.total_seconds())
        if total_sec <= 0:
            return "jetzt"
        hours, remainder = divmod(total_sec, 3600)
        minutes = remainder // 60
        if hours > 24:
            days = hours // 24
            hours = hours % 24
            return f"{days} T. {hours} Std. {minutes} Min."
        if hours > 0:
            return f"{hours} Std. {minutes} Min."
        return f"{minutes} Min."
    except Exception:
        return resets_at


def _format_reset_absolute(resets_at: str | None) -> str:
    """Format reset time as absolute date string."""
    if not resets_at:
        return ""
    try:
        reset = datetime.fromisoformat(resets_at.replace("Z", "+00:00"))
        local = reset.astimezone()
        days = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
        day_name = days[local.weekday()]
        return f"{day_name}, {local.strftime('%H:%M')}"
    except Exception:
        return resets_at


def _render_dashboard(result: FetchResult, last_update: str) -> str:
    """Build full dashboard markdown from a FetchResult."""
    lines = []

    # Session (5h)
    lines.append("### Session (5 Stunden)")
    if result.usage:
        five = result.usage.get("five_hour")
        if five:
            pct = five.get("utilization", 0)
            reset = _format_reset(five.get("resets_at"))
            lines.append(f"Aktuell: {_bar(pct)}")
            if reset:
                lines.append(f"Reset in: {reset}")
        else:
            lines.append("n/a")
    else:
        lines.append("Keine Daten")

    # Weekly
    lines.append("\n### Wöchentlich")
    if result.usage:
        week = result.usage.get("seven_day")
        if week:
            pct = week.get("utilization", 0)
            lines.append(f"Alle Modelle: {_bar(pct)}")
        else:
            lines.append("Alle Modelle: n/a")

        sonnet = result.usage.get("sonnet")
        if sonnet:
            pct = sonnet.get("utilization", 0)
            lines.append(f"Nur Sonnet: {_bar(pct)}")
        else:
            lines.append("Nur Sonnet: n/a")

        # Weekly reset info
        if week and week.get("resets_at"):
            abs_reset = _format_reset_absolute(week.get("resets_at"))
            rel_reset = _format_reset(week.get("resets_at"))
            lines.append(f"\nReset: {abs_reset} (in {rel_reset})")
    else:
        lines.append("Keine Daten")

    # Overage
    lines.append("\n### Zusatznutzung")
    if result.overage:
        currency = result.overage.get("currency", "EUR")
        spent = result.overage.get("spent_cents", 0) / 100
        limit = result.overage.get("limit_cents", 0) / 100
        balance = result.overage.get("balance_cents", 0) / 100
        sym = "€" if currency == "EUR" else "$"
        lines.append(
            f"{sym}{spent:.2f} / {sym}{limit:.2f} verbraucht — "
            f"Guthaben: {sym}{balance:.2f}"
        )
    else:
        lines.append("Nicht aktiviert")

    # API Costs
    lines.append("\n### API-Kosten")
    if result.api_entries:
        summary = storage.get_api_cost_summary()
        today = summary.get("today", 0)
        week_cost = summary.get("week", 0)
        month = summary.get("month", 0)
        lines.append(f"Heute: ${today:.2f} — Woche: ${week_cost:.2f} — Monat: ${month:.2f}")
    else:
        lines.append("Admin API nicht konfiguriert")

    # OpenRouter
    lines.append("\n### OpenRouter")
    if result.openrouter:
        total = result.openrouter.get("total_credits", 0)
        used = result.openrouter.get("total_usage", 0)
        available = total - used
        lines.append(
            f"Guthaben: ${total:.2f} — Verbraucht: ${used:.2f} — "
            f"Verfügbar: ${available:.2f}"
        )
    else:
        lines.append("Nicht konfiguriert")

    # DeepL
    lines.append("\n### DeepL")
    if result.deepl:
        used = result.deepl.get("character_count", 0)
        limit = result.deepl.get("character_limit", 0)
        pct = (used / limit * 100) if limit > 0 else 0
        remaining = limit - used
        lines.append(f"Zeichen: {_bar(pct)}")
        lines.append(f"{used:,} / {limit:,} verbraucht — Verbleibend: {remaining:,}")
    else:
        lines.append("Nicht konfiguriert")

    # Errors
    if result.errors:
        lines.append("\n### Fehler")
        for err in result.errors:
            lines.append(f"- {err}")

    # Footer
    lines.append(f"\n---\n*Zuletzt: {last_update}*")

    return "\n".join(lines)


def _do_refresh(config: AppConfig) -> str:
    """Execute fetch and return rendered markdown."""
    if not config.session_key:
        return "⚠ Session Key fehlt — siehe Einstellungen"

    result = fetch_all(config)

    # Save snapshot
    if result.usage:
        try:
            storage.save_snapshot(result.usage, result.overage)
        except Exception:
            logger.warning("Failed to save snapshot", exc_info=True)

    # Save API usage
    if result.api_entries:
        try:
            storage.save_api_usage(result.api_entries)
        except Exception:
            logger.warning("Failed to save API usage", exc_info=True)

    # Purge old data
    try:
        storage.purge_old_data(config.retention_days)
    except Exception:
        logger.warning("Failed to purge old data", exc_info=True)

    now = datetime.now(timezone.utc).astimezone().strftime("%H:%M:%S")
    return _render_dashboard(result, now)


def build_dashboard_tab(config: AppConfig) -> tuple[gr.Markdown, gr.Button]:
    """Build the dashboard tab. Returns (markdown, button) for wiring."""
    md = gr.Markdown("Dashboard bereit — klicke **Aktualisieren** zum Laden.")
    btn = gr.Button("Aktualisieren", variant="primary")

    def refresh():
        return _do_refresh(config)

    btn.click(fn=refresh, outputs=md)

    return md, btn
