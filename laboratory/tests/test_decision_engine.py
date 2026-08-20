from datetime import date

import pandas as pd

from lab.decision_engine import (
    data_quality_check,
    earnings_distance_days,
    net_rr,
    portfolio_fit_v1,
    regime_v1,
    risk_based_qty,
    trade_eligibility,
)


def test_risk_based_qty_respects_position_cap():
    qty = risk_based_qty(entry=100.0, stop=95.0)
    assert qty > 0
    assert qty * 100.0 <= 5000.0


def test_data_quality_blocks_invalid_stop():
    result = data_quality_check(
        price=100, entry=100, max_buy=102, stop=101, tp1=110, tp2=120,
        atr=2, sma50=95, sma200=90,
    )
    assert result["status"] == "RED"
    assert "STOP_INVALID" in result["red"]


def test_net_rr_includes_costs():
    rr = net_rr(entry=100, stop=95, target=112.5, qty=40)
    assert rr is not None
    assert rr < 2.5


def test_earnings_distance():
    assert earnings_distance_days("2026-09-01", date(2026, 8, 20)) == 12


def test_trade_gate_blocks_close_earnings_and_low_rr():
    dq = {"status": "GREEN"}
    result = trade_eligibility(
        data_quality=dq, trigger="CONFIRMED", price=100, max_buy=101,
        rr_net=1.7, earnings_days=5,
    )
    assert not result["eligible"]
    assert "RR_NET_BELOW_MIN" in result["failed"]
    assert "EARNINGS_LT_7D" in result["failed"]


def test_portfolio_v1_blocks_duplicate_ticker():
    result = portfolio_fit_v1(
        symbol="NVDA",
        open_positions=[{"symbol": "NVDA", "status": "OPEN"}],
        opened_this_run=0,
    )
    assert not result["eligible"]
    assert "DUPLICATE_TICKER" in result["failed"]


def test_regime_v1_returns_known_state():
    idx = pd.date_range("2025-01-01", periods=260, freq="B")
    close = pd.Series(range(100, 360), index=idx, dtype=float)
    frame = pd.DataFrame(index=idx)
    frame["Close"] = close
    frame["sma50"] = close.rolling(50).mean()
    frame["sma200"] = close.rolling(200).mean()
    frame["vol20"] = 0.15
    result = regime_v1(frame)
    assert result["state"] in {"BULL_QUIET", "BULL_VOLATILE", "RANGE_NEUTRAL", "BEAR_HIGH_VOL"}
