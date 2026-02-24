"""Trends tab — Plotly charts for usage history and API costs."""

from __future__ import annotations

from datetime import datetime

import gradio as gr
import plotly.graph_objects as go

from cgc_claude_usage import storage


PERIOD_MAP = {"24 Stunden": (24, 1), "7 Tage": (168, 7), "30 Tage": (720, 30)}


def _build_usage_chart(hours: int) -> go.Figure:
    """Build usage line chart from snapshots."""
    snapshots = storage.get_history(hours)
    fig = go.Figure()

    if not snapshots:
        fig.add_annotation(
            text="Keine Daten vorhanden",
            xref="paper", yref="paper", x=0.5, y=0.5,
            showarrow=False, font=dict(size=16, color="gray"),
        )
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#1a1a2e",
            plot_bgcolor="#1a1a2e",
        )
        return fig

    timestamps = []
    all_pcts = []
    sonnet_pcts = []
    for snap in snapshots:
        try:
            ts = datetime.fromisoformat(snap["timestamp"])
            timestamps.append(ts.astimezone())
        except Exception:
            timestamps.append(snap["timestamp"])
        all_pcts.append(snap.get("seven_day_pct") or 0)
        sonnet_pcts.append(snap.get("sonnet_pct") or 0)

    fig.add_trace(go.Scatter(
        x=timestamps, y=all_pcts,
        name="Alle Modelle", mode="lines+markers",
        line=dict(color="#00b4d8", width=2),
        marker=dict(size=4),
    ))
    fig.add_trace(go.Scatter(
        x=timestamps, y=sonnet_pcts,
        name="Sonnet", mode="lines+markers",
        line=dict(color="#9b59b6", width=2),
        marker=dict(size=4),
    ))

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#1a1a2e",
        plot_bgcolor="#1a1a2e",
        title="Wochen-Limits Verlauf",
        yaxis=dict(title="%", range=[0, 105]),
        xaxis=dict(title="Zeit"),
        legend=dict(orientation="h", y=1.12),
        margin=dict(l=50, r=20, t=60, b=40),
    )
    return fig


def _build_cost_chart(days: int) -> go.Figure:
    """Build API cost bar chart from daily aggregates."""
    api_data = storage.get_daily_api_usage(days)
    fig = go.Figure()

    if not api_data:
        fig.add_annotation(
            text="Keine API-Kostendaten vorhanden",
            xref="paper", yref="paper", x=0.5, y=0.5,
            showarrow=False, font=dict(size=16, color="gray"),
        )
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#1a1a2e",
            plot_bgcolor="#1a1a2e",
        )
        return fig

    daily: dict[str, float] = {}
    for entry in api_data:
        d = entry["date"][:10]
        daily[d] = daily.get(d, 0) + (entry.get("cost_usd") or 0)

    dates = sorted(daily.keys())
    costs = [daily[d] for d in dates]

    fig.add_trace(go.Bar(
        x=dates, y=costs,
        name="API-Kosten",
        marker_color="#00b4d8",
    ))

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#1a1a2e",
        plot_bgcolor="#1a1a2e",
        title="API-Kosten pro Tag",
        yaxis=dict(title="USD ($)"),
        xaxis=dict(title="Datum"),
        margin=dict(l=50, r=20, t=60, b=40),
    )
    return fig


def _compute_prognose(hours: int) -> str:
    """Estimate when weekly limit will be reached based on trend."""
    snapshots = storage.get_history(hours)
    if len(snapshots) < 2:
        return "Prognose: Mehr Datenpunkte benötigt."

    first = snapshots[0]
    last = snapshots[-1]
    try:
        t0 = datetime.fromisoformat(first["timestamp"])
        t1 = datetime.fromisoformat(last["timestamp"])
        dt_hours = (t1 - t0).total_seconds() / 3600
        if dt_hours < 0.1:
            return ""

        pct0 = first.get("seven_day_pct") or 0
        pct1 = last.get("seven_day_pct") or 0
        rate = (pct1 - pct0) / dt_hours

        if rate <= 0:
            return "Prognose: Verbrauch sinkt oder stabil — kein Limit-Risiko."

        remaining = 100 - pct1
        hours_left = remaining / rate

        reset_info = ""
        resets_at = last.get("seven_day_resets")
        if resets_at:
            try:
                reset = datetime.fromisoformat(resets_at.replace("Z", "+00:00"))
                hours_to_reset = (reset - t1).total_seconds() / 3600
                if hours_left > hours_to_reset:
                    reset_info = " (Reset erfolgt vorher)"
            except Exception:
                pass

        if hours_left > 168:
            return "Prognose: Bei aktuellem Verbrauch kein Limit-Risiko diese Woche."

        days_left = hours_left / 24
        return (
            f"Prognose: Bei aktuellem Tempo ({rate:.1f}%/Std.) Limit in "
            f"~{hours_left:.0f} Std. ({days_left:.1f} Tage) erreicht{reset_info}."
        )
    except Exception:
        return ""


def build_trends_tab() -> tuple[gr.Radio, gr.Plot, gr.Markdown, gr.Plot, gr.Timer]:
    """Build the trends tab. Returns components for wiring."""
    period = gr.Radio(
        choices=list(PERIOD_MAP.keys()),
        value="7 Tage",
        label="Zeitraum",
    )
    usage_plot = gr.Plot(label="Wochen-Limits Verlauf")
    prognose = gr.Markdown("")
    cost_plot = gr.Plot(label="API-Kosten pro Tag")
    timer = gr.Timer(value=300, active=True)  # 5 min independent refresh

    def update(period_label: str) -> tuple:
        hours, days = PERIOD_MAP.get(period_label, (168, 7))
        return (
            _build_usage_chart(hours),
            _compute_prognose(hours),
            _build_cost_chart(days),
        )

    period.change(fn=update, inputs=period, outputs=[usage_plot, prognose, cost_plot])
    timer.tick(fn=update, inputs=period, outputs=[usage_plot, prognose, cost_plot])

    # Load on first render via a short initial timer
    init_timer = gr.Timer(value=1, active=True)

    def init_load():
        return (*update("7 Tage"), gr.Timer(active=False))

    init_timer.tick(
        fn=init_load,
        outputs=[usage_plot, prognose, cost_plot, init_timer],
    )

    return period, usage_plot, prognose, cost_plot, timer
