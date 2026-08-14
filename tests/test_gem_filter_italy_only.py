from engine.market_rules import should_exclude_gem


def test_gem_pattern_excluded_only_in_italy():
    italy = {"market": "ITALY", "gem_filter_enabled": True}
    usa = {"market": "USA", "gem_filter_enabled": True}
    assert should_exclude_gem(italy, "1LOGN")
    assert should_exclude_gem(italy, "1NFLX")
    assert not should_exclude_gem(usa, "1LOGN")


def test_normal_italian_tickers_are_not_excluded():
    italy = {"market": "ITALY", "gem_filter_enabled": True}
    assert not should_exclude_gem(italy, "TEN")
    assert not should_exclude_gem(italy, "STLAM")
