from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import pandas as pd

CORRELATION_POLICY_VERSION = "CORRELATION_POLICY_V1"
LOOKBACK_SESSIONS = 60
MIN_VALID_SESSIONS = 45
STRONG_CORRELATION = 0.75
CLUSTER_MIN_POSITIONS = 3


@dataclass(frozen=True)
class CorrelationCluster:
    members: tuple[str, ...]
    average_abs_correlation: float
    risk_flag: bool
    policy_version: str = CORRELATION_POLICY_VERSION


def _pair_corr(returns: pd.DataFrame, a: str, b: str) -> float | None:
    pair = returns[[a, b]].dropna()
    if len(pair) < MIN_VALID_SESSIONS:
        return None
    value = pair[a].corr(pair[b])
    return None if pd.isna(value) else float(value)


def strong_pairs(price_history: Mapping[str, Sequence[float] | pd.Series]) -> list[tuple[str, str, float]]:
    frame = pd.DataFrame({k: pd.Series(v, dtype=float) for k, v in price_history.items()})
    if frame.empty:
        return []
    returns = frame.tail(LOOKBACK_SESSIONS + 1).pct_change().iloc[1:]
    names = sorted(frame.columns)
    out: list[tuple[str, str, float]] = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            corr = _pair_corr(returns, a, b)
            if corr is not None and abs(corr) >= STRONG_CORRELATION:
                out.append((a, b, corr))
    return out


def correlation_clusters(price_history: Mapping[str, Sequence[float] | pd.Series]) -> list[CorrelationCluster]:
    pairs = strong_pairs(price_history)
    graph: dict[str, set[str]] = {}
    pair_values: dict[frozenset[str], float] = {}
    for a, b, corr in pairs:
        graph.setdefault(a, set()).add(b)
        graph.setdefault(b, set()).add(a)
        pair_values[frozenset((a, b))] = abs(corr)

    seen: set[str] = set()
    clusters: list[CorrelationCluster] = []
    for start in sorted(graph):
        if start in seen:
            continue
        stack = [start]
        component: set[str] = set()
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            component.add(node)
            stack.extend(graph.get(node, set()) - seen)
        members = tuple(sorted(component))
        values = [
            value for pair, value in pair_values.items()
            if pair.issubset(component)
        ]
        avg = sum(values) / len(values) if values else 0.0
        clusters.append(CorrelationCluster(members, avg, len(members) >= CLUSTER_MIN_POSITIONS))
    return clusters
