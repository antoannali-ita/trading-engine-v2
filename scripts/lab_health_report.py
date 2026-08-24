from __future__ import annotations

import csv
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
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


def parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def parse_json(value: Any, default: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if value in (None, ""):
        return default
    try:
        return json.loads(str(value))
    except Exception:
        return default


def failed_gates(signal: dict[str, Any]) -> list[str]:
    details = parse_json(signal.get("details"), {})
    failed: list[str] = []
    if isinstance(details, dict):
        trade = details.get("trade_eligibility") or {}
        if isinstance(trade, dict):
            failed.extend(str(x) for x in (trade.get("failed") or []))
        data_quality = details.get("data_quality") or {}
        if isinstance(data_quality, dict) and data_quality.get("blocked"):
            failed.append("DATA_QUALITY_RED")
    if str(signal.get("status") or "").upper() == "BLOCKED_DATA" and not any("DATA" in x for x in failed):
        failed.append("BLOCKED_DATA")
    return sorted(set(failed))


def in_window(row: dict[str, Any], field: str, start: datetime, end: datetime) -> bool:
    dt = parse_dt(row.get(field))
    return bool(dt and start <= dt < end)


def pct_change(current: float, previous: float) -> float | None:
    if previous == 0:
        return None if current == 0 else 100.0
    return (current - previous) / abs(previous) * 100.0


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fields.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        if not fields:
            return
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    client = _client()
    now = datetime.now(timezone.utc)
    current_start = now - timedelta(hours=48)
    previous_start = current_start - timedelta(hours=48)

    data = {name: fetch_all(client, table) for name, table in TABLES.items()}
    signals = data["signals"]
    positions = data["positions"]
    outcomes = data["outcomes"]
    backtests = data["backtests"]

    current = [r for r in signals if in_window(r, "created_at", current_start, now)]
    previous = [r for r in signals if in_window(r, "created_at", previous_start, current_start)]
    current_positions = [r for r in positions if in_window(r, "opened_at", current_start, now)]
    previous_positions = [r for r in positions if in_window(r, "opened_at", previous_start, current_start)]

    def period_stats(rows: list[dict[str, Any]], opened: list[dict[str, Any]]) -> dict[str, Any]:
        statuses = Counter(str(r.get("status") or "N/D").upper() for r in rows)
        return {
            "signals": len(rows),
            "pre_buy": statuses.get("PRE_BUY", 0),
            "near_setup": statuses.get("NEAR_SETUP", 0),
            "confirmed": statuses.get("CONFIRMED", 0),
            "blocked_data": statuses.get("BLOCKED_DATA", 0),
            "paper_open": len(opened),
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
    gate_counter: Counter[tuple[str, str]] = Counter()
    for strategy in strategies:
        rows = [r for r in current if str(r.get("strategy") or "") == strategy]
        all_rows = [r for r in signals if str(r.get("strategy") or "") == strategy]
        opens = [r for r in current_positions if str(r.get("strategy") or "") == strategy]
        statuses = Counter(str(r.get("status") or "N/D").upper() for r in rows)
        for row in rows:
            for gate in failed_gates(row):
                gate_counter[(strategy, gate)] += 1

        bt = backtest_by_strategy.get(strategy, [])
        pf_values = [float(r["profit_factor"]) for r in bt if r.get("profit_factor") not in (None, "")]
        ret_values = [float(r["avg_return_pct"]) for r in bt if r.get("avg_return_pct") not in (None, "")]
        avg_pf = sum(pf_values) / len(pf_values) if pf_values else None
        avg_ret = sum(ret_values) / len(ret_values) if ret_values else None

        outs = outcome_by_strategy.get(strategy, [])
        d1 = [float(r["ret_d1"]) for r in outs if r.get("ret_d1") not in (None, "")]
        avg_d1 = sum(d1) / len(d1) if d1 else None

        conversion = (len(opens) / len(rows) * 100.0) if rows else 0.0
        blocked_ratio = (statuses.get("BLOCKED_DATA", 0) / len(rows)) if rows else 0.0
        if len(all_rows) < 10 or len(rows) < 3:
            health = "UNDERTESTED"
        elif blocked_ratio >= 0.30:
            health = "REVIEW"
        elif len(rows) >= 10 and conversion < 3.0:
            health = "REVIEW"
        elif avg_pf is not None and avg_pf >= 1.40 and (avg_ret or 0) > 0:
            health = "PROMISING"
        else:
            health = "ACTIVE"

        strategy_summary.append({
            "strategy": strategy,
            "signals_48h": len(rows),
            "pre_buy_48h": statuses.get("PRE_BUY", 0),
            "near_setup_48h": statuses.get("NEAR_SETUP", 0),
            "confirmed_48h": statuses.get("CONFIRMED", 0),
            "blocked_data_48h": statuses.get("BLOCKED_DATA", 0),
            "paper_open_48h": len(opens),
            "conversion_pct_48h": round(conversion, 2),
            "backtest_avg_profit_factor": round(avg_pf, 3) if avg_pf is not None else None,
            "backtest_avg_return_pct": round(avg_ret, 3) if avg_ret is not None else None,
            "forward_d1_samples": len(d1),
            "forward_avg_ret_d1_pct": round(avg_d1, 3) if avg_d1 is not None else None,
            "lab_status": health,
        })

    gate_rows = [
        {"strategy": strategy, "gate": gate, "blocked_48h": count}
        for (strategy, gate), count in gate_counter.most_common()
    ]

    dominant_gate = gate_rows[0]["gate"] if gate_rows else "N/D"
    overall_status = "HEALTHY"
    notes: list[str] = []
    if cur_stats["signals"] >= 10 and cur_stats["conversion_pct"] < 3.0:
        overall_status = "BOTTLENECK"
        notes.append("Conversione segnale→paper sotto 3% nelle ultime 48h")
    if cur_stats["blocked_data"] and cur_stats["signals"] and cur_stats["blocked_data"] / cur_stats["signals"] >= 0.20:
        overall_status = "REVIEW"
        notes.append("BLOCKED_DATA >=20% dei segnali nelle ultime 48h")
    if not cur_stats["signals"]:
        overall_status = "NO_ACTIVITY"
        notes.append("Nessun nuovo segnale nelle ultime 48h")

    report = {
        "generated_at_utc": now.isoformat(),
        "window_current": {"from": current_start.isoformat(), "to": now.isoformat()},
        "window_previous": {"from": previous_start.isoformat(), "to": current_start.isoformat()},
        "overall_status": overall_status,
        "dominant_gate": dominant_gate,
        "notes": notes,
        "current_48h": cur_stats,
        "previous_48h": prev_stats,
        "comparison": comparison,
        "strategy_summary": strategy_summary,
        "gate_failures": gate_rows,
    }

    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path("artifacts") / f"lab_health_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "lab_health_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(out_dir / "strategy_summary.csv", strategy_summary)
    write_csv(out_dir / "gate_failures.csv", gate_rows)
    write_csv(out_dir / "signals_48h.csv", current)

    md = [
        "# Laboratory Health Report",
        "",
        f"Generated: {now.isoformat()}",
        f"Status: **{overall_status}**",
        f"Dominant gate: **{dominant_gate}**",
        "",
        "## Last 48h",
        f"- Signals: {cur_stats['signals']}",
        f"- PRE_BUY: {cur_stats['pre_buy']}",
        f"- NEAR_SETUP: {cur_stats['near_setup']}",
        f"- CONFIRMED: {cur_stats['confirmed']}",
        f"- BLOCKED_DATA: {cur_stats['blocked_data']}",
        f"- Paper opens: {cur_stats['paper_open']}",
        f"- Signal→paper conversion: {cur_stats['conversion_pct']}%",
        "",
        "## Notes",
    ]
    md.extend([f"- {x}" for x in notes] or ["- Nessuna criticità automatica rilevata."])
    (out_dir / "LAB_HEALTH_REPORT.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(json.dumps({"status": overall_status, "current_48h": cur_stats, "dominant_gate": dominant_gate}, ensure_ascii=False))
    print(f"REPORT_DIR={out_dir}")


if __name__ == "__main__":
    main()
