from __future__ import annotations

from dataclasses import dataclass

WATCH_STATES = {
    "WATCH",
    "APPROACHING",
    "RECHECK_REQUIRED",
    "READY_FOR_COMMITTEE",
    "APPROVABLE",
    "NO_LONGER_INTERESTING",
    "EXPIRED",
}

ALERT_TRANSITIONS = {
    ("WATCH", "APPROACHING"),
    ("APPROACHING", "READY_FOR_COMMITTEE"),
    ("RECHECK_REQUIRED", "READY_FOR_COMMITTEE"),
    ("READY_FOR_COMMITTEE", "APPROVABLE"),
    ("WATCH", "NO_LONGER_INTERESTING"),
    ("APPROACHING", "NO_LONGER_INTERESTING"),
    ("READY_FOR_COMMITTEE", "NO_LONGER_INTERESTING"),
}


@dataclass(frozen=True)
class WatchTransition:
    previous: str
    current: str
    alert: bool
    active: bool


def transition(previous: str, current: str) -> WatchTransition:
    prev = previous.upper()
    cur = current.upper()
    if prev not in WATCH_STATES or cur not in WATCH_STATES:
        raise ValueError(f"Unsupported watchlist transition: {previous} -> {current}")
    return WatchTransition(
        previous=prev,
        current=cur,
        alert=(prev, cur) in ALERT_TRANSITIONS,
        active=cur not in {"NO_LONGER_INTERESTING", "EXPIRED"},
    )


def trade_plan_source(core_snapshot_available: bool) -> str:
    return "CORE" if core_snapshot_available else "COMMITTEE_ESTIMATE"


def core_validation_required(core_snapshot_available: bool) -> bool:
    """Committee-only estimates may be watched but can never be APPROVABLE."""
    return not core_snapshot_available
