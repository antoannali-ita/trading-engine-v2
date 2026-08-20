from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parents[1]
SRC = LAB_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lab.db import get_supabase_client
from lab.indicators import enrich_prices
from lab.market_data import MarketDataRequest, download_prices
from lab.strategies import STRATEGIES, generate_scores

DEFAULT_SYMBOLS = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "PGR", "AXP", "CVS", "ADBE", "NVO"]
PRICE_STRATEGIES = [name for name, spec in STRATEGIES.items() if spec.generator is not None]


def symbols() -> list[str]:
    raw = os.getenv("LAB_SYMBOLS", "")
    return [x.strip().upper() for x in raw.split(",") if x.strip()] or DEFAULT_SYMBOLS


def main() -> int:
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_SECRET_KEY"):
        print("Supabase secrets missing; no paper signals persisted")
        return 2

    client = get_supabase_client()
    threshold = float(os.getenv("LAB_PAPER_SCORE", "75"))
    written = 0

    for symbol in symbols():
        try:
            prices = download_prices(MarketDataRequest(symbol=symbol, start="2024-01-01"))
            x = enrich_prices(prices)
            if len(x) < 220:
                continue
            last = x.iloc[-1]
            signal_date = x.index[-1].date().isoformat()
            for strategy in PRICE_STRATEGIES:
                score = float(generate_scores(strategy, prices).iloc[-1])
                if score < threshold:
                    continue
                price = float(last.Close)
                atr = float(last.atr14)
                if not atr > 0:
                    continue
                stop = price - 2.0 * atr
                target = price + 2.5 * (price - stop)
                payload = {
                    "symbol": symbol,
                    "strategy": strategy,
                    "signal_date": signal_date,
                    "score": score,
                    "price": price,
                    "proposed_entry": price,
                    "proposed_stop": stop,
                    "proposed_target": target,
                    "status": "PAPER_ONLY",
                    "details": {
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                        "sma20": None if str(last.sma20) == "nan" else float(last.sma20),
                        "sma50": None if str(last.sma50) == "nan" else float(last.sma50),
                        "sma200": None if str(last.sma200) == "nan" else float(last.sma200),
                        "rsi14": None if str(last.rsi14) == "nan" else float(last.rsi14),
                        "atr14": atr,
                    },
                }
                client.table("lab_paper_signals").upsert(payload, on_conflict="symbol,strategy,signal_date").execute()
                written += 1
        except Exception as exc:
            print(f"{symbol}: {exc}")

    print(f"paper signals written: {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
