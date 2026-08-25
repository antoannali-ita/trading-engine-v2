import pandas as pd

from lab.correlation import correlation_clusters, strong_pairs


def test_correlation_requires_minimum_history():
    prices = {
        "A": pd.Series(range(40), dtype=float) + 100,
        "B": pd.Series(range(40), dtype=float) + 200,
    }
    assert strong_pairs(prices) == []


def test_three_highly_correlated_assets_form_risk_cluster():
    base = pd.Series([100 + i * 0.7 + (i % 5) * 0.2 for i in range(70)], dtype=float)
    prices = {
        "A": base,
        "B": base * 1.3 + 5,
        "C": base * 0.8 + 11,
    }
    clusters = correlation_clusters(prices)
    assert len(clusters) == 1
    assert clusters[0].members == ("A", "B", "C")
    assert clusters[0].risk_flag is True
