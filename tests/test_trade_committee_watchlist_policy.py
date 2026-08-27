from trade_committee.watchlist_policy import (
    core_validation_required,
    trade_plan_source,
    transition,
)


def test_watch_to_approaching_is_alert_worthy():
    result = transition("WATCH", "APPROACHING")
    assert result.alert is True
    assert result.active is True


def test_no_longer_interesting_is_archived_not_deleted():
    result = transition("APPROACHING", "NO_LONGER_INTERESTING")
    assert result.alert is True
    assert result.active is False


def test_committee_only_plan_is_explicit_and_requires_core_validation():
    assert trade_plan_source(False) == "COMMITTEE_ESTIMATE"
    assert core_validation_required(False) is True


def test_core_plan_is_authoritative():
    assert trade_plan_source(True) == "CORE"
    assert core_validation_required(True) is False
