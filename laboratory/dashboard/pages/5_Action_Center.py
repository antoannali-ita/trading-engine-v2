import sys
from pathlib import Path

import streamlit as st

LAB_ROOT = Path(__file__).resolve().parents[2]
SRC = LAB_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lab.data import load_signals

st.set_page_config(page_title="Trading Lab | Action Center", layout="wide")
st.title("Action Center")
st.caption("Solo supporto decisionale. Nessun ordine automatico viene inviato al broker.")

try:
    signals = load_signals(1000)
except Exception as exc:
    st.error(str(exc))
    st.stop()

if signals.empty:
    st.info("Nessun segnale disponibile.")
    st.stop()

interesting = {"BUY NOW", "BUY LIMIT", "PRE-BUY", "PRE_BUY", "PRE_BUY_HIGH", "SHADOW_BUY"}
mask = signals.apply(
    lambda r: str(r.get("decision", "")).upper() in interesting or str(r.get("status", "")).upper() in interesting,
    axis=1,
)
view = signals[mask].copy()
if view.empty:
    st.info("Nessun candidato operativo al momento.")
    st.stop()

for _, row in view.head(30).iterrows():
    ticker = row.get("ticker", "N/D")
    market = row.get("market", "")
    title = f"{ticker} | {row.get('status', row.get('decision', ''))} | Score {row.get('score_total', 'N/D')}"
    with st.expander(title):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Prezzo", row.get("price", "N/D"))
        c2.metric("Entry", row.get("entry", "N/D"))
        c3.metric("Max Buy", row.get("max_buy", "N/D"))
        c4.metric("R/R TP2", row.get("rr_net_tp2", "N/D"))

        st.write(
            {
                "setup": row.get("setup"),
                "trigger": row.get("trigger"),
                "buy_range": [row.get("buy_range_low"), row.get("buy_range_high")],
                "stop": row.get("stop"),
                "tp1": row.get("tp1"),
                "tp2": row.get("tp2"),
                "qty": row.get("qty"),
                "capital": row.get("capital"),
                "loss_max": row.get("loss_max"),
                "earnings": row.get("earnings_date"),
                "data_quality": row.get("data_quality"),
            }
        )

        exchange = "NASDAQ" if market == "USA" else "MIL"
        st.link_button("Apri TradingView", f"https://www.tradingview.com/chart/?symbol={exchange}:{ticker}")
        st.code(
            f"{ticker} | LIMIT {row.get('entry', 'N/D')} | QTY {row.get('qty', 'N/D')} | "
            f"STOP {row.get('stop', 'N/D')} | TP1 {row.get('tp1', 'N/D')} | TP2 {row.get('tp2', 'N/D')}",
            language=None,
        )
