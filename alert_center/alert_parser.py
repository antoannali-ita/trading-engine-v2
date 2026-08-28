from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta
from typing import Any


@dataclass(frozen=True)
class ParsedAlert:
    ticker: str
    condition_type: str
    trigger_level: float
    expires_at: str
    market: str = "USA"
    source: str = "CHAT"
    confidence: str = "HIGH"
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ParseResult:
    status: str
    alerts: list[ParsedAlert]
    errors: list[str]
    raw_text: str

    @property
    def needs_llm(self) -> bool:
        return self.status == "LOW_CONFIDENCE"


TICKER_ALIASES = {
    "MICROSOFT": "MSFT",
    "MSFT": "MSFT",
    "S&P GLOBAL": "SPGI",
    "SP GLOBAL": "SPGI",
    "SPGI": "SPGI",
    "NVIDIA": "NVDA",
    "NVDA": "NVDA",
    "NOVO NORDISK": "NVO",
    "NORDISK": "NVO",
    "NVO": "NVO",
    "ORACLE": "ORCL",
    "ORCL": "ORCL",
    "ALPHABET": "GOOGL",
    "GOOGLE": "GOOGL",
    "GOOGL": "GOOGL",
    "AIRBNB": "ABNB",
    "ABNB": "ABNB",
    "AMERICAN EXPRESS": "AXP",
    "AXP": "AXP",
    "CHUBB": "CB",
    "CB": "CB",
    "NETEASE": "NTES",
    "NTES": "NTES",
    "TAIWAN SEMI": "TSM",
    "TAIWAN SEMICONDUCTOR": "TSM",
    "TSM": "TSM",
    "TJX": "TJX",
    "CVS": "CVS",
    "INTUIT": "INTU",
    "INTU": "INTU",
    "OVINTIV": "OVV",
    "OVV": "OVV",
    "NATL FUEL GAS": "NFG",
    "NATIONAL FUEL GAS": "NFG",
    "NFG": "NFG",
    "AB INBEV": "BUD",
    "ANHEUSER BUSCH": "BUD",
    "BUD": "BUD",
    "BARRICK": "B",
}

_ABOVE_WORDS = r"(?:>=|>|sopra|oltre|supera|superiore\s+a|maggiore\s+di|maggiore\s+a)"
_BELOW_WORDS = r"(?:<=|<|sotto|perde|inferiore\s+a|minore\s+di|minore\s+a)"
_PRICE_RE = re.compile(r"(?P<value>\d+(?:[\.,]\d+)?)")
_DATE_NUM_RE = re.compile(r"(?P<day>\d{1,2})[/-](?P<month>\d{1,2})(?:[/-](?P<year>\d{2,4}))?")


def _normalize_number(raw: str) -> float:
    return float(raw.replace(".", "").replace(",", ".")) if "," in raw and "." in raw else float(raw.replace(",", "."))


def _resolve_ticker(text: str) -> str | None:
    upper = text.upper().strip()
    # Prefer aliases with spaces before generic all-caps token detection.
    for alias in sorted(TICKER_ALIASES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", upper):
            return TICKER_ALIASES[alias]
    candidates = re.findall(r"\b[A-Z]{1,5}\b", upper)
    ignored = {"SOPRA", "SOTTO", "FINO", "AL", "IL", "E", "USA", "NYSE", "NASDAQ", "PREZZO"}
    for candidate in candidates:
        if candidate not in ignored:
            return candidate
    return None


def _parse_expiry(text: str, today: date) -> date:
    lower = text.lower()
    m = _DATE_NUM_RE.search(text)
    if m:
        year = m.group("year")
        resolved_year = today.year if not year else int(year) + (2000 if len(year) == 2 else 0)
        candidate = date(resolved_year, int(m.group("month")), int(m.group("day")))
        if not year and candidate < today:
            candidate = candidate.replace(year=today.year + 1)
        return candidate

    month_map = {
        "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4,
        "maggio": 5, "giugno": 6, "luglio": 7, "agosto": 8,
        "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
    }
    for name, month in month_map.items():
        mm = re.search(rf"\b(\d{{1,2}})\s+{name}\b", lower)
        if mm:
            candidate = date(today.year, month, int(mm.group(1)))
            if candidate < today:
                candidate = candidate.replace(year=today.year + 1)
            return candidate

    if "fine mese" in lower or "fine del mese" in lower:
        first_next = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
        return first_next - timedelta(days=1)

    return today + timedelta(days=30)


def _split_segments(text: str) -> list[str]:
    cleaned = text.replace(";", "\n")
    lines = [line.strip(" -•\t") for line in cleaned.splitlines() if line.strip()]
    if len(lines) > 1:
        return lines
    # Conservative split: commas only when followed by a likely ticker/name and a trigger word.
    parts = re.split(r"\s*,\s*(?=(?:[A-Za-z&\. ]{1,30})\s+(?:sopra|sotto|>|<|>=|<=))", cleaned, flags=re.IGNORECASE)
    return [p.strip() for p in parts if p.strip()]


def _extract_conditions(segment: str) -> list[tuple[str, float]]:
    found: list[tuple[int, str, float]] = []
    for condition_type, words in (("PRICE_ABOVE", _ABOVE_WORDS), ("PRICE_BELOW", _BELOW_WORDS)):
        pattern = re.compile(rf"{words}\s*(?:a\s*)?(?:quota\s*)?(?P<price>\d+(?:[\.,]\d+)?)", re.IGNORECASE)
        for match in pattern.finditer(segment):
            found.append((match.start(), condition_type, _normalize_number(match.group("price"))))
    found.sort(key=lambda x: x[0])
    return [(condition, price) for _, condition, price in found]


def parse_alert_text(text: str, *, today: date | None = None) -> ParseResult:
    today = today or date.today()
    raw = str(text or "").strip()
    if not raw:
        return ParseResult("LOW_CONFIDENCE", [], ["Testo vuoto"], raw)

    alerts: list[ParsedAlert] = []
    errors: list[str] = []
    previous_ticker: str | None = None

    for segment in _split_segments(raw):
        ticker = _resolve_ticker(segment) or previous_ticker
        if ticker:
            previous_ticker = ticker
        conditions = _extract_conditions(segment)
        expiry = _parse_expiry(segment, today)

        if not ticker:
            errors.append(f"Ticker non riconosciuto: {segment}")
            continue
        if not conditions:
            errors.append(f"Condizione/prezzo non riconosciuti per {ticker}: {segment}")
            continue

        for condition_type, level in conditions:
            if level <= 0:
                errors.append(f"Prezzo non valido per {ticker}: {level}")
                continue
            alerts.append(
                ParsedAlert(
                    ticker=ticker,
                    condition_type=condition_type,
                    trigger_level=level,
                    expires_at=f"{expiry.isoformat()}T23:59:00+02:00",
                    note="Creato da Alert Assistant parser",
                )
            )

    # Deduplicate exact parses inside one paste.
    unique: dict[tuple[str, str, float, str], ParsedAlert] = {}
    for alert in alerts:
        key = (alert.ticker, alert.condition_type, alert.trigger_level, alert.expires_at)
        unique[key] = alert
    parsed = list(unique.values())

    if parsed and not errors:
        return ParseResult("HIGH_CONFIDENCE", parsed, [], raw)
    if parsed:
        return ParseResult("PARTIAL", parsed, errors, raw)
    return ParseResult("LOW_CONFIDENCE", [], errors or ["Nessun alert riconosciuto"], raw)


def validate_parsed_alerts(alerts: list[ParsedAlert], existing_rows: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    existing_rows = existing_rows or []
    existing_keys = {
        (
            str(row.get("ticker") or "").upper(),
            str(row.get("condition_type") or "").upper(),
            float(row.get("trigger_level")),
        )
        for row in existing_rows
        if row.get("ticker") and row.get("condition_type") and row.get("trigger_level") is not None
    }

    output: list[dict[str, Any]] = []
    for alert in alerts:
        key = (alert.ticker, alert.condition_type, float(alert.trigger_level))
        status = "DUPLICATE" if key in existing_keys else "OK"
        item = alert.to_dict()
        item["validation"] = status
        output.append(item)
    return output
