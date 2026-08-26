from __future__ import annotations

from typing import Any


def build_price_chart(history: list[dict[str, Any]], *, ticker: str, entry=None, stop=None, tp1=None, tp2=None):
    """Build an interactive Plotly candlestick chart for the Trade Committee."""
    import pandas as pd
    import plotly.graph_objects as go

    if not history:
        return None
    df = pd.DataFrame(history)
    if df.empty or "date" not in df:
        return None

    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df["date"], open=df["open"], high=df["high"], low=df["low"], close=df["close"], name=ticker
    ))
    for key, label in [("sma20", "SMA20"), ("sma50", "SMA50"), ("sma200", "SMA200")]:
        if key in df and df[key].notna().any():
            fig.add_trace(go.Scatter(x=df["date"], y=df[key], mode="lines", name=label))

    for value, label, dash in [
        (entry, "Entry", "dot"), (stop, "Stop", "dash"), (tp1, "TP1", "dot"), (tp2, "TP2", "dot")
    ]:
        if isinstance(value, (int, float)):
            fig.add_hline(y=value, line_dash=dash, annotation_text=f"{label} {value:.2f}", annotation_position="top left")

    fig.update_layout(
        title=f"{ticker} · Prezzo, medie e livelli Trade Committee",
        xaxis_title="Data", yaxis_title="Prezzo",
        xaxis_rangeslider_visible=False, height=620, margin=dict(l=10, r=10, t=50, b=10),
        legend=dict(orientation="h"),
    )
    return fig
