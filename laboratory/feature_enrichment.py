"""Passive Laboratory feature enrichment.

LAB-FEAT-001 collects candidate explanatory features without changing signal
eligibility, paper-position opening, score, entry, stop, sizing or decisions.
Production must not import this module.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

FEATURE_SET_VERSION = "LAB-FEAT-001.v1"
FEATURE_PROVIDER = "TRADINGVIEW"

# Benchmark definitions are versioned before data collection. The benchmark
# itself is metadata; RS calculation belongs to the collector/provider layer.
RS_BENCHMARKS = {
    "USA": {"symbol": "SPY", "definition_version": "RS-BENCHMARK.v1"},
    "ITALY": {"symbol": "FTSEMIB", "definition_version": "RS-BENCHMARK.v1"},
}

# Raw/continuous values only. No thresholds are encoded here on purpose.
CANDIDATE_FEATURES = (
    "relative_volume",
    "relative_strength_1m",
    "relative_strength_3m",
    "relative_strength_6m",
    "distance_sma20_pct",
    "distance_sma50_pct",
    "distance_sma200_pct",
    "atr14",
    "atr14_pct",
    "gap_pct",
    "distance_52w_high_pct",
    "distance_52w_low_pct",
)


@dataclass(frozen=True)
class FeatureSnapshot:
    market: str
    symbol: str
    strategy: str
    strategy_version: str
    observed_at: str
    provider: str
    feature_set_version: str
    benchmark_symbol: str
    benchmark_definition_version: str
    values: dict[str, float | None]
    source_metadata: dict[str, Any]

    def as_record(self) -> dict[str, Any]:
        return asdict(self)


def build_feature_snapshot(
    *,
    market: str,
    symbol: str,
    strategy: str,
    strategy_version: str,
    raw_features: Mapping[str, Any],
    source_metadata: Mapping[str, Any] | None = None,
    observed_at: datetime | None = None,
) -> FeatureSnapshot:
    """Normalize passive metadata for an already-generated Laboratory signal.

    Unknown fields are deliberately ignored. Missing fields remain None. This
    function performs no filtering and returns no trading decision.
    """
    normalized_market = str(market).upper()
    if normalized_market not in RS_BENCHMARKS:
        raise ValueError(f"Unsupported market for LAB-FEAT-001: {market}")

    benchmark = RS_BENCHMARKS[normalized_market]
    values: dict[str, float | None] = {}
    for name in CANDIDATE_FEATURES:
        value = raw_features.get(name)
        try:
            values[name] = float(value) if value is not None else None
        except (TypeError, ValueError):
            values[name] = None

    timestamp = observed_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    return FeatureSnapshot(
        market=normalized_market,
        symbol=str(symbol).upper(),
        strategy=str(strategy),
        strategy_version=str(strategy_version or "UNVERSIONED"),
        observed_at=timestamp.astimezone(timezone.utc).isoformat(),
        provider=FEATURE_PROVIDER,
        feature_set_version=FEATURE_SET_VERSION,
        benchmark_symbol=benchmark["symbol"],
        benchmark_definition_version=benchmark["definition_version"],
        values=values,
        source_metadata=dict(source_metadata or {}),
    )
