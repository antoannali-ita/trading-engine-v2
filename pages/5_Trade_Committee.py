from __future__ import annotations

from datetime import datetime
import streamlit as st

from trade_committee import run_committee
from trade_committee.charting import build_price_chart

st.set_page_config(page_title="Trade Committee", page_icon="🔬", layout="wide")
st.title("🔬 Trade Committee · Pre-Trade Check")
st.caption("LAB-RESEARCH-001 · Conferma indipendente prima di un eventuale acquisto. Nessun ordine automatico, CORE invariato.")

c1, c2 = st.columns([4, 1])
with c1:
    ticker = st.text_input("Ticker", placeholder="Es. ORCL, GSK, CSCO").strip().upper()
with c2:
    st.write("")
    start = st.button("🔬 ANALIZZA", type="primary", use_container_width=True, disabled=not bool(ticker))

if start:
    progress = st.progress(0, text="Avvio Trade Committee...")
    status = st.status(f"Analisi {ticker} in corso", expanded=True)

    def cb(step, label, state):
        progress.progress(step / 12, text=f"{step}/12 · {label}")
        icon = "✅" if state == "REAL" else ("🟡" if state in {"PARTIAL", "N/A"} else "⚪")
        status.write(f"{icon} {step:02d} · {label} · {state}")

    try:
        result = run_committee(ticker, cb)
        status.update(label=f"Trade Committee {ticker} completato", state="complete", expanded=False)
        progress.progress(1.0, text="Analisi completata")
        st.session_state["trade_committee_result"] = result
    except Exception as exc:
        status.update(label=f"Analisi {ticker} fallita", state="error")
        st.error(f"Errore: {type(exc).__name__}: {exc}")

r = st.session_state.get("trade_committee_result")
if r:
    st.divider()
    st.subheader(f"{r['ticker']} · Decisione")
    a, b, c, d, e = st.columns(5)
    a.metric("Verdetto", r["verdict"])
    b.metric("Committee Score", f"{r['committee_score']}/100")
    c.metric("Data Confidence", f"{r['data_confidence']:.0f}%")
    d.metric("Prezzo", f"{r['price']:.2f}" if r.get("price") else "N/D")
    cov = r.get("coverage_summary", {})
    e.metric("Copertura", f"{cov.get('real', 0)} reali / {cov.get('partial', 0)} parziali")

    if r["verdict"] == "APPROVE":
        st.success("🟢 APPROVE · Il Committee conferma il candidato. La decisione e l'ordine restano manuali.")
    elif r["verdict"] == "WAIT":
        st.warning("🟡 WAIT · Non comprerei adesso: servono condizioni o dati migliori.")
    else:
        st.error("🔴 REJECT · Il Committee non conferma l'acquisto.")
    if r.get("hard_reasons"):
        st.caption("Gate / motivi di blocco: " + " · ".join(r["hard_reasons"]))

    trade = r.get("trade_plan", {})
    chart = build_price_chart(
        r["ticker"], entry=trade.get("entry"), stop=trade.get("stop"), tp1=trade.get("tp1"), tp2=trade.get("tp2")
    )
    if chart is not None:
        st.plotly_chart(chart, use_container_width=True)

    st.subheader("Piano operativo indicativo")
    def money(v):
        return f"{v:.2f}" if isinstance(v, (int, float)) else "N/D"
    def ratio(v):
        return f"{v:.2f}" if isinstance(v, (int, float)) else "N/D"

    earnings = (r.get("earnings") or {}).get("next", {})
    plan_rows = [
        {"Voce": "Entry", "Valore": money(trade.get("entry"))},
        {"Voce": "Stop", "Valore": money(trade.get("stop"))},
        {"Voce": "TP1", "Valore": money(trade.get("tp1"))},
        {"Voce": "TP2", "Valore": money(trade.get("tp2"))},
        {"Voce": "R/R netto TP1", "Valore": ratio(trade.get("rr1_net"))},
        {"Voce": "R/R netto TP2", "Valore": ratio(trade.get("rr2_net"))},
        {"Voce": "Quantità su $2.500", "Valore": trade.get("qty", "N/D")},
        {"Voce": "Loss max stimata", "Valore": money(trade.get("loss_max"))},
        {"Voce": "Earnings", "Valore": f"{earnings.get('date', 'N/D')} · {earnings.get('days')} giorni" if earnings.get("days") is not None else earnings.get("date", "N/D")},
    ]
    st.dataframe(plan_rows, hide_index=True, use_container_width=True)
    st.caption(trade.get("method", ""))

    yes, no = st.columns(2)
    with yes:
        st.markdown("### Perché sì")
        for item in r.get("bull_case") or ["Nessuna conferma forte"]:
            st.write(f"• {item}")
    with no:
        st.markdown("### Perché no")
        for item in r.get("bear_case") or ["Nessuna criticità forte"]:
            st.write(f"• {item}")

    st.subheader("Copertura reale dell'analisi")
    st.caption("REAL = check eseguito con la fonte indicata · PARTIAL = copertura incompleta · N/A = non applicabile · N/D = non disponibile.")
    st.dataframe(r.get("coverage", []), hide_index=True, use_container_width=True)

    tab1, tab2, tab3, tab4 = st.tabs(["Fondamentali", "Catalizzatori & ownership", "SEC / Mercato", "Portafoglio & Data Quality"])

    with tab1:
        st.markdown("#### Qualità finanziaria")
        st.dataframe((r.get("quality") or {}).get("checks", []), hide_index=True, use_container_width=True)
        st.markdown("#### Valutazione")
        st.write(" · ".join((r.get("valuation") or {}).get("notes", [])) or "N/D")
        st.markdown("#### Metriche")
        labels = {
            "marketCap": "Market Cap", "trailingPE": "P/E", "forwardPE": "Forward P/E", "pegRatio": "PEG",
            "enterpriseToEbitda": "EV/EBITDA", "returnOnEquity": "ROE", "currentRatio": "Current Ratio",
            "debtToEquity": "Debt/Equity", "freeCashflow": "FCF", "operatingCashflow": "OCF",
            "revenueGrowth": "Revenue Growth", "earningsGrowth": "Earnings Growth", "profitMargins": "Profit Margin",
            "fcfYield": "FCF Yield",
        }
        rows = [{"Metrica": labels.get(k, k), "Valore": v if v is not None else "N/D"} for k, v in (r.get("fundamentals") or {}).items() if k in labels]
        st.dataframe(rows, hide_index=True, use_container_width=True)

    with tab2:
        analyst = (r.get("sentiment") or {}).get("analyst", {})
        st.markdown("#### Analisti")
        st.dataframe([analyst], hide_index=True, use_container_width=True)
        st.markdown("#### Short / istituzionali")
        st.dataframe([(r.get("sentiment") or {}).get("short", {})], hide_index=True, use_container_width=True)
        news = (r.get("sentiment") or {}).get("news", [])
        if news:
            st.markdown("#### News recenti")
            st.dataframe(news, hide_index=True, use_container_width=True)
        insiders = (r.get("sentiment") or {}).get("insiders", [])
        if insiders:
            st.markdown("#### Insider transactions")
            st.dataframe(insiders, hide_index=True, use_container_width=True)
        institutions = (r.get("sentiment") or {}).get("institutions", [])
        if institutions:
            st.markdown("#### Institutional holders")
            st.dataframe(institutions, hide_index=True, use_container_width=True)

    with tab3:
        sec = r.get("sec", {})
        st.markdown(f"#### SEC EDGAR · {sec.get('status', 'N/D')}")
        st.caption(sec.get("note", ""))
        if sec.get("filings"):
            st.dataframe(sec["filings"], hide_index=True, use_container_width=True)
        ctx = r.get("market_context", {})
        st.markdown("#### Forza relativa")
        rel = ctx.get("relative", {})
        st.dataframe([{"Benchmark": ctx.get("benchmark"), "Settore": ctx.get("sector"), "ETF settore": ctx.get("sector_ticker"), "RS 1m": rel.get("1m"), "RS 3m": rel.get("3m"), "RS 6m": rel.get("6m")}], hide_index=True, use_container_width=True)

    with tab4:
        st.markdown("#### Contesto portafoglio Production")
        portfolio = r.get("portfolio", {})
        st.write(f"Già presente: **{'SÌ' if portfolio.get('already_owned') else 'NO'}**")
        if portfolio.get("already_owned"):
            st.json(portfolio.get("position"))
        st.write(f"Peso stimato: **{(portfolio.get('estimated_weight') or 0)*100:.1f}%**")
        st.caption(portfolio.get("note", ""))
        st.markdown("#### Financial rigor")
        rigor_rows = [{"Check": k, **v} for k, v in (r.get("financial_rigor") or {}).items()]
        st.dataframe(rigor_rows, hide_index=True, use_container_width=True)
        st.markdown("#### Cross-check TradingView")
        st.json(r.get("tradingview_crosscheck", {}))

    st.caption(r.get("guardrail", ""))

st.caption(f"LAB-RESEARCH-001 · V2 · Updated: {datetime.now().astimezone().strftime('%d/%m/%Y %H:%M:%S %Z')}")
