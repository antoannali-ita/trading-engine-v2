from __future__ import annotations

import csv
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from supabase import create_client

PAGE_SIZE = 1000
TABLES = {
    "signals": "lab_paper_signals",
    "positions": "lab_paper_positions",
    "outcomes": "lab_signal_outcomes",
    "backtests": "lab_backtest_results",
}


def _client():
    url = (os.getenv("SUPABASE_URL") or "").strip()
    key = (os.getenv("SUPABASE_SECRET_KEY") or "").strip()
    if not url or not key:
        raise RuntimeError("SUPABASE_URL e SUPABASE_SECRET_KEY non configurati")
    return create_client(url, key)


def fetch_all(client, table: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0
    while True:
        batch = client.table(table).select("*").range(start, start + PAGE_SIZE - 1).execute().data or []
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            return rows
        start += PAGE_SIZE


def parse_json(value: Any, default: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if value in (None, ""):
        return default
    try:
        return json.loads(str(value))
    except Exception:
        return default


def signal_session(row: dict[str, Any]) -> str | None:
    value = row.get("signal_date")
    if value:
        return str(value)[:10]
    value = row.get("created_at")
    return str(value)[:10] if value else None


def position_session(row: dict[str, Any]) -> str | None:
    value = row.get("source_signal_date") or row.get("opened_at") or row.get("created_at")
    return str(value)[:10] if value else None


def paper_failed_gates(signal: dict[str, Any]) -> list[str]:
    details = parse_json(signal.get("details"), {})
    failed: list[str] = []
    if isinstance(details, dict):
        policy = details.get("paper_policy") or {}
        if isinstance(policy, dict):
            failed.extend(str(x) for x in (policy.get("hard_failed") or []))
    if str(signal.get("status") or "").upper() == "BLOCKED_DATA" and not failed:
        failed.append("BLOCKED_DATA")
    return sorted(set(failed))


def strict_failed_gates(signal: dict[str, Any]) -> list[str]:
    details = parse_json(signal.get("details"), {})
    failed: list[str] = []
    if isinstance(details, dict):
        trade = details.get("strict_trade_eligibility") or details.get("trade_eligibility") or {}
        if isinstance(trade, dict):
            failed.extend(str(x) for x in (trade.get("failed") or []))
        quality = details.get("data_quality") or {}
        if isinstance(quality, dict) and quality.get("blocked"):
            failed.append("DATA_QUALITY_RED")
    return sorted(set(failed))


def pct_change(current: float, previous: float) -> float | None:
    if previous == 0:
        return None if current == 0 else 100.0
    return (current - previous) / abs(previous) * 100.0


def write_csv(path: Path, rows: list[dict[str, Any]], default_fields: list[str] | None = None) -> None:
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fields.append(key)
    if not fields:
        fields = list(default_fields or [])
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        if not fields:
            return
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in fields})


def main() -> None:
    client = _client()
    now = datetime.now(timezone.utc)
    data = {name: fetch_all(client, table) for name, table in TABLES.items()}
    signals = data["signals"]
    positions = data["positions"]
    outcomes = data["outcomes"]
    backtests = data["backtests"]

    sessions = sorted({d for d in (signal_session(r) for r in signals) if d})
    latest_session = sessions[-1] if sessions else None
    previous_session = sessions[-2] if len(sessions) >= 2 else None

    current = [r for r in signals if signal_session(r) == latest_session] if latest_session else []
    previous = [r for r in signals if signal_session(r) == previous_session] if previous_session else []
    current_positions = [r for r in positions if position_session(r) == latest_session] if latest_session else []
    previous_positions = [r for r in positions if position_session(r) == previous_session] if previous_session else []

    def period_stats(rows: list[dict[str, Any]], opened: list[dict[str, Any]]) -> dict[str, Any]:
        statuses = Counter(str(r.get("status") or "N/D").upper() for r in rows)
        tier_counter = Counter()
        for row in rows:
            details = parse_json(row.get("details"), {})
            if isinstance(details, dict) and details.get("paper_tier"):
                tier_counter[str(details.get("paper_tier"))] += 1
        return {
            "signals": len(rows),
            "watch": statuses.get("WATCH", 0),
            "pre_buy": statuses.get("PRE_BUY", 0),
            "near_setup": statuses.get("NEAR_SETUP", 0),
            "confirmed": statuses.get("CONFIRMED", 0),
            "blocked_data": statuses.get("BLOCKED_DATA", 0),
            "paper_open": len(opened),
            "tier_a": tier_counter.get("A", 0),
            "tier_b": tier_counter.get("B", 0),
            "tier_c": tier_counter.get("C", 0),
            "conversion_pct": round((len(opened) / len(rows) * 100.0) if rows else 0.0, 2),
        }

    cur_stats = period_stats(current, current_positions)
    prev_stats = period_stats(previous, previous_positions)
    comparison = {
        key: {
            "current": cur_stats[key],
            "previous": prev_stats[key],
            "change_pct": pct_change(float(cur_stats[key]), float(prev_stats[key])),
        }
        for key in cur_stats
    }

    strategies = sorted({str(r.get("strategy") or "N/D") for r in signals if r.get("strategy")})
    backtest_by_strategy: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in backtests:
        backtest_by_strategy[str(row.get("strategy") or "N/D")].append(row)
    outcome_by_strategy: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in outcomes:
        outcome_by_strategy[str(row.get("strategy") or "N/D")].append(row)

    strategy_summary: list[dict[str, Any]] = []
    gate_counter: Counter[tuple[str, str, str]] = Counter()
    for strategy in strategies:
        rows = [r for r in current if str(r.get("strategy") or "") == strategy]
        all_rows = [r for r in signals if str(r.get("strategy") or "") == strategy]
        all_opens = [r for r in positions if str(r.get("strategy") or "") == strategy]
        opens = [r for r in current_positions if str(r.get("strategy") or "") == strategy]
        statuses = Counter(str(r.get("status") or "N/D").upper() for r in rows)
        tier_counter = Counter()
        for row in rows:
            details = parse_json(row.get("details"), {})
            if isinstance(details, dict) and details.get("paper_tier"):
                tier_counter[str(details.get("paper_tier"))] += 1
            for gate in paper_failed_gates(row):
                gate_counter[(strategy, "PAPER_POLICY", gate)] += 1
            for gate in strict_failed_gates(row):
                gate_counter[(strategy, "LEGACY_STRICT", gate)] += 1

        bt = backtest_by_strategy.get(strategy, [])
        pf_values = [float(r["profit_factor"]) for r in bt if r.get("profit_factor") not in (None, "")]
        ret_values = [float(r["avg_return_pct"]) for r in bt if r.get("avg_return_pct") not in (None, "")]
        avg_pf = sum(pf_values) / len(pf_values) if pf_values else None
        avg_ret = sum(ret_values) / len(ret_values) if ret_values else None

        outs = outcome_by_strategy.get(strategy, [])
        d1 = [float(r["ret_d1"]) for r in outs if r.get("ret_d1") not in (None, "")]
        avg_d1 = sum(d1) / len(d1) if d1 else None

        session_conversion = (len(opens) / len(rows) * 100.0) if rows else 0.0
        lifetime_conversion = (len(all_opens) / len(all_rows) * 100.0) if all_rows else 0.0
        blocked_ratio = (statuses.get("BLOCKED_DATA", 0) / len(rows)) if rows else 0.0

        # Do not put a strategy in standby with a tiny forward sample. First
        # diagnose whether it is under-tested or bottlenecked.
        if len(all_opens) < 10:
            health = "UNDERTESTED"
        elif blocked_ratio >= 0.30:
            health = "REVIEW"
        elif len(all_rows) >= 20 and lifetime_conversion < 5.0:
            health = "BOTTLENECK"
        elif avg_pf is not None and avg_pf >= 1.40 and (avg_ret or 0) > 0:
            health = "PROMISING"
        else:
            health = "ACTIVE"

        strategy_summary.append({
            "strategy": strategy,
            "latest_session": latest_session,
            "signals_session": len(rows),
            "pre_buy_session": statuses.get("PRE_BUY", 0),
            "near_setup_session": statuses.get("NEAR_SETUP", 0),
            "confirmed_session": statuses.get("CONFIRMED", 0),
            "blocked_data_session": statuses.get("BLOCKED_DATA", 0),
            "tier_a_session": tier_counter.get("A", 0),
            "tier_b_session": tier_counter.get("B", 0),
            "tier_c_session": tier_counter.get("C", 0),
            "paper_open_session": len(opens),
            "conversion_pct_session": round(session_conversion, 2),
            "signals_lifetime": len(all_rows),
            "paper_open_lifetime": len(all_opens),
            "conversion_pct_lifetime": round(lifetime_conversion, 2),
            "backtest_avg_profit_factor": round(avg_pf, 3) if avg_pf is not None else None,
            "backtest_avg_return_pct": round(avg_ret, 3) if avg_ret is not None else None,
            "forward_d1_samples": len(d1),
            "forward_avg_ret_d1_pct": round(avg_d1, 3) if avg_d1 is not None else None,
            "lab_status": health,
        })

    gate_rows = [
        {"strategy": strategy, "policy_type": policy_type, "gate": gate, "blocked_session": count}
        for (strategy, policy_type, gate), count in gate_counter.most_common()
    ]
    paper_gate_rows = [r for r in gate_rows if r["policy_type"] == "PAPER_POLICY"]
    dominant_gate = paper_gate_rows[0]["gate"] if paper_gate_rows else "N/D"

    overall_status = "HEALTHY"
    notes: list[str] = []
    if cur_stats["signals"] >= 10 and cur_stats["conversion_pct"] < 5.0:
        overall_status = "BOTTLENECK"
        notes.append("Conversione segnale→paper sotto 5% nell'ultima sessione completata")
    if cur_stats["blocked_data"] and cur_stats["signals"] and cur_stats["blocked_data"] / cur_stats["signals"] >= 0.20:
        overall_status = "REVIEW"
        notes.append("BLOCKED_DATA >=20% dei segnali dell'ultima sessione")
    if not cur_stats["signals"]:
        overall_status = "NO_ACTIVITY"
        notes.append("Nessuna sessione Laboratory disponibile")

    report = {
        "generated_at_utc": now.isoformat(),
        "latest_session": latest_session,
        "previous_session": previous_session,
        "overall_status": overall_status,
        "dominant_gate": dominant_gate,
        "notes": notes,
        "current_session": cur_stats,
        "previous_session_stats": prev_stats,
        "comparison": comparison,
        "strategy_summary": strategy_summary,
        "gate_failures": gate_rows,
    }

    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path("artifacts") / f"lab_health_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "lab_health_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(out_dir / "strategy_summary.csv", strategy_summary)
    write_csv(out_dir / "gate_failures.csv", gate_rows, ["strategy", "policy_type", "gate", "blocked_session"])
    write_csv(out_dir / "signals_latest_session.csv", current)

    md = [
        "# Laboratory Health Report",
        "",
        f"Generated: {now.isoformat()}",
        f"Latest market session: **{latest_session or 'N/D'}**",
        f"Previous market session: **{previous_session or 'N/D'}**",
        f"Status: **{overall_status}**",
        f"Dominant paper gate: **{dominant_gate}**",
        "",
        "## Latest completed session",
        f"- Signals: {cur_stats['signals']}",
        f"- PRE_BUY: {cur_stats['pre_buy']}",
        f"- NEAR_SETUP: {cur_stats['near_setup']}",
        f"- CONFIRMED: {cur_stats['confirmed']}",
        f"- BLOCKED_DATA: {cur_stats['blocked_data']}",
        f"- Tier A/B/C candidates: {cur_stats['tier_a']}/{cur_stats['tier_b']}/{cur_stats['tier_c']}",
        f"- Paper opens: {cur_stats['paper_open']}",
        f"- Signal→paper conversion: {cur_stats['conversion_pct']}%",
        "",
        "## Notes",
    ]
    md.extend([f"- {x}" for x in notes] or ["- Nessuna criticità automatica rilevata."])
    (out_dir / "LAB_HEALTH_REPORT.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(json.dumps({
        "status": overall_status,
        "latest_session": latest_session,
        "current_session": cur_stats,
        "dominant_gate": dominant_gate,
    }, ensure_ascii=False))
    print(f"REPORT_DIR={out_dir}")


if __name__ == "__main__":
    main()
