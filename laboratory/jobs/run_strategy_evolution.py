from __future__ import annotations

import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parents[1]
SRC = LAB_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lab.db import get_supabase_client
from lab.evolution import evaluate_family
from lab.market_data import MarketDataRequest, download_prices
from lab.strategies import STRATEGIES

DEFAULT_SYMBOLS = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "PGR", "AXP", "CVS", "ADBE", "NVO"]
PRICE_STRATEGIES = [name for name, spec in STRATEGIES.items() if spec.generator is not None]


def symbols() -> list[str]:
    raw = os.getenv("LAB_SYMBOLS", "")
    return [x.strip().upper() for x in raw.split(",") if x.strip()] or DEFAULT_SYMBOLS


def variant_id(strategy: str, params: dict) -> str:
    raw = json.dumps({"strategy": strategy, "parameters": params}, sort_keys=True).encode("utf-8")
    digest = hashlib.sha1(raw).hexdigest()[:10]
    return f"{strategy}__g1__{digest}"


def evaluation_id(variant: str, symbol: str, stamp: str) -> str:
    raw = f"{variant}|{symbol}|{stamp}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()


def _record_run_start(client, stamp: str) -> None:
    """Best-effort: a logging failure must never block the evolution run itself."""
    try:
        client.table("lab_evolution_runs").insert({
            "run_stamp": stamp,
            "status": "RUNNING",
            "symbols_requested": symbols(),
            "strategies_requested": PRICE_STRATEGIES,
        }).execute()
    except Exception as exc:
        print(f"lab_evolution_runs start logging failed (non-blocking): {exc}")


def _record_run_finish(client, stamp: str, *, status: str, variants_written: int,
                        evals_written: int, promotable: int,
                        symbol_failures: list[str], variant_write_failures: list[str]) -> None:
    """Best-effort: a logging failure must never mask the real run outcome."""
    try:
        client.table("lab_evolution_runs").update({
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "variants_written": variants_written,
            "evaluations_written": evals_written,
            "promotable_variants": promotable,
            "symbol_failures": symbol_failures,
            "variant_write_failures": variant_write_failures,
        }).eq("run_stamp", stamp).execute()
    except Exception as exc:
        print(f"lab_evolution_runs finish logging failed (non-blocking): {exc}")


def main() -> int:
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_SECRET_KEY"):
        print("Supabase secrets missing")
        return 2

    client = get_supabase_client()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    symbol_failures: list[str] = []
    variant_write_failures: list[str] = []

    _record_run_start(client, stamp)

    for symbol in symbols():
        try:
            prices = download_prices(MarketDataRequest(symbol=symbol, start="2020-01-01"))
            if len(prices) < 350:
                symbol_failures.append(f"{symbol}: insufficient history")
                continue
            for strategy in PRICE_STRATEGIES:
                try:
                    for row in evaluate_family(symbol, prices, strategy):
                        vid = variant_id(strategy, row["parameters"])
                        row["variant_id"] = vid
                        grouped[(strategy, vid)].append(row)
                except Exception as exc:
                    symbol_failures.append(f"{symbol}/{strategy}: {type(exc).__name__}: {exc}")
        except Exception as exc:
            symbol_failures.append(f"{symbol}: {type(exc).__name__}: {exc}")

    variants_written = 0
    evals_written = 0
    promotable = 0

    for (strategy, vid), rows in grouped.items():
        # Each variant group is written in isolation: one failing write (network
        # hiccup, transient Supabase error) must not discard every other
        # variant already computed in this run. Previously an unhandled
        # exception here silently aborted the whole write loop.
        try:
            params = rows[0]["parameters"]
            mean_score = sum(float(r["robustness_score"]) for r in rows) / max(len(rows), 1)
            positive = sum(r["verdict"] in {"CANDIDATE", "PROMOTABLE"} for r in rows)
            promoted_votes = sum(r["verdict"] == "PROMOTABLE" for r in rows)
            coverage = positive / max(len(rows), 1)

            critique_counts: Counter[str] = Counter()
            for r in rows:
                critique_counts.update(r.get("parent_critique", []))
            critique_summary = ", ".join(f"{k}:{v}" for k, v in critique_counts.most_common()) or "N/D"

            if len(rows) >= 5 and mean_score >= 70 and coverage >= 0.60 and promoted_votes >= 2:
                family_status = "PROMOTABLE"
                promotable += 1
            elif len(rows) >= 5 and mean_score >= 60 and coverage >= 0.50:
                family_status = "CANDIDATE"
            else:
                family_status = "REJECTED"

            variant_payload = {
                "variant_id": vid,
                "parent_strategy": strategy,
                "parent_variant_id": None,
                "generation": 1,
                "parameters": params,
                "mutation_reason": f"Parent critique across universe: {critique_summary}. Generation-1 mutation varies entry threshold, ATR stop and R target.",
                "status": family_status,
                "promoted_to_core": False,
                "notes": f"mean_robustness={mean_score:.2f}; coverage={coverage:.2%}; symbols={len(rows)}; run={stamp}",
            }
            client.table("lab_strategy_variants").upsert(variant_payload, on_conflict="variant_id").execute()
            variants_written += 1

            for r in rows:
                train = r["train"]
                oos = r["oos"]
                parent_oos = r["parent_oos"]
                details = {
                    "run": stamp,
                    "single_symbol_verdict": r["verdict"],
                    "parent_parameters": r["parent_parameters"],
                    "parent_oos": parent_oos,
                    "parent_critique": r.get("parent_critique", []),
                    "family_status": family_status,
                }
                payload = {
                    "evaluation_id": evaluation_id(vid, r["symbol"], stamp),
                    "variant_id": vid,
                    "symbol": r["symbol"],
                    "train_return_pct": train.get("return_pct"),
                    "oos_return_pct": oos.get("return_pct"),
                    "train_profit_factor": train.get("profit_factor"),
                    "oos_profit_factor": oos.get("profit_factor"),
                    "train_trades": train.get("trades"),
                    "oos_trades": oos.get("trades"),
                    "train_max_drawdown_pct": train.get("max_drawdown_pct"),
                    "oos_max_drawdown_pct": oos.get("max_drawdown_pct"),
                    "robustness_score": r["robustness_score"],
                    "verdict": r["verdict"],
                    "details": details,
                }
                try:
                    client.table("lab_strategy_evaluations").insert(payload).execute()
                    evals_written += 1
                except Exception as exc:
                    variant_write_failures.append(
                        f"{strategy}/{vid}/{r['symbol']}: evaluation insert failed: {type(exc).__name__}: {exc}"
                    )
        except Exception as exc:
            variant_write_failures.append(f"{strategy}/{vid}: variant write failed: {type(exc).__name__}: {exc}")

    status = "COMPLETED" if grouped else "NO_DATA"
    _record_run_finish(
        client, stamp, status=status, variants_written=variants_written,
        evals_written=evals_written, promotable=promotable,
        symbol_failures=symbol_failures, variant_write_failures=variant_write_failures,
    )

    print(json.dumps({
        "run": stamp,
        "strategies": PRICE_STRATEGIES,
        "symbols": symbols(),
        "variants_written": variants_written,
        "evaluations_written": evals_written,
        "promotable_variants": promotable,
        "symbol_failures": symbol_failures,
        "variant_write_failures": variant_write_failures,
        "research_only": True,
        "automatic_core_promotion": False,
    }, indent=2))
    return 0 if grouped else 1


if __name__ == "__main__":
    raise SystemExit(main())
