import html
import sys
from pathlib import Path

import pandas as pd
import streamlit as st
import yfinance as yf

LAB_ROOT = Path(__file__).resolve().parents[2]
SRC = LAB_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lab.auth import require_dashboard_auth
from lab.data import load_core_high_conviction
from lab.ui import apply_theme, fmt_money, fmt_rr, fmt_score, page_header

st.set_page_config(page_title="Trading Lab | Core Opportunities", layout="wide", page_icon="🎯")
require_dashboard_auth()
apply_theme()
page_header(
    "Core Opportunities",
    "Solo BUY e PRE-BUY HIGH prodotti dai motori Core. USA e Italy mantengono le proprie regole; questa pagina non ricalcola né promuove segnali.",
    eyebrow="CORE · USA · ITALY · HIGH CONVICTION",
)


@st.cache_data(ttl=300, show_spinner=False)
def intraday_snapshot(ticker: str, market: str):
    symbol = ticker if market.upper() == "USA" or "." in ticker else f"{ticker}.MI"
    try:
        hist = yf.Ticker(symbol).history(period="1d", interval="5m", auto_adjust=True)
        if hist.empty or hist["Close"].dropna().empty:
            return None, None, None, None
        current = float(hist["Close"].dropna().iloc[-1])
        day_low = float(hist["Low"].dropna().min()) if "Low" in hist and not hist["Low"].dropna().empty else None
        day_high = float(hist["High"].dropna().max()) if "High" in hist and not hist["High"].dropna().empty else None
        session_open = float(hist["Open"].dropna().iloc[0]) if "Open" in hist and not hist["Open"].dropna().empty else None
        day_pct = ((current / session_open) - 1.0) * 100.0 if session_open not in (None, 0) else None
        return current, day_low, day_high, day_pct
    except Exception:
        return None, None, None, None


def _currency(market: str) -> str:
    return "€" if market.upper() == "ITALY" else "$"


def _money(value, market: str) -> str:
    return fmt_money(value, symbol=_currency(market))


def _pct_text(value) -> str:
    if value is None or pd.isna(value):
        return "N/D"
    return f"{float(value):+.2f}%"


def _pct_html(value) -> str:
    if value is None or pd.isna(value):
        return '<span style="opacity:.72;font-weight:800">N/D</span>'
    color = "#dc2626" if float(value) < 0 else "inherit"
    return f'<span style="color:{color};font-weight:800">{float(value):+.2f}%</span>'


def _payload(row) -> dict:
    value = row.get("payload")
    return value if isinstance(value, dict) else {}


def _field(row, column: str, *payload_aliases: str):
    value = row.get(column)
    try:
        if value is not None and not pd.isna(value):
            return value
    except Exception:
        if value is not None:
            return value
    payload = _payload(row)
    for key in payload_aliases:
        candidate = payload.get(key)
        try:
            if candidate is not None and not pd.isna(candidate):
                return candidate
        except Exception:
            if candidate is not None:
                return candidate
    return None


def _requirements(row) -> dict:
    value = _payload(row).get("_buy_requirements")
    return value if isinstance(value, dict) else {}


def _num(value):
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def _bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    return None


def _tri_and(*values):
    if any(v is False for v in values):
        return False
    if values and all(v is True for v in values):
        return True
    return None


def _gt(a, b):
    return None if a is None or b is None else a > b


def _ge(a, b):
    return None if a is None or b is None else a >= b


def _status_icon(value) -> str:
    return "✅" if value is True else "❌" if value is False else "➖"


def tv_url(row, market: str) -> str:
    ticker = str(row.get("ticker") or "").upper()
    payload = _payload(row)
    if market.upper() == "ITALY":
        ticker = ticker.replace(".MI", "")
        return f"https://www.tradingview.com/chart/?symbol=MIL:{ticker}"
    exchange = str(payload.get("exchange") or "").upper().strip()
    if exchange:
        return f"https://www.tradingview.com/chart/?symbol={exchange}:{ticker}"
    return f"https://www.tradingview.com/chart/?symbol={ticker}"


def _missing(row) -> list[str]:
    value = row.get("missing_gates")
    if isinstance(value, list):
        return [str(x).strip().lower() for x in value if str(x).strip()]
    fallback = _payload(row).get("prebuy_missing")
    return [str(x).strip().lower() for x in fallback] if isinstance(fallback, list) else []


def _hard_blockers(row) -> list[str]:
    value = _payload(row).get("prebuy_hard_blockers")
    return [str(x) for x in value] if isinstance(value, list) else []


def _is_missing(missing: list[str], *aliases: str) -> bool:
    normalized = {x.replace("-", "_").replace(" ", "_") for x in missing}
    return any(alias.lower().replace("-", "_").replace(" ", "_") in normalized for alias in aliases)


def _req_num_text(value, prefix="≥") -> str:
    number = _num(value)
    return "N/D" if number is None else f"{prefix}{number:.2f}"


def _gate_rows(row, market: str) -> list[dict]:
    payload = _payload(row)
    req = _requirements(row)
    missing = _missing(row)

    score = _num(row.get("opportunity_score"))
    rr1 = _num(_field(row, "net_rr_tp1", "net_rr_tp1", "rr_net_tp1"))
    rr2 = _num(_field(row, "net_rr_tp2", "net_rr_tp2", "rr_net_tp2", "net_rr", "rr"))
    trigger = str(_field(row, "trigger", "trigger_state", "trigger") or "N/D").upper().replace("_", " ")
    technical = str(payload.get("technical_state") or payload.get("setup_state") or "N/D").replace("_", " ")
    qty = _num(payload.get("qty") or payload.get("shares"))

    score_min = _num(req.get("score_min"))
    rr1_min = _num(req.get("rr_tp1_min"))
    rr2_min = _num(req.get("rr_tp2_min"))

    score_ok = not _is_missing(missing, "score") if score_min is None else score is not None and score >= score_min
    rr1_ok = not _is_missing(missing, "rr_tp1") if rr1_min is None else rr1 is not None and rr1 >= rr1_min
    rr2_ok = not _is_missing(missing, "rr_tp2", "rr") if rr2_min is None else rr2 is not None and rr2 >= rr2_min
    trigger_ok = trigger == str(req.get("trigger_required") or "CONFIRMED").upper().replace("_", " ")
    structure_ok = not _is_missing(missing, "structure", "technical", "trend")
    sizing_ok = not _is_missing(missing, "sizing", "size", "qty") and (qty is None or qty > 0)

    return [
        {"name": "Opportunity Score", "current": fmt_score(score), "requirement": _req_num_text(score_min), "ok": score_ok},
        {"name": "Net R/R TP1", "current": fmt_rr(rr1), "requirement": _req_num_text(rr1_min), "ok": rr1_ok},
        {"name": "Net R/R TP2", "current": fmt_rr(rr2), "requirement": _req_num_text(rr2_min), "ok": rr2_ok},
        {"name": "Trigger", "current": trigger, "requirement": str(req.get("trigger_required") or "CONFIRMED"), "ok": trigger_ok},
        {"name": "Structure", "current": technical, "requirement": "PASS", "ok": structure_ok},
        {"name": "Sizing", "current": f"Qty {int(qty)}" if qty is not None else "PASS/N-D", "requirement": "PASS", "ok": sizing_ok},
    ]


def _trigger_snapshot(row) -> dict:
    """Rebuild the Core trigger checklist only from the persisted Core snapshot."""
    payload = _payload(row)
    price = _num(payload.get("price"))
    if price is None:
        price = _num(row.get("signal_price"))
    last_open = _num(payload.get("last_open"))
    prev_close = _num(payload.get("prev_close"))
    sma20 = _num(payload.get("ma20"))
    rvol = _num(payload.get("relative_volume"))
    zone_low = _num(_field(row, "buy_zone_low", "buy_zone_low", "buy_range_low", "entry_low"))
    zone_high = _num(_field(row, "buy_zone_high", "buy_zone_high", "buy_range_high", "entry_high"))

    in_zone = _bool(payload.get("in_buy_zone"))
    if in_zone is None and price is not None and zone_low is not None and zone_high is not None:
        in_zone = zone_low <= price <= zone_high

    price_gt_open = _gt(price, last_open)
    price_gt_prev = _gt(price, prev_close)
    rvol_080 = _ge(rvol, 0.80)
    price_gt_sma20 = _gt(price, sma20)
    rvol_100 = _ge(rvol, 1.00)

    path_a = _tri_and(in_zone, price_gt_open, price_gt_prev, rvol_080)
    path_b = _tri_and(in_zone, price_gt_sma20, rvol_100)
    confirmed = True if path_a is True or path_b is True else False if path_a is False and path_b is False else None

    return {
        "price": price,
        "last_open": last_open,
        "prev_close": prev_close,
        "sma20": sma20,
        "rvol": rvol,
        "zone_low": zone_low,
        "zone_high": zone_high,
        "in_zone": in_zone,
        "price_gt_open": price_gt_open,
        "price_gt_prev": price_gt_prev,
        "rvol_080": rvol_080,
        "price_gt_sma20": price_gt_sma20,
        "rvol_100": rvol_100,
        "path_a": path_a,
        "path_b": path_b,
        "confirmed": confirmed,
        "reason": payload.get("trigger_reason"),
    }


def _render_trigger_confirmation(row, market: str) -> None:
    snap = _trigger_snapshot(row)
    p = snap["price"]
    op = snap["last_open"]
    prev = snap["prev_close"]
    sma20 = snap["sma20"]
    rvol = snap["rvol"]

    st.markdown("**TRIGGER CONFIRMATION · CORE SNAPSHOT**")
    st.caption("Usa i valori dello stesso Master Scan che ha prodotto WAITING/CONFIRMED; il Current live mostrato sopra è solo contesto.")

    zone_text = "YES" if snap["in_zone"] is True else "NO" if snap["in_zone"] is False else "N/D"
    zone_ref = f"{_money(snap['zone_low'], market)} – {_money(snap['zone_high'], market)}"
    st.markdown(f"{_status_icon(snap['in_zone'])} **In Buy Zone:** {zone_text} <span style='opacity:.68'>({html.escape(zone_ref)} required)</span>", unsafe_allow_html=True)

    st.markdown("**Path A · Positive Candle + Volume**")
    st.markdown(
        f"{_status_icon(snap['price_gt_open'])} Price {_money(p, market)} > Open {_money(op, market)}  \\n"
        f"{_status_icon(snap['price_gt_prev'])} Price {_money(p, market)} > Previous Close {_money(prev, market)}  \\n"
        f"{_status_icon(snap['rvol_080'])} Relative Volume {('N/D' if rvol is None else f'{rvol:.2f}')} (≥0.80)"
    )
    path_a_text = "PASS" if snap["path_a"] is True else "NOT CONFIRMED" if snap["path_a"] is False else "N/D"
    st.caption(f"Path A: {path_a_text}")

    st.markdown("**Path B · SMA20 Reclaim + Strong Volume**")
    st.markdown(
        f"{_status_icon(snap['price_gt_sma20'])} Price {_money(p, market)} > SMA20 {_money(sma20, market)}  \\n"
        f"{_status_icon(snap['rvol_100'])} Relative Volume {('N/D' if rvol is None else f'{rvol:.2f}')} (≥1.00)"
    )
    path_b_text = "PASS" if snap["path_b"] is True else "NOT CONFIRMED" if snap["path_b"] is False else "N/D"
    st.caption(f"Path B: {path_b_text}")

    if snap["confirmed"] is True:
        st.success("Trigger condition satisfied in the persisted Core snapshot: Path A OR Path B passed while price was in Buy Zone.")
    elif snap["confirmed"] is False:
        st.warning("Per diventare CONFIRMED: il prezzo deve restare in Buy Zone e deve passare Path A oppure Path B.")
    else:
        st.info("Trigger details partially N/D in this snapshot. The next Master Scan will refresh the persisted Core values.")

    if snap.get("reason"):
        st.caption(f"Core trigger reason: {snap['reason']}")


def _render_buy_checklist(row, market: str) -> None:
    gates = _gate_rows(row, market)
    passed = sum(1 for gate in gates if gate["ok"])
    total = len(gates)
    missing_names = [gate["name"] for gate in gates if not gate["ok"]]

    st.markdown("**BUY GATES**")
    for gate in gates:
        icon = "✅" if gate["ok"] else "❌"
        st.markdown(
            f"{icon} **{gate['name']}:** {html.escape(str(gate['current']))} "
            f"<span style='opacity:.68'>({html.escape(str(gate['requirement']))})</span>",
            unsafe_allow_html=True,
        )
        if gate["name"] == "Trigger":
            _render_trigger_confirmation(row, market)

    readiness_color = "#15803d" if passed == total else "#b45309"
    st.markdown(
        f"<div style='margin:.45rem 0 .25rem 0;padding:.45rem .6rem;border-radius:8px;"
        f"background:rgba(128,128,128,.06);font-weight:750'>"
        f"BUY Readiness: <span style='color:{readiness_color}'>{passed}/{total} gates passed</span></div>",
        unsafe_allow_html=True,
    )
    if missing_names:
        st.write(f"To become BUY: **{', '.join(missing_names)}**")
    else:
        st.write("BUY gate checklist: **PASS**. Final executable state remains the Core decision BUY NOW / BUY LIMIT.")

    blockers = _hard_blockers(row)
    if blockers:
        st.error(f"Hard Blockers: {', '.join(blockers)}")

    req = _requirements(row)
    if not req:
        st.caption("Reference thresholds are not stored in this older snapshot. They will populate automatically after the next Master Scan.")
    elif req.get("market_regime"):
        st.caption(f"Reference thresholds from Core run · Market Regime: {req.get('market_regime')}")


def _reason(row) -> str:
    state = str(row.get("operational_state") or "N/D")
    signal_class = str(row.get("signal_class") or "N/D")
    missing = _missing(row)
    missing_txt = ", ".join(missing) if missing else "none"
    if signal_class == "BUY NOW":
        return "Core decision is BUY NOW: tutti i gate richiesti dal motore risultano superati."
    if signal_class == "BUY LIMIT":
        return "Core decision is BUY LIMIT: setup operativo valido al prezzo limite definito dal motore."
    if state == "READY_FOR_TRIGGER":
        return "PRE-BUY HIGH: i gate non-trigger risultano validi; manca la conferma del trigger."
    if state == "SCORE_MARGINAL":
        return "PRE-BUY HIGH Italy: R/R e struttura sono validi, ma lo score è ancora marginale rispetto alla soglia BUY."
    return f"PRE-BUY HIGH indica readiness elevata, non BUY eseguibile. Missing gates: {missing_txt}."


try:
    opportunities = load_core_high_conviction(500, active_only=True)
except Exception as exc:
    text = str(exc)
    if "core_high_conviction_signals" in text or "PGRST205" in text:
        st.info("Core feed not initialized yet. Run SQL 06 in Supabase, then execute one Master Scan for USA and one for Italy.")
        a, b, c = st.columns(3)
        a.metric("Status", "NOT INITIALIZED")
        b.metric("Required Step", "SQL 06")
        c.metric("Next Step", "MASTER SCAN")
    else:
        st.warning("Core high-conviction feed is temporarily unavailable. The Core engine remains independent from this dashboard.")
    st.stop()

if opportunities.empty:
    st.info("No active BUY / PRE-BUY HIGH opportunities. This is a valid Core outcome.")
    st.stop()

if "created_at" in opportunities:
    opportunities["_created"] = pd.to_datetime(opportunities["created_at"], errors="coerce", utc=True)
    opportunities = opportunities.sort_values("_created", ascending=False)

for market in ["USA", "ITALY"]:
    block = opportunities[opportunities["market"].fillna("").astype(str).str.upper() == market].copy()
    st.markdown(f"## {market}")
    if block.empty:
        st.caption("No active high-conviction opportunity.")
        continue

    block = block.drop_duplicates(subset=["ticker"], keep="first")
    snapshots = [intraday_snapshot(str(row.get("ticker")), market) for _, row in block.iterrows()]
    block["Current Price"] = [x[0] for x in snapshots]
    block["Min"] = [x[1] for x in snapshots]
    block["Max"] = [x[2] for x in snapshots]
    block["Oggi %"] = [x[3] for x in snapshots]
    block["Company"] = block.get("company_name", pd.Series(index=block.index)).fillna("N/D")
    block["Status"] = block.get("signal_class", pd.Series(index=block.index)).fillna("N/D")
    block["Buy Range"] = block.apply(lambda r: f"{_money(_field(r, 'buy_zone_low', 'buy_zone_low', 'buy_range_low', 'entry_low'), market)} – {_money(_field(r, 'buy_zone_high', 'buy_zone_high', 'buy_range_high', 'entry_high'), market)}", axis=1)
    block["Min / Max"] = block.apply(lambda r: f"{_money(r.get('Min'), market)} – {_money(r.get('Max'), market)}", axis=1)
    block["Entry"] = block.apply(lambda r: _money(_field(r, "entry", "entry", "ideal_entry", "entry_price", "proposed_entry"), market), axis=1)
    block["SL"] = block.apply(lambda r: _money(_field(r, "stop", "stop", "stop_loss", "proposed_stop"), market), axis=1)
    block["TP1"] = block.apply(lambda r: _money(_field(r, "tp1", "tp1", "target1"), market), axis=1)
    block["TP2"] = block.apply(lambda r: _money(_field(r, "tp2", "tp2", "target2", "target", "proposed_target"), market), axis=1)
    block["Net R/R"] = block.apply(lambda r: fmt_rr(_field(r, "net_rr_tp2", "net_rr_tp2", "rr_net_tp2", "net_rr", "rr")), axis=1)
    block["Chart"] = block.apply(lambda r: tv_url(r, market), axis=1)

    table = block[["ticker", "Company", "Status", "Current Price", "Oggi %", "Min / Max", "Buy Range", "Entry", "SL", "TP1", "TP2", "Net R/R", "Chart"]].copy()
    table = table.rename(columns={"ticker": "Ticker"})
    table["Current Price"] = table["Current Price"].map(lambda v: _money(v, market))
    table["Oggi %"] = table["Oggi %"].map(_pct_text)

    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
        column_config={"Chart": st.column_config.LinkColumn("TradingView", display_text="Open")},
    )

    info_cols = st.columns(min(len(block), 4))
    for idx, (_, row) in enumerate(block.iterrows()):
        with info_cols[idx % len(info_cols)]:
            ticker = str(row.get("ticker", "N/D"))
            with st.popover(f"ℹ️ {ticker}", use_container_width=True):
                st.markdown(f"**{ticker} · {row.get('company_name') or 'N/D'}**")
                st.write(f"Status: **{row.get('signal_class', 'N/D')}**")
                st.markdown(
                    '<div style="line-height:1.7">'
                    f'<b>Current:</b> {html.escape(_money(row.get("Current Price"), market))} &nbsp;·&nbsp; '
                    f'<b>Min:</b> {html.escape(_money(row.get("Min"), market))} &nbsp;·&nbsp; '
                    f'<b>Max:</b> {html.escape(_money(row.get("Max"), market))} &nbsp;·&nbsp; '
                    f'<b>Oggi:</b> {_pct_html(row.get("Oggi %"))}'
                    '</div>',
                    unsafe_allow_html=True,
                )
                st.write(
                    f"Entry / Max Buy: **{_money(_field(row, 'entry', 'entry', 'ideal_entry', 'entry_price', 'proposed_entry'), market)} / "
                    f"{_money(_field(row, 'max_buy', 'max_buy', 'max_entry'), market)}**"
                )
                st.write(
                    f"Stop / TP1 / TP2: **{_money(_field(row, 'stop', 'stop', 'stop_loss', 'proposed_stop'), market)} / "
                    f"{_money(_field(row, 'tp1', 'tp1', 'target1'), market)} / "
                    f"{_money(_field(row, 'tp2', 'tp2', 'target2', 'target', 'proposed_target'), market)}**"
                )
                if pd.notna(row.get("prebuy_score")):
                    req = _requirements(row)
                    pb_req = _num(req.get("prebuy_high_min"))
                    pb_ref = f" (≥{pb_req:.0f}/10 for PRE-BUY HIGH)" if pb_req is not None else ""
                    st.write(f"PRE-BUY Score: **{int(float(row.get('prebuy_score')))}/10**{pb_ref}")
                if pd.notna(row.get("quality_score")):
                    st.write(f"Quality Score: **{fmt_score(row.get('quality_score'))}**")
                st.write(f"Operational: **{row.get('operational_state') or 'N/D'}**")

                st.divider()
                _render_buy_checklist(row, market)

                missing = _missing(row)
                if any("rr" in x for x in missing):
                    st.warning("R/R gate non ancora superato: PRE-BUY HIGH indica readiness elevata, non un BUY eseguibile.")
                st.info(_reason(row))
                snapshot = pd.to_datetime(row.get("created_at"), errors="coerce", utc=True)
                snapshot_text = snapshot.strftime("%d/%m/%Y %H:%M UTC") if pd.notna(snapshot) else "N/D"
                st.caption(f"Snapshot: {snapshot_text} · Run {row.get('run_id', 'N/D')}")

st.caption("Source: Core high-conviction persistence. Current/Min/Max/% Oggi are cached market-data context; Signal Price remains stored in the DB for audit.")
