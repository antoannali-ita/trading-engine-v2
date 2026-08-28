from __future__ import annotations

from engine import factor_ranker as fr


def _candidate(ticker: str, **overrides):
    base = {
        "ticker": ticker,
        "passes_survival": True,
        "price": 120.0,
        "ma50": 110.0,
        "ma200": 95.0,
        "rs_3m": 8.0,
        "rs_6m": 12.0,
        "perf3m": 15.0,
        "perf6m": 25.0,
        "quality_score": 75.0,
        "roic": 18.0,
        "roe": 22.0,
        "free_cashflow": 1_000_000.0,
        "operating_cashflow": 1_500_000.0,
        "revenue_growth": 10.0,
        "eps_growth": 15.0,
        "fcf_growth": 12.0,
        "opportunity_score": 70,
    }
    base.update(overrides)
    return base


def test_positive_revisions_improve_factor_score():
    neutral = _candidate("AAA")
    positive = _candidate(
        "BBB",
        eps_revision_30d_pct=5.0,
        eps_revision_60d_pct=7.0,
        eps_up_30d=6,
        eps_down_30d=1,
    )

    neutral_score = fr.score_candidate(neutral)
    positive_score = fr.score_candidate(positive)

    assert positive_score["factor_score"] > neutral_score["factor_score"]
    assert positive_score["factor_components"]["earnings_revisions"] is not None
    assert neutral_score["factor_components"]["earnings_revisions"] is None


def test_ranker_keeps_survival_failures_out_of_selection_pool(monkeypatch):
    candidates = [
        _candidate("GOOD"),
        _candidate("WEAK", rs_3m=-20, rs_6m=-25, perf3m=-15, perf6m=-20),
        _candidate("FAIL", passes_survival=False),
    ]
    monkeypatch.setattr(fr, "fetch_earnings_revisions", lambda ticker, cfg: {
        "eps_revision_30d_pct": None,
        "eps_revision_60d_pct": None,
        "eps_up_30d": None,
        "eps_down_30d": None,
        "earnings_revision_status": "N/D",
        "earnings_revision_source": "TEST",
    })

    result = fr.rank_candidates(candidates, {
        "factor_ranker_enabled": True,
        "factor_ranker_pool_size": 10,
        "factor_ranker_revisions_enabled": True,
        "factor_ranker_revision_top_n": 2,
    })

    tickers = [c["ticker"] for c in result["selection_pool"]]
    assert "FAIL" not in tickers
    assert tickers[0] == "GOOD"
    assert result["revision_enriched"] == 2


def test_italy_symbol_suffix_is_added_once():
    cfg = {"yfinance_suffix": ".MI"}
    assert fr._query_symbol("ENI", cfg) == "ENI.MI"
    assert fr._query_symbol("ENI.MI", cfg) == "ENI.MI"


def test_ranker_disabled_is_non_invasive():
    candidates = [_candidate("AAA"), _candidate("BBB")]
    result = fr.rank_candidates(candidates, {"factor_ranker_enabled": False})
    assert result["selection_pool"] is candidates
    assert result["candidates"] is candidates
    assert result["revision_enriched"] == 0
