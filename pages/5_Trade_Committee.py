from __future__ import annotations

from datetime import datetime
import pandas as pd
import streamlit as st

from trade_committee import run_committee
from trade_committee.charting import build_price_chart
from trade_committee.input_resolver import resolve_many
from trade_committee.persistence import fail_run, finish_run, make_run_id, start_run, ticker_history

st.set_page_config(page_title="Trade Committee", page_icon="🔬", layout="wide")
st.title("🔬 Trade Committee · Pre-Trade Check")
st.caption("Analisi manuale indipendente prima di un eventuale acquisto. CORE invariato, nessun ordine automatico.")

raw = st.text_area(
    "Titolo/i da analizzare",
    placeholder="Es. TSM, NVIDIA, Novo Nordisk\nSeparatore principale: virgola",
    height=82,
    help="Puoi usare ticker oppure nome società. Per più titoli usa la virgola. Sono accettati anche punto e virgola e ritorno a capo. Massimo 10 titoli per batch.",
)
start = st.button("🔬 ANALIZZA", type="primary", use_container_width=False, disabled=not bool(raw.strip()))
st.caption("Ricerca: ticker o nome società · Multi-titolo: **virgola (,)** · accettati anche `;` e una riga per titolo.")

if "trade_committee_results" not in st.session_state:
    st.session_state["trade_committee_results"] = {}

if start:
    try:
        resolved = resolve_many(raw, max_symbols=10)
    except Exception as exc:
        st.error(f"Input non valido: {exc}")
        resolved = []

    if resolved:
        batch_progress = st.progress(0, text=f"0/{len(resolved)} titoli analizzati")
        batch_results = {}
        for idx, item in enumerate(resolved, start=1):
            ticker = item.ticker
            run_id = make_run_id(ticker)
            start_run(run_id, ticker)
            with st.status(f"{ticker} · analisi in corso", expanded=False) as status:
                step_box = st.empty()
                def cb(step, label, state):
                    step_box.caption(f"{step}/12 · {label} · {state}")
                try:
                    result = run_committee(ticker, cb)
                    result["run_id"] = run_id
                    result["resolved_name"] = item.name
                    result["input_query"] = item.query
                    result["input_source"] = item.source
                    finish_run(run_id, result)
                    batch_results[ticker] = result
                    status.update(label=f"{ticker} · completato", state="complete")
                except Exception as exc:
                    fail_run(run_id, exc)
                    status.update(label=f"{ticker} · fallito", state="error")
                    st.error(f"{ticker}: {type(exc).__name__}: {exc}")
            batch_progress.progress(idx / len(resolved), text=f"{idx}/{len(resolved)} titoli analizzati")
        st.session_state["trade_committee_results"] = batch_results

results = st.session_state.get("trade_committee_results") or {}


def money(v):
    return f"{v:.2f}" if isinstance(v, (int, float)) else "N/D"


def ratio(v):
    return f"{v:.2f}" if isinstance(v, (int, float)) else "N/D"


def delta(v):
    if not isinstance(v, (int, float)):
        return "-"
    return f"{v:+.2f}"


def render_history(ticker: str):
    history, err = ticker_history(ticker, limit=20)
    st.markdown("### Storico analisi")
    st.caption("Confronta cosa proponeva il Committee nelle analisi precedenti e cosa è cambiato nelle esecuzioni successive.")
    if err:
        st.info("Storico persistente non disponibile finché il database Trade Committee non è configurato/applicato.")
        return
    if not history:
        st.info("Questa è la prima analisi persistita per il titolo.")
        return

    rows = []
    for h in history:
        when = str(h.get("when") or "")
        try:
            when = datetime.fromisoformat(when.replace("Z", "+00:00")).astimezone().strftime("%d/%m/%Y %H:%M")
        except Exception:
            pass
        rows.append({
            "Quando": when,
            "Verdetto": h.get("verdict") or h.get("status"),
            "Prezzo": h.get("price"),
            "Entry": h.get("entry"),
            "SL": h.get("stop"),
            "TP1": h.get("tp1"),
            "TP2": h.get("tp2"),
            "R/R TP2": h.get("rr2_net"),
            "Score": h.get("committee_score"),
            "Confidence": h.get("data_confidence"),
            "Δ Prezzo": h.get("delta_price"),
            "Δ Entry": h.get("delta_entry"),
            "Δ SL": h.get("delta_stop"),
            "Δ TP1": h.get("delta_tp1"),
            "Δ TP2": h.get("delta_tp2"),
            "Cambio verdetto": "SÌ" if h.get("verdict_changed") else "",
        })
    frame = pd.DataFrame(rows)
    st.dataframe(
        frame,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Prezzo": st.column_config.NumberColumn(format="%.2f"),
            "Entry": st.column_config.NumberColumn(format="%.2f"),
            "SL": st.column_config.NumberColumn(format="%.2f"),
            "TP1": st.column_config.NumberColumn(format="%.2f"),
            "TP2": st.column_config.NumberColumn(format="%.2f"),
            "R/R TP2": st.column_config.NumberColumn(format="%.2f"),
            "Score": st.column_config.NumberColumn(format="%.1f"),
            "Confidence": st.column_config.NumberColumn(format="%.1f%%"),
            "Δ Prezzo": st.column_config.NumberColumn(format="%+.2f"),
            "Δ Entry": st.column_config.NumberColumn(format="%+.2f"),
            "Δ SL": st.column_config.NumberColumn(format="%+.2f"),
            "Δ TP1": st.column_config.NumberColumn(format="%+.2f"),
            "Δ TP2": st.column_config.NumberColumn(format="%+.2f"),
        },
    )


def render_result(r: dict):
    ticker = r["ticker"]
    name = r.get("resolved_name")
    title = f"{ticker} · {name}" if name else ticker
    st.subheader(title)

    trade = r.get("trade_plan") or {}
    a, b, c, d, e, f = st.columns(6)
    a.metric("Verdetto", r.get("verdict", "N/D"))
    b.metric("Prezzo", money(r.get("price")))
    c.metric("Entry", money(trade.get("entry")))
    d.metric("Stop Loss", money(trade.get("stop")))
    e.metric("TP1", money(trade.get("tp1")))
    f.metric("TP2", money(trade.get("tp2")))

    a2, b2, c2, d2 = st.columns(4)
    a2.metric("Committee Score", f"{r.get('committee_score', 0):.1f}/100")
    b2.metric("Data Confidence", f"{r.get('data_confidence', 0):.0f}%")
    c2.metric("R/R netto TP2", ratio(trade.get("rr2_net")))
    run_at = r.get("run_at")
    try:
        run_label = datetime.fromisoformat(str(run_at).replace("Z", "+00:00")).astimezone().strftime("%d/%m/%Y %H:%M")
    except Exception:
        run_label = str(run_at or "N/D")
    d2.metric("Analizzato il", run_label)

    verdict = r.get("verdict")
    reason = r.get("decision_reason") or ""
    if verdict == "APPROVE":
        st.success(f"🟢 {verdict} · {reason}")
    elif str(verdict).startswith("REJECT"):
        st.error(f"🔴 {verdict} · {reason}")
    else:
        st.warning(f"🟡 {verdict} · {reason}")
    if r.get("hard_reasons"):
        st.caption("Blocchi: " + " · ".join(r["hard_reasons"]))

    chart = build_price_chart(ticker, entry=trade.get("entry"), stop=trade.get("stop"), tp1=trade.get("tp1"), tp2=trade.get("tp2"))
    if chart is not None:
        st.plotly_chart(chart, use_container_width=True)

    yes, no = st.columns(2)
    with yes:
        st.markdown("#### Perché è interessante")
        for item in r.get("bull_case") or ["Nessuna conferma forte rilevata"]:
            st.write(f"• {item}")
    with no:
        st.markdown("#### Cosa non convince")
        for item in r.get("bear_case") or ["Nessuna criticità materiale rilevata"]:
            st.write(f"• {item}")

    render_history(ticker)

    with st.expander("Approfondimento", expanded=False):
        cov = r.get("coverage_summary") or {}
        st.caption(f"Copertura: {cov.get('real', 0)} REAL · {cov.get('partial', 0)} PARTIAL · {cov.get('missing', 0)} N/D/FAILED")
        tabs = st.tabs(["Fondamentali", "Catalizzatori / Ownership", "SEC / Mercato", "Portafoglio / Data Quality"])
        with tabs[0]:
            st.dataframe((r.get("quality") or {}).get("checks", []), hide_index=True, use_container_width=True)
            notes = (r.get("valuation") or {}).get("notes", [])
            if notes:
                st.write(" · ".join(notes))
        with tabs[1]:
            sentiment = r.get("sentiment") or {}
            st.dataframe([sentiment.get("analyst", {})], hide_index=True, use_container_width=True)
            if sentiment.get("news"):
                st.dataframe(sentiment["news"], hide_index=True, use_container_width=True)
        with tabs[2]:
            sec = r.get("sec") or {}
            st.write(f"SEC EDGAR: **{sec.get('status', 'N/D')}**")
            if sec.get("filings"):
                st.dataframe(sec["filings"], hide_index=True, use_container_width=True)
            ctx = r.get("market_context") or {}
            st.json({"benchmark": ctx.get("benchmark"), "sector": ctx.get("sector"), "relative": ctx.get("relative")})
        with tabs[3]:
            portfolio = r.get("portfolio") or {}
            st.write(f"Già in portafoglio: **{'SÌ' if portfolio.get('already_owned') else 'NO'}**")
            st.caption(portfolio.get("note", ""))
            st.dataframe(r.get("coverage", []), hide_index=True, use_container_width=True)


if results:
    st.divider()
    if len(results) == 1:
        render_result(next(iter(results.values())))
    else:
        st.subheader(f"Risultati batch · {len(results)} titoli")
        summary = []
        for ticker, r in results.items():
            trade = r.get("trade_plan") or {}
            summary.append({
                "Ticker": ticker,
                "Nome": r.get("resolved_name") or "",
                "Verdetto": r.get("verdict"),
                "Prezzo": r.get("price"),
                "Entry": trade.get("entry"),
                "SL": trade.get("stop"),
                "TP1": trade.get("tp1"),
                "TP2": trade.get("tp2"),
                "R/R TP2": trade.get("rr2_net"),
                "Score": r.get("committee_score"),
                "Confidence": r.get("data_confidence"),
            })
        st.dataframe(summary, hide_index=True, use_container_width=True)
        tabs = st.tabs(list(results.keys()))
        for tab, r in zip(tabs, results.values()):
            with tab:
                render_result(r)

st.caption(f"Trade Committee V2 · Updated: {datetime.now().astimezone().strftime('%d/%m/%Y %H:%M:%S %Z')}")
