from engine.market_rules import financial_adjustment_enabled


def test_financial_adjustment_is_italy_only():
    assert financial_adjustment_enabled(
        {"market": "ITALY", "financial_sector_adjustment": True}, "Financial Services"
    )
    assert financial_adjustment_enabled(
        {"market": "ITALY", "financial_sector_adjustment": True}, "Banca"
    )
    assert not financial_adjustment_enabled(
        {"market": "USA", "financial_sector_adjustment": True}, "Financial Services"
    )


def test_non_financial_italian_sector_not_adjusted():
    assert not financial_adjustment_enabled(
        {"market": "ITALY", "financial_sector_adjustment": True}, "Industrials"
    )
