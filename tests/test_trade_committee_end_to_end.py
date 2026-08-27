from trade_committee.core_snapshot import build_core_snapshot
import trade_committee.orchestrator as orch


def _patch_dependencies(monkeypatch):
    monkeypatch.setattr(orch, "fetch_market_bundle", lambda symbol: {"ticker_obj": object(), "price": 100.0, "rsi14": 50.0})
    monkeypatch.setattr(orch, "fetch_info", lambda t: {})
    monkeypatch.setattr(
        orch,
        "fundamental_bundle",
        lambda info, price: {"data": {f"k{i}": i for i in range(16)}, "rigor": {}},
    )
    monkeypatch.setattr(orch, "tradingview_crosscheck", lambda *args: {"status": "REAL"})
    monkeypatch.setattr(orch, "quality_assessment", lambda f: {"score": 80.0, "coverage": 8, "red_flags": []})
    monkeypatch.setattr(orch, "valuation_assessment", lambda f: {"score": 80.0, "notes": ["validated"]})
    monkeypatch.setattr(
        orch,
        "earnings_and_catalysts",
        lambda t: {"status": "REAL", "next": {"date": "30/09/2026", "days": 30}, "history": []},
    )
    monkeypatch.setattr(
        orch,
        "news_analyst_ownership",
        lambda t, info: {"status": "PARTIAL", "analyst": {}, "news": [], "insiders": [], "institutions": []},
    )
    monkeypatch.setattr(orch, "sec_recent_filings", lambda symbol: {"status": "REAL", "source": "SEC EDGAR", "filings": []})
    monkeypatch.setattr(
        orch,
        "benchmark_context",
        lambda *args: {"status": "REAL", "benchmark": "SPY", "relative": {"3m": 0.05, "6m": 0.08}, "score": 70.0},
    )
    monkeypatch.setattr(
        orch,
        "portfolio_context",
        lambda *args: {"status": "REAL", "already_owned": False, "estimated_weight": 0.0, "note": "fixture"},
    )
    monkeypatch.setattr(orch, "build_trade_plan", lambda *args, **kwargs: {"status": "REAL", "entry": 100, "stop": 95, "tp1": 110, "tp2": 115, "rr1_net": 2.0, "rr2_net": 3.0})
    monkeypatch.setattr(orch, "technical_assessment", lambda m: {"score": 70.0, "trend_fail": False})
    monkeypatch.setattr(orch, "volume_assessment", lambda m: {"score": 50.0, "relative_volume": 1.0})


def _core_payload(**overrides):
    payload = {
        "market": "USA",
        "ticker": "TEST",
        "price": 100.0,
        "ideal_entry": 100.0,
        "max_buy": 102.0,
        "stop": 95.0,
        "tp1": 110.0,
        "tp2": 115.0,
        "net_rr_tp1": 2.0,
        "net_rr_tp2": 3.0,
        "trigger_state": "CONFIRMED",
        "technical_state": "BULLISH",
        "shares": 20,
        "invested": 2000.0,
        "data_review_required": False,
        "corporate_action_status": "OK",
        "days_to_earnings": 30,
        "operational_state": "PRE_BUY_HIGH",
        "failed_gates": [],
        "veto_reasons": [],
    }
    payload.update(overrides)
    return payload


def test_engine_prebuy_valid_candidate_can_reach_committee_approve(monkeypatch):
    _patch_dependencies(monkeypatch)
    snapshot = build_core_snapshot(_core_payload(), engine_version="fixture")
    result = orch.run_committee("TEST", core_snapshot=snapshot)
    assert result["verdict"] in {"APPROVE", "APPROVE_WITH_WARNING"}
    assert result["core_snapshot_authoritative"] is True
    assert result["trade_plan"]["source"] == "CORE_SNAPSHOT"
    assert result["hard_vetoes"] == []


def test_engine_candidate_with_core_hard_veto_can_never_reach_committee_approve(monkeypatch):
    _patch_dependencies(monkeypatch)
    snapshot = build_core_snapshot(_core_payload(veto_reasons=["CORE liquidity gate failed"]), engine_version="fixture")
    result = orch.run_committee("TEST", core_snapshot=snapshot)
    assert result["verdict"] == "REJECT_HARD_VETO"
    assert "core_hard_veto" in result["hard_vetoes"]
