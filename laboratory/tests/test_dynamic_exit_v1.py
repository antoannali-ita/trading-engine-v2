from __future__ import annotations

import pandas as pd

from lab.dynamic_exit import (
    POLICY_VERSION,
    RecalibrationReason,
    TargetMode,
    breakout_confirmed,
    evaluate,
)


def _frame(*, close=120.0, high=121.0, low=118.0, atr=2.0, sma20=115.0, rvol=1.4, prev_high=118.0):
    rows = []
    for i in range(25):
        rows.append({
            "Open": 110 + i * 0.2,
            "High": prev_high - 1.0 + (i % 3) * 0.1,
            "Low": 108 + i * 0.2,
            "Close": 109 + i * 0.2,
            "atr14": atr,
            "sma20": sma20,
            "relative_volume": 0.9,
        })
    rows[-1].update({"High": high, "Low": low, "Close": close, "atr14": atr, "sma20": sma20, "relative_volume": rvol})
    return pd.DataFrame(rows)


def _position(status="TP1_HIT", stop_current=100.0, tp2=118.0):
    return {
        "id": 1,
        "symbol": "TEST",
        "status": status,
        "entry_price": 105.0,
        "stop_initial": 98.0,
        "stop_current": stop_current,
        "tp1": 112.0,
        "tp2": tp2,
        "details": {},
    }


def test_stop_never_moves_below_initial_stop():
    result = evaluate(_position(stop_current=97.0), _frame(close=110, high=111, low=108, sma20=109, rvol=0.8), now_iso="2026-08-27T20:00:00+00:00")
    assert result["stop_current"] >= 98.0


def test_stop_never_moves_down_after_raise():
    result = evaluate(_position(stop_current=108.0), _frame(close=112, high=113, low=110, sma20=111, rvol=0.8), now_iso="2026-08-27T20:00:00+00:00")
    assert result["stop_current"] >= 108.0


def test_tp2_never_moves_below_initial_tp2():
    p = _position(tp2=118.0)
    p["details"] = {"dynamic_exit": {"policy_version": POLICY_VERSION, "target_mode": TargetMode.POST_TP1_TRAILING.value, "stop_initial": 98.0, "stop_current": 105.0, "tp2_initial": 120.0, "tp2_current": 118.0}}
    result = evaluate(p, _frame(close=114, high=115, low=112, rvol=0.7), now_iso="2026-08-27T20:00:00+00:00")
    assert result["tp2_current"] >= 120.0


def test_breakout_requires_price_and_volume_confirmation():
    snap = {"close": 120.0, "previous_high": 118.0, "relative_volume": 1.4}
    assert breakout_confirmed(snap)
    assert not breakout_confirmed({**snap, "relative_volume": 1.0})
    assert not breakout_confirmed({**snap, "close": 118.2})


def test_tp1_hit_activates_trailing_mode():
    result = evaluate(_position(status="TP1_HIT"), _frame(close=114, high=115, low=112, rvol=0.8), now_iso="2026-08-27T20:00:00+00:00")
    assert result["target_mode"] == TargetMode.POST_TP1_TRAILING.value
    assert any(e["event_type"] == "TARGET_MODE_CHANGED" for e in result["events"])


def test_confirmed_breakout_can_raise_tp2_and_tighten_stop():
    result = evaluate(_position(status="TP1_HIT", stop_current=105.0, tp2=118.0), _frame(close=120, high=121, low=118, atr=2, rvol=1.4, prev_high=118), now_iso="2026-08-27T20:00:00+00:00")
    assert result["target_mode"] == TargetMode.POST_BREAKOUT_TRAILING.value
    assert result["tp2_current"] > 118.0
    assert result["stop_current"] >= 105.0
    assert any(e["event_type"] == "TP2_RAISED" for e in result["events"])


def test_open_position_keeps_fixed_target_mode():
    result = evaluate(_position(status="OPEN"), _frame(close=120, high=121, low=118, rvol=1.4), now_iso="2026-08-27T20:00:00+00:00")
    assert result["target_mode"] == TargetMode.FIXED.value
    assert result["tp2_current"] == 118.0


def test_recalibration_reason_is_closed_enum():
    allowed = {x.value for x in RecalibrationReason}
    result = evaluate(_position(status="TP1_HIT"), _frame(close=114, high=115, low=112, rvol=0.8), now_iso="2026-08-27T20:00:00+00:00")
    assert result["reason"] in allowed


def test_same_market_path_is_deterministic():
    p = _position(status="TP1_HIT", stop_current=105.0, tp2=118.0)
    frame = _frame(close=120, high=121, low=118, atr=2, rvol=1.4, prev_high=118)
    a = evaluate(p, frame, now_iso="2026-08-27T20:00:00+00:00")
    b = evaluate(p, frame, now_iso="2026-08-27T20:00:00+00:00")
    assert a == b
