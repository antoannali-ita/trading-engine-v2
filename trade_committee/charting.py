from __future__ import annotations

from datetime import datetime


def get_live_price(ticker: str):
    """Return the freshest available market price, timestamp and source label.

    Best effort only: during market hours it tries 1-minute data first, then
    5-minute data, and finally falls back to the latest daily close.
    """
    import yfinance as yf

    symbol = ticker.strip().upper()
    t = yf.Ticker(symbol)

    for interval, period, source in (
        ("1m", "1d", "Yahoo 1m"),
        ("5m", "5d", "Yahoo 5m"),
        ("1d", "5d", "Yahoo EOD"),
    ):
        try:
            hist = t.history(period=period, interval=interval, auto_adjust=False, prepost=False)
            close = hist["Close"].dropna() if not hist.empty and "Close" in hist else None
            if close is not None and not close.empty:
                ts = close.index[-1]
                try:
                    ts_label = ts.to_pydatetime().astimezone().strftime("%d/%m/%Y %H:%M:%S %Z")
                except Exception:
                    ts_label = str(ts)
                return float(close.iloc[-1]), ts_label, source
        except Exception:
            continue

    return None, None, "N/D"


def build_price_chart(
    ticker: str,
    *,
    entry=None,
    stop=None,
    tp1=None,
    tp2=None,
    current_price=None,
    current_price_time=None,
    period: str = "6mo",
):
    """Grafico interattivo read-only: candele, medie, volume e livelli CORE."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import yfinance as yf

    symbol = ticker.strip().upper()
    hist = yf.Ticker(symbol).history(period=period, auto_adjust=False)
    if hist.empty:
        return None

    hist = hist.copy()
    hist["SMA20"] = hist["Close"].rolling(20).mean()
    hist["SMA50"] = hist["Close"].rolling(50).mean()
    hist["SMA200"] = hist["Close"].rolling(200).mean()

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.78, 0.22], vertical_spacing=0.04)
    fig.add_trace(
        go.Candlestick(x=hist.index, open=hist["Open"], high=hist["High"], low=hist["Low"], close=hist["Close"], name=symbol),
        row=1, col=1,
    )
    for key in ("SMA20", "SMA50", "SMA200"):
        if hist[key].notna().any():
            fig.add_trace(go.Scatter(x=hist.index, y=hist[key], mode="lines", name=key), row=1, col=1)
    fig.add_trace(go.Bar(x=hist.index, y=hist["Volume"], name="Volume"), row=2, col=1)

    for value, label, dash in [
        (entry, "Entry CORE", "dot"),
        (stop, "Stop", "dash"),
        (tp1, "TP1", "dot"),
        (tp2, "TP2", "dot"),
        (current_price, "Prezzo corrente", "solid"),
    ]:
        if isinstance(value, (int, float)):
            annotation = f"{label} {value:.2f}"
            if label == "Prezzo corrente" and current_price_time:
                annotation += f" · {current_price_time}"
            fig.add_hline(
                y=value,
                line_dash=dash,
                annotation_text=annotation,
                annotation_position="top left" if label != "Prezzo corrente" else "bottom right",
                row=1,
                col=1,
            )

    fig.update_layout(
        title=f"{symbol} · Prezzo, trend, volumi e livelli operativi",
        xaxis_rangeslider_visible=False,
        height=670,
        margin=dict(l=10, r=10, t=55, b=10),
        legend=dict(orientation="h"),
        hovermode="x unified",
    )
    fig.update_yaxes(title_text="Prezzo", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)
    return fig
