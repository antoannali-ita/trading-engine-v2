from __future__ import annotations

import json
from statistics import median
from typing import Any, Iterable

from lab.blocker_policy import BLOCKER_LOOKBACK_SESSIONS, main_blocker, primary_blocker
from lab.risk_metrics import (
    build_risk_basis,
    expectancy_r,
    max_drawdown_r,
    mtm_r,
    open_risk_and_locked_profit_r,
    price_r,
    profit_factor,
)
from lab.stress_policy import evaluate_live_stress
from lab.verdict_engine import evaluate_verdict

ACTIVE_STATUSES = {"OPEN", "TP1_HIT"}


def _dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except Exception:
        return None


def _signal_session(row: dict[str, Any]) -> str | None:
    value = row.get("signal_date") or row.get("created_at")
    return str(value)[:10] if value else None


def strategy_version(row: dict[str, Any]) -> str:
    details = _dict(row.get("details"))
    return str(row.get("strategy_version") or details.get("strategy_version") or details.get("version") or "UNVERSIONED")


def _side(row: dict[str, Any]) -> str:
    details = _dict(row.get("details"))
    return str(row.get("side") or details.get("side") or "LONG").upper()


def _fill(row: dict[str, Any]) -> float | None:
    details = _dict(row.get("details"))
    return _float(row.get("fill_price")) or _float(details.get("fill_price")) or _float(details.get("execution_entry")) or _float(row.get("entry_price"))


def _atr(row: dict[str, Any]) -> float | None:
    details = _dict(row.get("details"))
    return _float(row.get("atr14_at_entry")) or _float(details.get("atr14"))


def position_r_metrics(row: dict[str, Any]) -> dict[str, float | bool | None]:
    fill = _fill(row)
    stop_initial = _float(row.get("stop_initial"))
    if fill is None or stop_initial is None:
        return {"mtm_r": None, "realized_r": None, "open_risk_r": None, "locked_profit_r": None, "risk_floor_applied": None}
    try:
        basis = build_risk_basis(side=_side(row), fill_price=fill, stop_initial=stop_initial, atr14=_atr(row))
    except ValueError:
        return {"mtm_r": None, "realized_r": None, "open_risk_r": None, "locked_profit_r": None, "risk_floor_applied": None}

    status = str(row.get("status") or "").upper()
    current = _float(row.get("last_price")) or fill
    result: dict[str, float | bool | None] = {
        "mtm_r": mtm_r(basis=basis, current_price=current) if status in ACTIVE_STATUSES else None,
        "realized_r": None,
        "open_risk_r": None,
        "locked_profit_r": None,
        "risk_floor_applied": basis.risk_floor_applied,
    }
    if status in ACTIVE_STATUSES:
        risk_r, locked_r = open_risk_and_locked_profit_r(basis=basis, stop_current=_float(row.get("stop_current")))
        result["open_risk_r"] = risk_r
        result["locked_profit_r"] = locked_r
    elif status == "CLOSED":
        stored = _float(row.get("realized_r"))
        exit_price = _float(row.get("exit_price")) or _float(row.get("last_price"))
        result["realized_r"] = stored if stored is not None else (
            price_r(side=basis.side, fill_price=basis.fill_price, price=exit_price, risk_denominator=basis.normalized_initial_risk)
            if exit_price is not None else None
        )
    return result


def _tier_a_primary_blocker(signal: dict[str, Any]) -> str | None:
    details = _dict(signal.get("details"))
    policy = _dict(details.get("paper_policy"))
    tier_checks = _dict(policy.get("tier_checks"))
    tier_a = _dict(tier_checks.get("A"))
    failed = tier_a.get("failed") or []
    if isinstance(failed, str):
        failed = [failed]
    return primary_blocker(failed)


def _recent_blocker_signals(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sessions = sorted({s for s in (_signal_session(row) for row in signals) if s})
    if not sessions:
        return signals
    keep = set(sessions[-BLOCKER_LOOKBACK_SESSIONS:])
    return [row for row in signals if _signal_session(row) in keep]


def aggregate_strategy(
    *,
    strategy: str,
    strategy_version_value: str,
    signals: Iterable[dict[str, Any]],
    positions: Iterable[dict[str, Any]],
    outcomes: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    sigs = [x for x in signals if str(x.get("strategy") or "") == strategy and strategy_version(x) == strategy_version_value]
    pos = [x for x in positions if str(x.get("strategy") or "") == strategy and strategy_version(x) == strategy_version_value]
    outs = [x for x in outcomes if str(x.get("strategy") or "") == strategy]

    closed_rows = [p for p in pos if str(p.get("status") or "").upper() == "CLOSED"]
    open_rows = [p for p in pos if str(p.get("status") or "").upper() in ACTIVE_STATUSES]

    closed_r: list[float] = []
    open_r: list[float] = []
    open_risk: list[float] = []
    locked: list[float] = []
    for p in pos:
        metrics = position_r_metrics(p)
        if metrics.get("realized_r") is not None:
            closed_r.append(float(metrics["realized_r"]))
        if metrics.get("mtm_r") is not None:
            open_r.append(float(metrics["mtm_r"]))
        if metrics.get("open_risk_r") is not None:
            open_risk.append(float(metrics["open_risk_r"]))
        if metrics.get("locked_profit_r") is not None:
            locked.append(float(metrics["locked_profit_r"]))

    returns = [_float(p.get("return_pct")) for p in closed_rows]
    returns = [x for x in returns if x is not None]
    wins = sum(1 for x in closed_r if x > 0)
    losses = sum(1 for x in closed_r if x < 0)
    near_stop_count = sum(1 for x in open_r if x <= -0.75)
    stress = evaluate_live_stress(
        total_mtm_r=sum(open_r) if open_r else 0.0,
        worst_open_r=min(open_r) if open_r else None,
        open_risk_r=sum(open_risk) if open_risk else 0.0,
        near_stop_count=near_stop_count,
        open_count=len(open_rows),
    )

    blocker_sigs = _recent_blocker_signals(sigs)
    rejected_primary = [
        code for code in (_tier_a_primary_blocker(s) for s in blocker_sigs)
        if code is not None
    ]
    blocker = main_blocker(rejected_primary)

    mfe_values = [_float(x.get("mfe_r")) for x in outs]
    mae_values = [_float(x.get("mae_r")) for x in outs]
    mfe_values = [x for x in mfe_values if x is not None]
    mae_values = [x for x in mae_values if x is not None]

    pf = profit_factor(closed_r)
    exp_r = expectancy_r(closed_r)
    avg_return = sum(returns) / len(returns) if returns else None
    data_issue = len(closed_rows) >= 30 and len(closed_r) < int(0.8 * len(closed_rows))
    verdict = evaluate_verdict(
        closed_count=len(closed_rows),
        net_pf=pf,
        expectancy_r=exp_r,
        avg_net_return_pct=avg_return,
        stress_status=stress.status,
        data_issue=data_issue,
    )

    eligible = 0
    tier_counts = {"A": 0, "B": 0, "C": 0}
    paper_opened = 0
    data_rejects = 0
    triggered = 0
    for s in sigs:
        details = _dict(s.get("details"))
        policy = _dict(details.get("paper_policy"))
        tier = policy.get("tier")
        if tier in tier_counts:
            tier_counts[str(tier)] += 1
        if policy.get("eligible"):
            eligible += 1
        if str(s.get("status") or "").upper() == "PAPER_OPEN":
            paper_opened += 1
        if str(details.get("trigger") or "").upper() == "CONFIRMED":
            triggered += 1
        dq = _dict(details.get("data_quality"))
        if str(dq.get("status") or "").upper() == "RED":
            data_rejects += 1

    return {
        "strategy": strategy,
        "strategy_version": strategy_version_value,
        "signals": len(sigs),
        "eligible": eligible,
        "paper_opened": paper_opened,
        "open": len(open_rows),
        "closed": len(closed_rows),
        "wins": wins,
        "losses": losses,
        "win_rate": (100.0 * wins / len(closed_r)) if closed_r else None,
        "net_pf": pf,
        "expectancy_r": exp_r,
        "realized_r": sum(closed_r) if closed_r else 0.0,
        "mtm_r": sum(open_r) if open_r else 0.0,
        "avg_return_pct": avg_return,
        "max_drawdown_r": max_drawdown_r(closed_r),
        "open_risk_r": sum(open_risk) if open_risk else 0.0,
        "locked_profit_r": sum(locked) if locked else 0.0,
        "mfe_r_median": median(mfe_values) if mfe_values else None,
        "mae_r_median": median(mae_values) if mae_values else None,
        "main_blocker": blocker.code,
        "main_blocker_label": blocker.label,
        "main_blocker_pct": blocker.pct,
        "blocker_sample": blocker.sample,
        "maturity": verdict.maturity,
        "verdict": verdict.verdict,
        "verdict_reason_codes": list(verdict.reason_codes),
        "verdict_policy_version": verdict.policy_version,
        "stress_status": stress.status,
        "stress_reason_codes": list(stress.reason_codes),
        "stress_policy_version": stress.policy_version,
        "tier_a": tier_counts["A"],
        "tier_b": tier_counts["B"],
        "tier_c": tier_counts["C"],
        "triggered": triggered,
        "data_rejects": data_rejects,
    }


def aggregate_all_strategies(
    *,
    signals: Iterable[dict[str, Any]],
    positions: Iterable[dict[str, Any]],
    outcomes: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    sigs = list(signals)
    pos = list(positions)
    outs = list(outcomes)
    keys: set[tuple[str, str]] = set()
    for row in sigs + pos:
        strategy = str(row.get("strategy") or "")
        if strategy:
            keys.add((strategy, strategy_version(row)))
    return [
        aggregate_strategy(strategy=s, strategy_version_value=v, signals=sigs, positions=pos, outcomes=outs)
        for s, v in sorted(keys)
    ]
