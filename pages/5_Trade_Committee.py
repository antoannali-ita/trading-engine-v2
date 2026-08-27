from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from trade_committee import run_committee
from trade_committee.charting import build_price_chart
from trade_committee.input_resolver import resolve_many


st.set_page_config(page_title="Trade Committee", page_icon="🔬", layout="wide")
st.title("🔬 Trade Committee · Pre-Trade Check")
st.caption("Analisi manuale indipendente prima di un eventuale acquisto. CORE invariato. Nessun ordine automatico.")

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
            with st.status(f"{ticker} · analisi in corso", expanded=False) as status:
                step_box = st.empty()

                def cb(step, label, state):
                    step_box.caption(f"{step}/12 · {label} · {state}")

                try:
                    result = run_committee(ticker, cb)
                    result["resolved_name"] = item.name
                    result["input_query"] = item.query
                    result["input_source"] = item.source
                    batch_results[ticker] = result
                    status.update(label=f"{ticker} · completato", state="complete")
                except Exception as exc:
                    status.update(label=f"{ticker} · fallito", state="error")
                    st.error(f"{ticker}: {type(exc).__name__}: {exc}")
            batch_progress.progress(idx / len(resolved), text=f"{idx}/{len(resolved)} titoli analizzati")
        st.session_state["trade_committee_results"] = batch_results

results = st.session_state.get("trade_committee_results") or {}


def money(v):
    return f"{v:.2f}" if isinstance(v, (int, float)) else "N/D"


def ratio(v):
    return f"{v:.2f}" if isinstance(v, (int, float)) else "N/D"


def render_result(r: dict):
    ticker = r["ticker"]
    name = r.get("resolved_name")
    title = f"{ticker} · {name}" if name else ticker
    st.subheader(title)

    trade = r.get("trade_plan") or {}
    a, b, c, d, e, f = st.columns(6)
    a.metric("Verdetto", r.get("verdict", "N/D"))
    b.metric("Prezzo", money(r.get("price")))
    c.metric("Entry CORE", money(trade.get("entry")))
    d.metric("Stop Loss", money(trade.get("stop")))
    e.metric("TP1", money(trade.get("tp1")))
    f.metric("TP2", money(trade.get("tp2")))

    a2, b2, c2, d2, e2 = st.columns(5)
    a2.metric("Trade Validation Score", f"{r.get('trade_validation_score', 0):.1f}/100")
    b2.metric("Core Data Confidence", f"{r.get('core_data_confidence', 0):.0f}%")
    c2.metric("Enrichment Coverage", f"{r.get('enrichment_coverage', 0):.0f}%")
    d2.metric("R/R netto TP2", ratio(trade.get("rr2_net")))
    run_at = r.get("run_at")
    try:
        run_label = datetime.fromisoformat(str(run_at).replace("Z", "+00:00")).astimezone().strftime("%d/%m/%Y %H:%M")
    except Exception:
        run_label = str(run_at or "N/D")
    e2.metric("Analizzato il", run_label)

    verdict = str(r.get("verdict") or "N/D")
    reason = r.get("decision_reason") or ""
    if verdict in {"APPROVE", "APPROVE_WITH_WARNING"}:
        st.success(f"🟢 {verdict} · {reason}")
    elif verdict.startswith("REJECT"):
        st.error(f"🔴 {verdict} · {reason}")
    else:
        st.warning(f"🟡 {verdict} · {reason}")

    if r.get("hard_reasons"):
        st.caption("Hard veto: " + " · ".join(r["hard_reasons"]))

    if r.get("core_snapshot_authoritative"):
        st.caption(
            "CORE snapshot authoritative"
            + (f" · source: {r.get('core_snapshot_source')}" if r.get("core_snapshot_source") else "")
            + (f" · hash: {str(r.get('core_snapshot_hash'))[:12]}…" if r.get("core_snapshot_hash") else "")
        )
    else:
        st.info("Snapshot CORE non trovato: il Committee resta in modalità research e non può approvare una trade ricostruita localmente.")

    chart = build_price_chart(
        ticker,
        entry=trade.get("entry"),
        stop=trade.get("stop"),
        tp1=trade.get("tp1"),
        tp2=trade.get("tp2"),
    )
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

    with st.expander("Approfondimento", expanded=False):
        cov = r.get("coverage_summary") or {}
        st.markdown("#### Copertura reale dell'analisi")
        st.caption(
            f"{cov.get('complete', 0)} COMPLETE · "
            f"{cov.get('core_warning', 0)} CORE WARNING · "
            f"{cov.get('soft_warning', 0)} SOFT WARNING · "
            f"{cov.get('enrichment_nd', 0)} ENRICHMENT N/D · "
            f"{cov.get('hard_veto', 0)} HARD VETO"
        )

        validation = r.get("engine_validation") or {}
        if validation.get("checks"):
            st.markdown("#### Validazione tesi CORE")
            st.dataframe(validation["checks"], hide_index=True, use_container_width=True)

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
                "Validation": r.get("trade_validation_score"),
                "Core Confidence": r.get("core_data_confidence"),
                "Enrichment": r.get("enrichment_coverage"),
            })
        st.dataframe(pd.DataFrame(summary), hide_index=True, use_container_width=True)
        tabs = st.tabs(list(results.keys()))
        for tab, r in zip(tabs, results.values()):
            with tab:
                render_result(r)

st.caption(f"Trade Committee V2.2 · Updated: {datetime.now().astimezone().strftime('%d/%m/%Y %H:%M:%S %Z')}")
