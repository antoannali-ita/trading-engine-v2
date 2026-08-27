from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

import pandas as pd


POLICY_VERSION = "DYNAMIC_EXIT_V1"


class RecalibrationReason(str, Enum):
    TP1_HIT = "TP1_HIT"
    BREAKOUT_CONFIRMED = "BREAKOUT_CONFIRMED"
    TREND_DETERIORATION = "TREND_DETERIORATION"
    STRUCTURE_BREAK = "STRUCTURE_BREAK"
    TIME_DECAY = "TIME_DECAY"


class TargetMode(str, Enum):
    FIXED = "FIXED"
    POST_TP1_TRAILING = "POST_TP1_TRAILING"
    POST_BREAKOUT_TRAILING = "POST_BREAKOUT_TRAILING"


@dataclass(frozen=True)
class DynamicExitConfig:
    breakout_lookback: int = 20
    breakout_buffer_pct: float = 0.005
    breakout_rvol_min: float = 1.20
    post_tp1_atr_stop: float = 1.50
    breakout_atr_stop: float = 1.25
    breakout_target_atr: float = 2.00
    structure_lookback: int = 5
    structure_atr_buffer: float = 0.25


DEFAULT_CONFIG = DynamicExitConfig()


def _f(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def _details(position: dict) -> dict:
    value = position.get("details")
    return dict(value) if isinstance(value, dict) else {}


def initial_state(position: dict) -> dict:
    details = _details(position)
    existing = details.get("dynamic_exit")
    if isinstance(existing, dict):
        return dict(existing)
    return {
        "policy_version": POLICY_VERSION,
        "target_mode": TargetMode.FIXED.value,
        "stop_initial": _f(position.get("stop_initial")),
        "stop_current": _f(position.get("stop_current")) or _f(position.get("stop_initial")),
        "tp2_initial": _f(position.get("tp2")),
        "tp2_current": _f(position.get("tp2")),
        "last_recalibration_at": None,
        "recalibration_reason": None,
    }


def _market_snapshot(frame: pd.DataFrame, config: DynamicExitConfig) -> dict:
    if frame is None or frame.empty:
        raise ValueError("price frame is empty")
    last = frame.iloc[-1]
    close = _f(last.get("Close"))
    high = _f(last.get("High"))
    low = _f(last.get("Low"))
    atr = _f(last.get("atr14"))
    sma20 = _f(last.get("sma20"))
    rvol = _f(last.get("relative_volume"))
    if close is None or high is None or low is None:
        raise ValueError("OHLC data incomplete")

    previous = frame.iloc[:-1]
    prev_high = None
    if not previous.empty and "High" in previous:
        series = previous["High"].tail(config.breakout_lookback).dropna()
        if not series.empty:
            prev_high = float(series.max())

    swing_low = None
    if "Low" in frame:
        lows = frame["Low"].tail(config.structure_lookback).dropna()
        if not lows.empty:
            swing_low = float(lows.min())

    return {
        "close": close,
        "high": high,
        "low": low,
        "atr": atr,
        "sma20": sma20,
        "relative_volume": rvol,
        "previous_high": prev_high,
        "swing_low": swing_low,
    }


def breakout_confirmed(snapshot: dict, config: DynamicExitConfig = DEFAULT_CONFIG) -> bool:
    close = _f(snapshot.get("close"))
    previous_high = _f(snapshot.get("previous_high"))
    rvol = _f(snapshot.get("relative_volume"))
    if close is None or previous_high is None or rvol is None:
        return False
    return close > previous_high * (1.0 + config.breakout_buffer_pct) and rvol >= config.breakout_rvol_min


def evaluate(position: dict, frame: pd.DataFrame, *, now_iso: str, config: DynamicExitConfig = DEFAULT_CONFIG) -> dict:
    """Return a deterministic, monotonic dynamic-exit decision.

    The policy never lowers stop_current and never lowers tp2_current. It does not
    close positions; the existing paper lifecycle remains authoritative for fills.
    """
    state = initial_state(position)
    snap = _market_snapshot(frame, config)

    entry = _f(position.get("entry_price"))
    stop_initial = _f(state.get("stop_initial"))
    stop_current = _f(position.get("stop_current")) or _f(state.get("stop_current")) or stop_initial
    tp2_initial = _f(state.get("tp2_initial")) or _f(position.get("tp2"))
    tp2_current = _f(position.get("tp2")) or _f(state.get("tp2_current")) or tp2_initial
    status = str(position.get("status") or "OPEN").upper()
    close = snap["close"]
    atr = snap["atr"]

    new_stop = stop_current
    new_tp2 = tp2_current
    mode = str(state.get("target_mode") or TargetMode.FIXED.value)
    reasons: list[str] = []
    events: list[dict] = []

    if status == "TP1_HIT" and entry is not None:
        if mode == TargetMode.FIXED.value:
            mode = TargetMode.POST_TP1_TRAILING.value
            reasons.append(RecalibrationReason.TP1_HIT.value)
            events.append({"event_type": "TARGET_MODE_CHANGED", "reason": RecalibrationReason.TP1_HIT.value})

        candidates = [entry]
        if atr is not None and atr > 0:
            candidates.append(close - config.post_tp1_atr_stop * atr)
            swing_low = _f(snap.get("swing_low"))
            if swing_low is not None:
                candidates.append(swing_low - config.structure_atr_buffer * atr)
            sma20 = _f(snap.get("sma20"))
            if sma20 is not None:
                candidates.append(sma20 - config.structure_atr_buffer * atr)
        candidate_stop = max(candidates)
        if atr is not None and atr > 0:
            candidate_stop = min(candidate_stop, close - 0.25 * atr)
        if new_stop is None or candidate_stop > new_stop:
            old = new_stop
            new_stop = candidate_stop
            reasons.append(RecalibrationReason.TP1_HIT.value)
            events.append({"event_type": "STOP_MOVED", "reason": RecalibrationReason.TP1_HIT.value, "old_stop": old, "new_stop": new_stop})

    if status == "TP1_HIT" and breakout_confirmed(snap, config):
        if mode != TargetMode.POST_BREAKOUT_TRAILING.value:
            mode = TargetMode.POST_BREAKOUT_TRAILING.value
            events.append({"event_type": "TARGET_MODE_CHANGED", "reason": RecalibrationReason.BREAKOUT_CONFIRMED.value})
        reasons.append(RecalibrationReason.BREAKOUT_CONFIRMED.value)
        if atr is not None and atr > 0:
            target_candidate = max(close + config.breakout_target_atr * atr, snap["high"] + 0.50 * atr)
            if new_tp2 is None or target_candidate > new_tp2:
                old_tp2 = new_tp2
                new_tp2 = target_candidate
                events.append({"event_type": "TP2_RAISED", "reason": RecalibrationReason.BREAKOUT_CONFIRMED.value, "old_tp2": old_tp2, "new_tp2": new_tp2})
            stop_candidate = close - config.breakout_atr_stop * atr
            if new_stop is None or stop_candidate > new_stop:
                old_stop = new_stop
                new_stop = stop_candidate
                events.append({"event_type": "STOP_MOVED", "reason": RecalibrationReason.BREAKOUT_CONFIRMED.value, "old_stop": old_stop, "new_stop": new_stop})

    sma20 = _f(snap.get("sma20"))
    if status == "TP1_HIT" and sma20 is not None and close < sma20 and atr is not None and atr > 0:
        tighten = close - 1.0 * atr
        if new_stop is None or tighten > new_stop:
            old_stop = new_stop
            new_stop = tighten
            reasons.append(RecalibrationReason.TREND_DETERIORATION.value)
            events.append({"event_type": "STOP_MOVED", "reason": RecalibrationReason.TREND_DETERIORATION.value, "old_stop": old_stop, "new_stop": new_stop})

    if stop_initial is not None and new_stop is not None:
        new_stop = max(new_stop, stop_initial)
    if stop_current is not None and new_stop is not None:
        new_stop = max(new_stop, stop_current)
    if tp2_initial is not None and new_tp2 is not None:
        new_tp2 = max(new_tp2, tp2_initial)
    if tp2_current is not None and new_tp2 is not None:
        new_tp2 = max(new_tp2, tp2_current)

    changed = (new_stop != stop_current) or (new_tp2 != tp2_current) or (mode != str(state.get("target_mode") or TargetMode.FIXED.value))
    reason = reasons[-1] if reasons else state.get("recalibration_reason")
    new_state = {
        "policy_version": POLICY_VERSION,
        "target_mode": mode,
        "stop_initial": stop_initial,
        "stop_current": new_stop,
        "tp2_initial": tp2_initial,
        "tp2_current": new_tp2,
        "last_recalibration_at": now_iso if changed else state.get("last_recalibration_at"),
        "recalibration_reason": reason,
        "breakout": {
            "lookback": config.breakout_lookback,
            "buffer_pct": config.breakout_buffer_pct,
            "rvol_min": config.breakout_rvol_min,
            "previous_high": snap.get("previous_high"),
            "relative_volume": snap.get("relative_volume"),
            "confirmed": breakout_confirmed(snap, config),
        },
    }
    return {
        "changed": changed,
        "stop_current": new_stop,
        "tp2_current": new_tp2,
        "target_mode": mode,
        "reason": reason,
        "events": events,
        "state": new_state,
        "snapshot": snap,
    }
