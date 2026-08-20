from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

LAB_ROOT = Path(__file__).resolve().parents[1]
SRC = LAB_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lab.backtest_engine import BacktestConfig, run_backtest
from lab.market_data import MarketDataRequest, download_prices
from lab.strategies import DataRequired, STRATEGIES


DEFAULT_SYMBOLS = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "PGR", "AXP", "CVS", "ADBE", "NVO"]
PRICE_STRATEGIES = [name for name, spec in STRATEGIES.items() if spec.generator is not None]


def _symbols() -> list[str]:
    raw = os.getenv("LAB_SYMBOLS", "")
    return [x.strip().upper() for x in raw.split(",") if x.strip()] or DEFAULT_SYMBOLS


def main() -> int:
    run_id = f"LAB_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    start = os.getenv("LAB_START", "2020-01-01")
    symbols = _symbols()
    output = LAB_ROOT / "results" / run_id
    output.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    failures: list[dict] = []
    cfg = BacktestConfig()

    for symbol in symbols:
        try:
            prices = download_prices(MarketDataRequest(symbol=symbol, start=start))
        except Exception as exc:
            failures.append({"symbol": symbol, "stage": "market_data", "error": str(exc)})
            continue

        for strategy in PRICE_STRATEGIES:
            try:
                trades, metrics = run_backtest(symbol, prices, strategy, cfg)
                metrics["data_status"] = "OK"
                rows.append(metrics)
                if not trades.empty:
                    trades.to_csv(output / f"{symbol}_{strategy}_trades.csv", index=False)
            except DataRequired as exc:
                rows.append({"symbol": symbol, "strategy": strategy, "data_status": "DATA_REQUIRED", "error": str(exc)})
            except Exception as exc:
                failures.append({"symbol": symbol, "strategy": strategy, "stage": "backtest", "error": str(exc)})

    results = pd.DataFrame(rows)
    results.to_csv(output / "summary.csv", index=False)
    manifest = {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "symbols": symbols,
        "strategies_executed": PRICE_STRATEGIES,
        "strategies_waiting_for_data": [name for name, spec in STRATEGIES.items() if spec.generator is None],
        "failures": failures,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    if not results.empty:
        print(results.to_string(index=False))
    return 0 if rows else 2


if __name__ == "__main__":
    raise SystemExit(main())
