from __future__ import annotations


def build_price_chart(ticker: str, *, entry=None, stop=None, tp1=None, tp2=None, period: str = "6mo"):
    """Grafico interattivo read-only: candele, medie, volume e livelli del Committee."""
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
        (entry, "Entry", "dot"), (stop, "Stop", "dash"), (tp1, "TP1", "dot"), (tp2, "TP2", "dot")
    ]:
        if isinstance(value, (int, float)):
            fig.add_hline(y=value, line_dash=dash, annotation_text=f"{label} {value:.2f}", annotation_position="top left", row=1, col=1)

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
