from lab.correlation import CorrelationCluster
from lab.paper_policy import lab_portfolio_fit


def _cluster(*members, avg=0.82):
    return CorrelationCluster(members=tuple(members), average_abs_correlation=avg, risk_flag=True)


def test_no_clusters_provided_is_fully_backward_compatible():
    positions = [{"symbol": "NVDA", "strategy": "trend_continuation", "status": "OPEN"}]
    out = lab_portfolio_fit(symbol="AMD", strategy="trend_continuation", open_positions=positions, opened_this_run=0)
    assert out["eligible"] is True
    assert out["correlated_exposure"] is None
    assert out["model"] == "LAB_PORTFOLIO_V2_RESEARCH"


def test_correlated_exposure_is_surfaced_but_never_blocks():
    clusters = [_cluster("NVDA", "AMD", "AVGO")]
    positions = [
        {"symbol": "NVDA", "strategy": "trend_continuation", "status": "OPEN"},
        {"symbol": "AVGO", "strategy": "cross_sectional_momentum", "status": "OPEN"},
    ]
    out = lab_portfolio_fit(
        symbol="AMD", strategy="short_term_reversal_rsi45", open_positions=positions,
        opened_this_run=0, correlation_clusters=clusters,
    )
    # Never blocks: correlation is informational only, preserving the Lab's
    # ability to compare strategies on the same/correlated names.
    assert out["eligible"] is True
    assert out["correlated_exposure"]["already_held_count"] == 2
    assert out["correlated_exposure"]["already_held_in_cluster"] == ["AVGO", "NVDA"]
    assert out["model"] == "LAB_PORTFOLIO_V2_1_WITH_CORRELATION"


def test_warning_appears_only_at_or_above_threshold():
    clusters = [_cluster("NVDA", "AMD", "AVGO", "TSM")]
    one_held = [{"symbol": "NVDA", "strategy": "trend_continuation", "status": "OPEN"}]
    out = lab_portfolio_fit(
        symbol="AMD", strategy="trend_continuation", open_positions=one_held,
        opened_this_run=0, correlation_clusters=clusters, correlated_exposure_warn_at=3,
    )
    assert out["warnings"] == []

    three_held = [
        {"symbol": "NVDA", "strategy": "a", "status": "OPEN"},
        {"symbol": "AVGO", "strategy": "b", "status": "OPEN"},
        {"symbol": "TSM", "strategy": "c", "status": "OPEN"},
    ]
    out2 = lab_portfolio_fit(
        symbol="AMD", strategy="trend_continuation", open_positions=three_held,
        opened_this_run=0, correlation_clusters=clusters, correlated_exposure_warn_at=3,
    )
    assert "CORRELATED_CLUSTER_EXPOSURE" in out2["warnings"]


def test_symbol_not_in_any_cluster_has_no_correlated_exposure():
    clusters = [_cluster("NVDA", "AMD")]
    positions = [{"symbol": "NVDA", "strategy": "trend_continuation", "status": "OPEN"}]
    out = lab_portfolio_fit(
        symbol="KO", strategy="defensive_low_vol", open_positions=positions,
        opened_this_run=0, correlation_clusters=clusters,
    )
    assert out["correlated_exposure"] is None
    assert out["warnings"] == []


def test_closed_positions_do_not_count_as_correlated_exposure():
    clusters = [_cluster("NVDA", "AMD")]
    positions = [{"symbol": "NVDA", "strategy": "trend_continuation", "status": "CLOSED"}]
    out = lab_portfolio_fit(
        symbol="AMD", strategy="trend_continuation", open_positions=positions,
        opened_this_run=0, correlation_clusters=clusters,
    )
    assert out["correlated_exposure"]["already_held_count"] == 0


def test_duplicate_symbol_strategy_still_blocks_with_correlation_enabled():
    clusters = [_cluster("NVDA", "AMD")]
    positions = [{"symbol": "NVDA", "strategy": "trend_continuation", "status": "OPEN"}]
    out = lab_portfolio_fit(
        symbol="NVDA", strategy="trend_continuation", open_positions=positions,
        opened_this_run=0, correlation_clusters=clusters,
    )
    assert out["eligible"] is False
    assert "DUPLICATE_SYMBOL_STRATEGY" in out["failed"]
