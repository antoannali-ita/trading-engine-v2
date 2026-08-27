from __future__ import annotations

import streamlit as st

try:
    from dashboard.data_access import lab_watchlist
except ModuleNotFoundError:
    from data_access import lab_watchlist  # type: ignore

st.title("👀 Watchlist")
st.caption("Titoli da seguire. WATCH non significa BUY: questa pagina serve a non perdere candidati interessanti e a vedere quando cambiano stato.")

rows = lab_watchlist(1500)
if not rows:
    st.info("Nessun titolo attivo in watchlist.")
    st.stop()

preferred = [
    "symbol", "ticker", "strategy", "source", "status", "score", "reason",
    "price", "entry", "max_buy", "stop", "tp1", "tp2", "trigger",
    "distance_to_entry_pct", "signal_date", "created_at", "updated_at", "active",
]

available = set().union(*(r.keys() for r in rows))
cols = [c for c in preferred if c in available]
if not cols:
    cols = list(rows[0].keys())

st.dataframe(
    [{c: r.get(c) for c in cols} for r in rows],
    hide_index=True,
    use_container_width=True,
)

st.info(
    "La watchlist verrà progressivamente arricchita con stati WATCH / APPROACHING / RECHECK_REQUIRED / READY_FOR_COMMITTEE / APPROVABLE. "
    "I titoli non più interessanti saranno disattivati, non cancellati, così il Laboratory conserva lo storico."
)
