from datetime import date

from alert_center.alert_parser import parse_alert_text, validate_parsed_alerts


def test_parses_multiple_lines_and_multiple_conditions():
    result = parse_alert_text(
        "MSFT sopra 525 fino al 15/09\nSPGI sopra 445 e sotto 425 fino al 25/09\nNVO sopra 48,2 fino al 15 settembre",
        today=date(2026, 8, 28),
    )
    assert result.status == "HIGH_CONFIDENCE"
    assert len(result.alerts) == 4
    assert [(a.ticker, a.condition_type, a.trigger_level) for a in result.alerts] == [
        ("MSFT", "PRICE_ABOVE", 525.0),
        ("SPGI", "PRICE_ABOVE", 445.0),
        ("SPGI", "PRICE_BELOW", 425.0),
        ("NVO", "PRICE_ABOVE", 48.2),
    ]
    assert result.alerts[0].expires_at.startswith("2026-09-15")
    assert result.alerts[1].expires_at.startswith("2026-09-25")


def test_parses_symbols_and_aliases():
    result = parse_alert_text(
        "Microsoft >= 520 fino al 16/09\nOracle < 145 fino al 10/09",
        today=date(2026, 8, 28),
    )
    assert result.status == "HIGH_CONFIDENCE"
    assert result.alerts[0].ticker == "MSFT"
    assert result.alerts[1].ticker == "ORCL"


def test_low_confidence_does_not_invent_levels():
    result = parse_alert_text(
        "Microsoft se torna sulla zona che avevamo detto",
        today=date(2026, 8, 28),
    )
    assert result.status == "LOW_CONFIDENCE"
    assert result.alerts == []
    assert result.needs_llm is True


def test_duplicate_validation():
    result = parse_alert_text("MSFT sopra 525 fino al 15/09", today=date(2026, 8, 28))
    validated = validate_parsed_alerts(
        result.alerts,
        [{"ticker": "MSFT", "condition_type": "PRICE_ABOVE", "trigger_level": 525}],
    )
    assert validated[0]["validation"] == "DUPLICATE"


def test_default_expiry_is_30_days():
    result = parse_alert_text("MSFT sopra 525", today=date(2026, 8, 28))
    assert result.status == "HIGH_CONFIDENCE"
    assert result.alerts[0].expires_at.startswith("2026-09-27")
