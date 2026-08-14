"""
Italy Tactical Opportunity Monitor v1.2
=====================================

Obiettivo
---------
Selezionare opportunità italiane con orizzonte 3-6 mesi combinando:
- valutazione
- qualità del business
- crescita e qualità degli utili
- solidità finanziaria
- catalyst/expectations (proxy quantitativo quando i dati qualitativi non sono affidabili)
- setup tecnico essenziale
- relative strength e volumi
- entry / stop / TP1 / TP2
- R/R netto commissioni
- portfolio fit
- storico Change-First

Principi
--------
1) Pochi hard filter di sopravvivenza; il resto è scoring/penalty.
2) Nessun obbligo di produrre 5 BUY.
3) Score decide SE; rischio e stop decidono QUANTO.
4) R/R è calcolato al netto delle commissioni.
5) Dati mancanti non vengono inventati: sono N/D e abbassano la data quality.
6) Storico persistente SQLite: NEW/REPEAT/UPGRADE/DOWNGRADE/BUY_ZONE/DROPPED.
7) Ogni run genera anche un JSON standardizzato per forward test e audit.
8) Il link al grafico TradingView resta nell'email.

Dipendenze attese nel repository GitHub:
    pip install pandas numpy yfinance tradingview-screener

Mailer:
    integrato direttamente nello script tramite SMTP Gmail.
    Non richiede mailer esterno né PAT_TOKEN.


Copyright / Proprietà
---------------------
Copyright (c) 2026 Antonio Larocca. Tutti i diritti riservati.
Questo script è destinato all'uso personale del proprietario.
Qualsiasi utilizzo, copia, modifica, distribuzione, pubblicazione,
riutilizzo totale o parziale da parte di terzi richiede preventiva
autorizzazione scritta del proprietario.

Nota: questa dicitura è un avviso di proprietà e condizioni d'uso;
non sostituisce una licenza software o una valutazione legale formale.

Adattamenti specifici Italia
---------------------------
- TradingView market: italy
- Yahoo Finance: suffisso .MI
- benchmark relativo: FTSE MIB
- prezzi/costi in EUR
- filtri liquidità/capitalizzazione più bassi rispetto agli USA
- banche/assicurazioni: niente penalità automatiche basate su FCF, D/E o Net Debt/EBITDA
- sessione automatica: 09:00-17:30 Europe/Rome, lun-ven, con chiusure 2026 configurabili

Nota importante
---------------
TradingView/yfinance non offrono in modo affidabile e uniforme tutte le variabili
qualitative (moat, management, conference call, catalizzatori discrezionali, ecc.).
Questa versione automatizza solo ciò che può essere derivato in modo ragionevole dai dati.
Le componenti qualitative non confermate sono esplicitamente marcate come proxy/N-D.
"""

from __future__ import annotations

import json
import math
import os
import re
import smtplib
import sqlite3
import ssl
import time
import warnings
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dataclasses import dataclass
from datetime import datetime, timezone, time as dt_time
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import yfinance as yf
from tradingview_screener import Column, Query


warnings.filterwarnings("ignore")


# =============================================================================
# VERSION / CONFIG
# =============================================================================

STRATEGY_VERSION = "MASTER_ITALY_v1.2"
REPORT_NAME = "Italia Tactical Value & Quality Monitor"

GMAIL_SENDER = os.getenv("GMAIL_SENDER", "").strip()
GMAIL_RECIPIENT = os.getenv("GMAIL_RECIPIENT", "").strip()
GMAIL_PASSWORD = os.getenv("GMAIL_PASSWORD", "").strip()
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
MAIL_TIMEOUT_SECONDS = int(os.getenv("MAIL_TIMEOUT_SECONDS", "30"))

TOP_N = int(os.getenv("TOP_N", "5"))
TOP_CANDIDATES_EMAIL = int(os.getenv("TOP_CANDIDATES_EMAIL", "10"))
MAX_CANDIDATES_PER_LENS = int(os.getenv("MAX_CANDIDATES_PER_LENS", "80"))
MAX_PER_SECTOR = int(os.getenv("MAX_PER_SECTOR", "2"))

# Costi Fineco / sizing
MAX_POSITION_SIZE = float(os.getenv("MAX_POSITION_SIZE", "2500"))
COMMISSION_PER_SIDE = float(os.getenv("COMMISSION_PER_SIDE", "19"))  # default conservativo Fineco Italia; configurabile
ROUND_TRIP_COMMISSION = COMMISSION_PER_SIDE * 2
TRADING_CAPITAL = float(os.getenv("TRADING_CAPITAL", "0"))  # 0 = non configurato
RISK_PCT_PER_TRADE = float(os.getenv("RISK_PCT_PER_TRADE", "0.0075"))
MAX_PORTFOLIO_HEAT = float(os.getenv("MAX_PORTFOLIO_HEAT", "0.05"))
MAX_SECTOR_EXPOSURE = float(os.getenv("MAX_SECTOR_EXPOSURE", "0.30"))

# Hard survival filter finali
MIN_PRICE = float(os.getenv("MIN_PRICE", "1"))
MIN_MARKET_CAP = float(os.getenv("MIN_MARKET_CAP", "200000000"))
MIN_AVG_DOLLAR_VOLUME = float(os.getenv("MIN_AVG_DOLLAR_VOLUME", "2000000"))
MIN_AVG_DOLLAR_VOLUME_SOFT = float(os.getenv("MIN_AVG_DOLLAR_VOLUME_SOFT", "750000"))

# Decision thresholds
MIN_SCORE_WATCH = int(os.getenv("MIN_SCORE_WATCH", "56"))
MIN_SCORE_BUY = int(os.getenv("MIN_SCORE_BUY", "72"))
MIN_NET_RR_NORMAL = float(os.getenv("MIN_NET_RR_NORMAL", "2.0"))
MIN_NET_RR_CAUTION = float(os.getenv("MIN_NET_RR_CAUTION", "2.5"))
MIN_NET_RR_RISKOFF = float(os.getenv("MIN_NET_RR_RISKOFF", "3.0"))
MIN_NET_RR_TP1 = float(os.getenv("MIN_NET_RR_TP1", "1.35"))
MAX_LIMIT_DISTANCE_PCT = float(os.getenv("MAX_LIMIT_DISTANCE_PCT", "3.0"))
MAX_LIMIT_DISTANCE_ATR = float(os.getenv("MAX_LIMIT_DISTANCE_ATR", "1.0"))
SCORE_MARGINAL_GAP = int(os.getenv("SCORE_MARGINAL_GAP", "2"))

ITALY_TV_MARKET = os.getenv("ITALY_TV_MARKET", "italy")
ITALY_YF_SUFFIX = os.getenv("ITALY_YF_SUFFIX", ".MI")
ITALY_TV_EXCHANGE = os.getenv("ITALY_TV_EXCHANGE", "MIL")
MARKET_TZ = ZoneInfo("Europe/Rome")
MARKET_OPEN = dt_time(9, 0)
MARKET_CLOSE = dt_time(17, 30)
ENFORCE_MARKET_SESSION = os.getenv("ENFORCE_MARKET_SESSION", "1") == "1"
FORCE_RUN_OUTSIDE_SESSION = os.getenv("FORCE_RUN_OUTSIDE_SESSION", "0") == "1"

# Chiusure Borsa Italiana 2026 pubblicate da Borsa Italiana.
# Per anni successivi aggiornare la lista o passarla da env MARKET_HOLIDAYS.
DEFAULT_MARKET_HOLIDAYS_2026 = {
    "2026-01-01", "2026-04-03", "2026-04-06",
    "2026-05-01", "2026-12-24", "2026-12-25", "2026-12-31",
}
MARKET_HOLIDAYS = {
    x.strip()
    for x in os.getenv("MARKET_HOLIDAYS", ",".join(sorted(DEFAULT_MARKET_HOLIDAYS_2026))).split(",")
    if x.strip()
}

# Portfolio/risk data opzionali.
# PORTFOLIO_POSITIONS_JSON esempio:
# [{"ticker":"CF","shares":21,"entry":114.23,"stop":109,"sector":"Basic Materials"}]
PORTFOLIO_POSITIONS_JSON = os.getenv("PORTFOLIO_POSITIONS_JSON", "").strip()

# Change engine
SCORE_CHANGE_MATERIAL = int(os.getenv("SCORE_CHANGE_MATERIAL", "5"))

# Dati / output
DATA_DIR = Path(os.getenv("SCREENER_DATA_DIR", "data"))
DB_PATH = DATA_DIR / "italy_trading_forward_test.db"
JSON_DIR = DATA_DIR / "italy_snapshots"

# Portafoglio opzionale da env: "MSFT,FNV,PYPL"
PORTFOLIO_TICKERS = [
    x.strip().upper()
    for x in os.getenv("PORTFOLIO_TICKERS", "").split(",")
    if x.strip()
]


# =============================================================================
# SCORE WEIGHTS (100)
# =============================================================================

WEIGHTS = {
    "valuation": 12,
    "business_quality": 13,
    "growth_quality": 10,
    "financial_strength": 10,
    "earnings_quality": 8,
    "catalyst_expectations": 12,
    "technical_setup": 12,
    "volume_rs": 7,
    "entry_rr": 10,
    "portfolio_fit": 6,
}
assert sum(WEIGHTS.values()) == 100


QUALITY_COMPONENT_KEYS = (
    "business_quality",
    "growth_quality",
    "financial_strength",
    "earnings_quality",
)

# L'Opportunity Score resta il punteggio operativo complessivo.
# Il Quality Score misura solo qualità/crescita/solidità/utili, senza timing.


# =============================================================================
# HELPERS
# =============================================================================


def _parse_recipients(raw: str) -> List[str]:
    """Destinatari separati da virgola o punto e virgola."""
    if not raw:
        return []
    return [x.strip() for x in re.split(r"[;,]", raw) if x.strip()]


def validate_mail_config() -> Tuple[bool, str]:
    missing = []
    if not GMAIL_SENDER:
        missing.append("GMAIL_SENDER")
    if not GMAIL_RECIPIENT:
        missing.append("GMAIL_RECIPIENT")
    if not GMAIL_PASSWORD:
        missing.append("GMAIL_PASSWORD")
    if missing:
        return False, "Secret/variabili mancanti: " + ", ".join(missing)
    return True, "OK"


def send_email(subject: str, body: str, is_html: bool = True) -> bool:
    """Invio autonomo via Gmail SMTP STARTTLS. Nessun PAT_TOKEN richiesto."""
    ok, note = validate_mail_config()
    if not ok:
        print(f"❌ Email non inviata: {note}")
        return False

    recipients = _parse_recipients(GMAIL_RECIPIENT)
    if not recipients:
        print("❌ Email non inviata: nessun destinatario valido")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = GMAIL_SENDER
        msg["To"] = ", ".join(recipients)
        msg.attach(MIMEText(body, "html" if is_html else "plain", "utf-8"))

        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=MAIL_TIMEOUT_SECONDS) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(GMAIL_SENDER, GMAIL_PASSWORD)
            server.sendmail(GMAIL_SENDER, recipients, msg.as_string())
        return True

    except smtplib.SMTPAuthenticationError:
        print("❌ Autenticazione Gmail fallita: verificare GMAIL_SENDER e GMAIL_PASSWORD/App Password.")
        return False
    except Exception as exc:
        print(f"❌ Errore invio email: {type(exc).__name__}: {exc}")
        return False



def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    try:
        v = float(value)
        if math.isfinite(v):
            return v
    except Exception:
        pass
    return default


def safe_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    v = safe_float(value)
    if v is None:
        return default
    try:
        return int(v)
    except Exception:
        return default


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def first_not_none(*values: Any) -> Any:
    for v in values:
        if v is not None:
            return v
    return None


def fmt_price(v: Optional[float]) -> str:
    return "N/D" if v is None else f"€{v:,.2f}"


def fmt_pct(v: Optional[float]) -> str:
    return "N/D" if v is None else f"{v:+.1f}%"


def fmt_num(v: Optional[float], digits: int = 2) -> str:
    if v is None:
        return "N/D"
    return f"{v:,.{digits}f}"


def html_escape(value: Any) -> str:
    s = "" if value is None else str(value)
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def extract_unknown_field(err: Exception) -> Optional[str]:
    s = str(err)
    patterns = [
        r'Unknown field\s+\\?"([^\"]+)\\?"',
        r"unknown field[:\s]+[\"']?([^\"'\s,}]+)",
    ]
    for p in patterns:
        m = re.search(p, s, flags=re.I)
        if m:
            return m.group(1)
    return None


def normalize_percent(v: Optional[float]) -> Optional[float]:
    """Converte 0.23 -> 23 se sembra percentuale in forma frazionaria."""
    if v is None:
        return None
    if -2.0 <= v <= 2.0:
        return v * 100.0
    return v


def normalize_debt_to_equity(v: Optional[float]) -> Optional[float]:
    """Yahoo spesso restituisce D/E come percentuale (es. 35 = 0.35)."""
    if v is None:
        return None
    if abs(v) > 5:
        return v / 100.0
    return v


def point_score_ratio(points: float, possible: float, weight: int) -> float:
    if possible <= 0:
        return 0.0
    return clamp(points / possible, 0.0, 1.0) * weight



def to_yfinance_ticker(ticker: str) -> str:
    """TradingView usa es. ENI, Yahoo Finance usa ENI.MI."""
    t = (ticker or "").strip().upper()
    if not t:
        return t
    if "." in t:
        return t
    return f"{t}{ITALY_YF_SUFFIX}"


def to_tv_symbol(ticker: str) -> str:
    t = (ticker or "").strip().upper().replace(ITALY_YF_SUFFIX.upper(), "")
    return f"{ITALY_TV_EXCHANGE}:{t}"


def is_financial_sector_value(sector: Optional[str]) -> bool:
    s = (sector or "").strip().lower()
    keys = ("finance", "financial", "finanza", "bank", "banca", "insurance", "assicur")
    return any(k in s for k in keys)


def italian_market_session_status(now: Optional[datetime] = None) -> Dict[str, Any]:
    now_local = now.astimezone(MARKET_TZ) if now else datetime.now(MARKET_TZ)
    d = now_local.date().isoformat()
    weekday_open = now_local.weekday() < 5
    holiday = d in MARKET_HOLIDAYS
    clock = now_local.time().replace(tzinfo=None)
    in_hours = MARKET_OPEN <= clock <= MARKET_CLOSE
    is_open = weekday_open and not holiday and in_hours
    return {
        "market_session_open": is_open,
        "market_local_time": now_local.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "market_holiday": holiday,
        "market_in_hours": in_hours,
    }


def score_band(score: float) -> str:
    if score >= 85:
        return "ECCELLENTE"
    if score >= 75:
        return "FORTE"
    if score >= 65:
        return "INTERESSANTE"
    if score >= 55:
        return "DEBOLE"
    return "SCARSO"


# =============================================================================
# TRADINGVIEW DISCOVERY LENSES
# =============================================================================

# Campi volutamente compatibili con la V4; quelli non disponibili vengono rimossi.
TV_FIELDS = [
    "name",
    "description",
    "close",
    "market_cap_basic",
    "volume",
    "sector",
    "exchange",
    # valuation
    "price_earnings_ttm",
    "price_earnings_forward_fy",
    "price_free_cash_flow_ttm",
    "enterprise_value_ebitda_ttm",
    # growth
    "earnings_per_share_diluted_yoy_growth_ttm",
    "total_revenue_yoy_growth_ttm",
    "free_cash_flow_yoy_growth_ttm",
    # quality
    "return_on_equity",
    "return_on_invested_capital",
    "operating_margin",
    "net_margin",
    # strength
    "current_ratio_fq",
    "debt_to_equity_fq",
    "net_debt_to_ebitda_fq",
    "interest_coverage_fy",
    "piotroski_f_score_fy",
    "altman_z_score_fy",
    # technical
    "RSI",
    "SMA50",
    "SMA200",
    "Perf.1M",
    "Perf.3M",
    "Perf.6M",
]


DISCOVERY_LENSES = {
    # Parametri calibrati sul mercato italiano: meno liquidità e capitalizzazioni
    # più basse rispetto agli USA, ma senza scendere in micro-cap illiquide.
    "QUALITY_ITALY": {
        "market_cap_min": 1_000_000_000,
        "pe_min": 3,
        "pe_max": 35,
        "eps_growth_min": -5,
        "revenue_growth_min": -5,
        "volume_min": 20_000,
    },
    "TACTICAL_VALUE_ITALY": {
        "market_cap_min": 200_000_000,
        "pe_min": 3,
        "pe_max": 45,
        "eps_growth_min": -15,
        "revenue_growth_min": -15,
        "volume_min": 8_000,
    },
    "MIDCAP_GARP_ITALY": {
        "market_cap_min": 300_000_000,
        "pe_min": 4,
        "pe_max": 40,
        "eps_growth_min": 0,
        "revenue_growth_min": -2,
        "volume_min": 8_000,
    },
}


def build_discovery_where(active_fields: set[str], lens: Dict[str, Any]) -> List[Any]:
    w: List[Any] = []

    def has(field: str) -> bool:
        return field in active_fields

    def ge(field: str, value: Optional[float]) -> None:
        if value is not None and has(field):
            w.append(Column(field) >= value)

    def gt(field: str, value: Optional[float]) -> None:
        if value is not None and has(field):
            w.append(Column(field) > value)

    def le(field: str, value: Optional[float]) -> None:
        if value is not None and has(field):
            w.append(Column(field) <= value)

    gt("close", MIN_PRICE)
    gt("market_cap_basic", lens.get("market_cap_min"))
    gt("volume", lens.get("volume_min"))
    ge("price_earnings_ttm", lens.get("pe_min"))
    le("price_earnings_ttm", lens.get("pe_max"))
    gt("earnings_per_share_diluted_yoy_growth_ttm", lens.get("eps_growth_min"))
    gt("total_revenue_yoy_growth_ttm", lens.get("revenue_growth_min"))
    return w


def run_single_tv_lens(lens_name: str, lens: Dict[str, Any]) -> Tuple[pd.DataFrame, List[str]]:
    active = set(TV_FIELDS)
    removed: List[str] = []

    for _ in range(25):
        try:
            q = (
                Query()
                .set_markets(ITALY_TV_MARKET)
                .select(*[f for f in TV_FIELDS if f in active])
                .where(*build_discovery_where(active, lens))
                .order_by("market_cap_basic", ascending=False)
                .limit(MAX_CANDIDATES_PER_LENS)
            )
            _, df = q.get_scanner_data()
            if df is None:
                df = pd.DataFrame()
            if not df.empty:
                df = df.copy()
                df["screen_source"] = lens_name
            return df, removed

        except Exception as e:
            unknown = extract_unknown_field(e)
            if unknown and unknown in active:
                active.remove(unknown)
                removed.append(unknown)
                print(f"⚠️ TradingView {lens_name}: campo non disponibile {unknown} -> rimosso")
                continue
            print(f"❌ TradingView {lens_name}: {e}")
            return pd.DataFrame(), removed

    return pd.DataFrame(), removed


def run_tradingview_discovery() -> Tuple[pd.DataFrame, List[str]]:
    frames: List[pd.DataFrame] = []
    removed_all: List[str] = []

    print("\n🔍 TradingView discovery")
    for name, lens in DISCOVERY_LENSES.items():
        df, removed = run_single_tv_lens(name, lens)
        print(f"  {name}: {len(df)} candidati")
        if not df.empty:
            frames.append(df)
        removed_all.extend(removed)

    if not frames:
        return pd.DataFrame(), sorted(set(removed_all))

    merged = pd.concat(frames, ignore_index=True)

    # Unione per ticker con indicazione delle lenti in cui compare.
    source_map = (
        merged.groupby("name")["screen_source"]
        .apply(lambda s: "+".join(sorted(set(map(str, s)))))
        .to_dict()
    )

    dedup = merged.drop_duplicates(subset=["name"], keep="first").copy()
    dedup["screen_source"] = dedup["name"].map(source_map)
    return dedup, sorted(set(removed_all))


# =============================================================================
# YFINANCE DATA / TECHNICALS
# =============================================================================

def compute_rsi(close: pd.Series, period: int = 14) -> Optional[float]:
    if len(close) < period + 2:
        return None
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return safe_float(rsi.iloc[-1])


def compute_atr(hist: pd.DataFrame, period: int = 14) -> Optional[float]:
    if hist is None or hist.empty or len(hist) < period + 2:
        return None
    high = hist["High"]
    low = hist["Low"]
    close = hist["Close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low).abs(), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    atr = tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    return safe_float(atr.iloc[-1])


def pct_return(series: pd.Series, periods: int) -> Optional[float]:
    if len(series) <= periods:
        return None
    base = safe_float(series.iloc[-periods - 1])
    last = safe_float(series.iloc[-1])
    if base in (None, 0) or last is None:
        return None
    return (last / base - 1) * 100


def extract_cashflow_line(df: pd.DataFrame, keywords: Sequence[str]) -> Optional[float]:
    if df is None or df.empty:
        return None
    for idx in df.index:
        label = str(idx).lower()
        if all(k.lower() in label for k in keywords):
            row = df.loc[idx]
            if isinstance(row, pd.Series):
                for v in row.tolist():
                    x = safe_float(v)
                    if x is not None:
                        return x
            else:
                return safe_float(row)
    return None



def resolve_next_earnings_date(
    stock: yf.Ticker,
    info: Dict[str, Any],
    now_utc: Optional[datetime] = None,
) -> Tuple[Optional[datetime], Optional[int]]:
    """
    Restituisce esclusivamente la prima data earnings FUTURA disponibile.
    Le date storiche vengono ignorate alla fonte: nessun days_to_earnings negativo.
    """
    now_utc = now_utc or datetime.now(timezone.utc)
    candidates: List[datetime] = []

    try:
        ed = stock.get_earnings_dates(limit=12)
        if ed is not None and not ed.empty:
            idx = pd.to_datetime(ed.index, utc=True, errors="coerce")
            for ts in idx:
                if pd.isna(ts):
                    continue
                dt = ts.to_pydatetime()
                if dt >= now_utc:
                    candidates.append(dt)
    except Exception:
        pass

    # Yahoo può fornire uno o più timestamp nell'info dict.
    for key in ("earningsTimestampStart", "earningsTimestamp", "earningsTimestampEnd"):
        raw_ts = safe_int(info.get(key))
        if not raw_ts:
            continue
        try:
            dt = datetime.fromtimestamp(raw_ts, tz=timezone.utc)
        except Exception:
            continue
        if dt >= now_utc:
            candidates.append(dt)

    if not candidates:
        return None, None

    earnings_date = min(candidates)
    seconds = max(0.0, (earnings_date - now_utc).total_seconds())
    days_to_earnings = int(math.floor(seconds / 86400.0))
    return earnings_date, days_to_earnings


def detect_corporate_action_inconsistency(
    hist_raw: pd.DataFrame,
    hist_adjusted: pd.DataFrame,
    atr_pct: Optional[float],
) -> Dict[str, Any]:
    """
    Diagnostica conservativa di possibili discontinuità/corporate action.

    - Le serie aggiustate restano la fonte per gli indicatori tecnici.
    - Uno split correttamente presente nei metadata NON è un'anomalia.
    - Si segnala POSSIBLE_CORPORATE_ACTION solo quando:
      a) raw e adjusted divergono materialmente senza metadata compatibili; oppure
      b) la serie adjusted mostra un salto recente eccezionale rispetto alla volatilità.

    Non corregge silenziosamente i dati e non inventa la causa.
    """
    result = {
        "possible_corporate_action": False,
        "corporate_action_status": "NONE",
        "corporate_action_reason": None,
        "recent_split_metadata": False,
        "max_raw_adjusted_return_gap_pct": None,
        "max_adjusted_jump_63d_pct": None,
    }

    if (
        hist_raw is None or hist_raw.empty
        or hist_adjusted is None or hist_adjusted.empty
        or "Close" not in hist_raw.columns
        or "Close" not in hist_adjusted.columns
    ):
        result["corporate_action_status"] = "N/D"
        return result

    try:
        raw_close = hist_raw["Close"].astype(float).dropna()
        adj_close = hist_adjusted["Close"].astype(float).dropna()
        common = raw_close.index.intersection(adj_close.index)
        if len(common) < 10:
            result["corporate_action_status"] = "N/D"
            return result

        raw_ret = raw_close.loc[common].pct_change()
        adj_ret = adj_close.loc[common].pct_change()
        gap = (raw_ret - adj_ret).abs()

        recent_gap = gap.tail(252).dropna()
        if not recent_gap.empty:
            max_gap = float(recent_gap.max())
            result["max_raw_adjusted_return_gap_pct"] = max_gap * 100.0
            gap_date = recent_gap.idxmax()
        else:
            max_gap = 0.0
            gap_date = None

        split_dates = []
        if "Stock Splits" in hist_raw.columns:
            split_series = hist_raw["Stock Splits"].fillna(0)
            split_dates = list(split_series[split_series != 0].index)
            result["recent_split_metadata"] = bool(split_dates[-10:])

        dividend_dates = []
        if "Dividends" in hist_raw.columns:
            div_series = hist_raw["Dividends"].fillna(0)
            dividend_dates = list(div_series[div_series != 0].index)

        def has_known_action_near(ts: Any, days: int = 3) -> bool:
            if ts is None:
                return False
            try:
                target = pd.Timestamp(ts)
                return any(
                    abs((pd.Timestamp(d) - target).days) <= days
                    for d in (split_dates + dividend_dates)
                )
            except Exception:
                return False

        # Divergenza >15% raw-vs-adjusted senza split/dividend noto vicino.
        if max_gap >= 0.15 and not has_known_action_near(gap_date):
            result.update({
                "possible_corporate_action": True,
                "corporate_action_status": "POSSIBLE_CORPORATE_ACTION",
                "corporate_action_reason": (
                    f"Raw/adjusted return gap {max_gap*100:.1f}% senza corporate action "
                    "coerente nei metadata"
                ),
            })
            return result

        # Salto recente sulla serie adjusted: deve essere eccezionale sia in assoluto
        # sia rispetto all'ATR corrente. Questo intercetta discontinuità sospette,
        # senza chiamarle automaticamente 'split'.
        recent_adj = adj_ret.tail(63).abs().dropna()
        if not recent_adj.empty:
            max_jump = float(recent_adj.max())
            result["max_adjusted_jump_63d_pct"] = max_jump * 100.0
            jump_date = recent_adj.idxmax()
            atr_threshold = 0.35
            if atr_pct is not None and atr_pct > 0:
                atr_threshold = max(0.35, 10.0 * atr_pct / 100.0)

            if max_jump >= atr_threshold and not has_known_action_near(jump_date):
                result.update({
                    "possible_corporate_action": True,
                    "corporate_action_status": "POSSIBLE_CORPORATE_ACTION",
                    "corporate_action_reason": (
                        f"Salto adjusted recente {max_jump*100:.1f}% > soglia "
                        f"{atr_threshold*100:.1f}%"
                    ),
                })
                return result

        if split_dates:
            result["corporate_action_status"] = "CORPORATE_ACTION_ADJUSTED_OK"
        else:
            result["corporate_action_status"] = "NONE"
        return result

    except Exception as exc:
        result["corporate_action_status"] = "N/D"
        result["corporate_action_reason"] = f"Corporate action check non disponibile: {exc}"
        return result

def get_yfinance_details(ticker: str, benchmark_hist: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    try:
        stock = yf.Ticker(ticker)
        info = stock.info or {}
        # Serie RAW per audit/corporate actions, serie ADJUSTED per indicatori tecnici.
        # Questo evita che split/dividendi distorcano SMA, ATR, RSI e Relative Strength.
        hist_raw = stock.history(period="2y", auto_adjust=False, actions=True)
        hist = stock.history(period="2y", auto_adjust=True, actions=True)
        if hist is None or hist.empty or len(hist) < 50:
            return {"data_error": "OHLCV insufficiente"}

        hist = hist.dropna(subset=["Close", "High", "Low"])
        if hist_raw is None:
            hist_raw = pd.DataFrame()
        close_s = hist["Close"]
        close = safe_float(close_s.iloc[-1])
        if close is None:
            return {"data_error": "Prezzo non disponibile"}

        ma20 = safe_float(close_s.rolling(20).mean().iloc[-1]) if len(hist) >= 20 else None
        ma50 = safe_float(close_s.rolling(50).mean().iloc[-1]) if len(hist) >= 50 else None
        ma200 = safe_float(close_s.rolling(200).mean().iloc[-1]) if len(hist) >= 200 else None

        sma50_prev = safe_float(close_s.rolling(50).mean().iloc[-21]) if len(hist) >= 71 else None
        sma200_prev = safe_float(close_s.rolling(200).mean().iloc[-21]) if len(hist) >= 221 else None
        slope50 = None if ma50 is None or sma50_prev in (None, 0) else (ma50 / sma50_prev - 1) * 100
        slope200 = None if ma200 is None or sma200_prev in (None, 0) else (ma200 / sma200_prev - 1) * 100

        low20 = safe_float(hist["Low"].tail(20).min())
        low63 = safe_float(hist["Low"].tail(63).min()) if len(hist) >= 63 else low20
        high20 = safe_float(hist["High"].tail(20).max())
        high63 = safe_float(hist["High"].tail(63).max()) if len(hist) >= 63 else high20
        low52 = safe_float(hist["Low"].tail(252).min()) if len(hist) >= 252 else safe_float(hist["Low"].min())
        high52 = safe_float(hist["High"].tail(252).max()) if len(hist) >= 252 else safe_float(hist["High"].max())

        atr = compute_atr(hist, 14)
        rsi = compute_rsi(close_s, 14)
        atr_pct = None if atr is None or close == 0 else atr / close * 100

        avg_vol20 = safe_float(hist["Volume"].tail(20).mean()) if "Volume" in hist.columns else None
        avg_vol50 = safe_float(hist["Volume"].tail(50).mean()) if "Volume" in hist.columns else None
        dollar_vol20 = None if avg_vol20 is None else avg_vol20 * close
        rel_volume = None
        if avg_vol20 not in (None, 0) and "Volume" in hist.columns:
            rel_volume = safe_float(hist["Volume"].iloc[-1]) / avg_vol20

        perf1m = pct_return(close_s, 21)
        perf3m = pct_return(close_s, 63)
        perf6m = pct_return(close_s, 126)

        rs_1m = rs_3m = rs_6m = None
        if benchmark_hist is not None and not benchmark_hist.empty and "Close" in benchmark_hist.columns:
            benchmark_close = benchmark_hist["Close"].dropna()
            benchmark1 = pct_return(benchmark_close, 21)
            benchmark3 = pct_return(benchmark_close, 63)
            benchmark6 = pct_return(benchmark_close, 126)
            rs_1m = None if perf1m is None or benchmark1 is None else perf1m - benchmark1
            rs_3m = None if perf3m is None or benchmark3 is None else perf3m - benchmark3
            rs_6m = None if perf6m is None or benchmark6 is None else perf6m - benchmark6

        # Fondamentali Yahoo
        market_cap = safe_float(info.get("marketCap"))
        forward_pe = safe_float(info.get("forwardPE"))
        peg = safe_float(info.get("pegRatio"))
        ev_ebitda = safe_float(info.get("enterpriseToEbitda"))
        current_ratio = safe_float(info.get("currentRatio"))
        quick_ratio = safe_float(info.get("quickRatio"))
        debt_to_equity = normalize_debt_to_equity(safe_float(info.get("debtToEquity")))
        roe = normalize_percent(safe_float(info.get("returnOnEquity")))
        roa = normalize_percent(safe_float(info.get("returnOnAssets")))
        gross_margin = normalize_percent(safe_float(info.get("grossMargins")))
        operating_margin = normalize_percent(safe_float(info.get("operatingMargins")))
        net_margin = normalize_percent(safe_float(info.get("profitMargins")))
        revenue_growth = normalize_percent(safe_float(info.get("revenueGrowth")))
        earnings_growth = normalize_percent(safe_float(info.get("earningsGrowth")))
        fcf = safe_float(info.get("freeCashflow"))
        ocf = safe_float(info.get("operatingCashflow"))
        total_debt = safe_float(info.get("totalDebt"))
        total_cash = safe_float(info.get("totalCash"))
        shares_out = safe_float(info.get("sharesOutstanding"))
        target_mean = safe_float(info.get("targetMeanPrice"))
        target_low = safe_float(info.get("targetLowPrice"))
        target_high = safe_float(info.get("targetHighPrice"))
        recommendation_mean = safe_float(info.get("recommendationMean"))
        beta = safe_float(info.get("beta"))
        short_percent = normalize_percent(safe_float(info.get("shortPercentOfFloat")))
        insider_pct = normalize_percent(safe_float(info.get("heldPercentInsiders")))
        inst_pct = normalize_percent(safe_float(info.get("heldPercentInstitutions")))

        p_fcf_yf = None
        if market_cap and fcf and fcf > 0:
            p_fcf_yf = market_cap / fcf

        fcf_yield = None
        if market_cap and fcf:
            fcf_yield = fcf / market_cap * 100

        net_debt = None
        if total_debt is not None and total_cash is not None:
            net_debt = total_debt - total_cash

        # SBC da cash flow quando disponibile
        sbc = None
        try:
            cf_df = stock.cash_flow
            sbc = extract_cashflow_line(cf_df, ["stock", "based", "compensation"])
            if sbc is None:
                sbc = extract_cashflow_line(cf_df, ["share", "based", "compensation"])
        except Exception:
            pass

        sbc_to_fcf = None
        if sbc is not None and fcf not in (None, 0):
            sbc_to_fcf = abs(sbc) / abs(fcf) * 100

        # Earnings sanitation: selezionare esclusivamente la prima data FUTURA.
        # Date storiche provenienti da Yahoo non devono generare giorni negativi.
        earnings_date, days_to_earnings = resolve_next_earnings_date(stock, info)

        # Corporate-action / price-discontinuity audit.
        corporate_diag = detect_corporate_action_inconsistency(hist_raw, hist, atr_pct)

        # Ultime candele per Trigger Engine. Nessuna pattern recognition "magica":
        # servono solo close/open/previous close e volume relativo.
        last_open = safe_float(hist["Open"].iloc[-1]) if "Open" in hist.columns else None
        last_high = safe_float(hist["High"].iloc[-1]) if "High" in hist.columns else None
        last_low = safe_float(hist["Low"].iloc[-1]) if "Low" in hist.columns else None
        prev_close = safe_float(close_s.iloc[-2]) if len(close_s) >= 2 else None
        last_volume = safe_float(hist["Volume"].iloc[-1]) if "Volume" in hist.columns else None

        return {
            "company_name": info.get("longName") or info.get("shortName") or ticker,
            "exchange_yf": info.get("exchange"),
            "currency": info.get("currency") or "EUR",
            "yf_price": close,
            "last_open": last_open,
            "last_high": last_high,
            "last_low": last_low,
            "prev_close": prev_close,
            "last_volume": last_volume,
            "market_cap_yf": market_cap,
            "ma20": ma20,
            "ma50": ma50,
            "ma200": ma200,
            "slope50_1m": slope50,
            "slope200_1m": slope200,
            "low20": low20,
            "low63": low63,
            "low52": low52,
            "high20": high20,
            "high63": high63,
            "high52": high52,
            "atr": atr,
            "atr_pct": atr_pct,
            "rsi_yf": rsi,
            "avg_volume20": avg_vol20,
            "avg_volume50": avg_vol50,
            "avg_dollar_volume20": dollar_vol20,
            "relative_volume": rel_volume,
            "perf1m_yf": perf1m,
            "perf3m_yf": perf3m,
            "perf6m_yf": perf6m,
            "rs_1m": rs_1m,
            "rs_3m": rs_3m,
            "rs_6m": rs_6m,
            "forward_pe_yf": forward_pe,
            "peg_yf": peg,
            "ev_ebitda_yf": ev_ebitda,
            "current_ratio_yf": current_ratio,
            "quick_ratio_yf": quick_ratio,
            "debt_to_equity_yf": debt_to_equity,
            "roe_yf": roe,
            "roa_yf": roa,
            "gross_margin_yf": gross_margin,
            "operating_margin_yf": operating_margin,
            "net_margin_yf": net_margin,
            "revenue_growth_yf": revenue_growth,
            "eps_growth_yf": earnings_growth,
            "free_cashflow": fcf,
            "operating_cashflow": ocf,
            "p_fcf_yf": p_fcf_yf,
            "fcf_yield": fcf_yield,
            "total_debt": total_debt,
            "total_cash": total_cash,
            "net_debt": net_debt,
            "shares_outstanding": shares_out,
            "stock_based_compensation": sbc,
            "sbc_to_fcf": sbc_to_fcf,
            "target_mean": target_mean,
            "target_low": target_low,
            "target_high": target_high,
            "recommendation_mean": recommendation_mean,
            "beta": beta,
            "short_percent_float": short_percent,
            "insider_ownership": insider_pct,
            "institutional_ownership": inst_pct,
            "earnings_date": earnings_date.isoformat() if earnings_date else None,
            "days_to_earnings": days_to_earnings,
            "possible_corporate_action": corporate_diag.get("possible_corporate_action", False),
            "corporate_action_status": corporate_diag.get("corporate_action_status"),
            "corporate_action_reason": corporate_diag.get("corporate_action_reason"),
            "recent_split_metadata": corporate_diag.get("recent_split_metadata", False),
            "max_raw_adjusted_return_gap_pct": corporate_diag.get("max_raw_adjusted_return_gap_pct"),
            "max_adjusted_jump_63d_pct": corporate_diag.get("max_adjusted_jump_63d_pct"),
        }

    except Exception as e:
        return {"data_error": str(e)}


# =============================================================================
# MARKET REGIME
# =============================================================================

def fetch_market_hist(ticker: str, period: str = "2y") -> pd.DataFrame:
    try:
        df = yf.Ticker(ticker).history(period=period, auto_adjust=False)
        return df if df is not None else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def market_regime_engine() -> Dict[str, Any]:
    # Benchmark Italia + contesto europeo. Fallback multipli per tollerare
    # eventuali differenze di simbolo Yahoo.
    def first_hist(symbols: Sequence[str]) -> Tuple[str, pd.DataFrame]:
        for s in symbols:
            df = fetch_market_hist(s)
            if df is not None and not df.empty:
                return s, df
        return symbols[0], pd.DataFrame()

    ftse_symbol, ftse = first_hist(("FTSEMIB.MI", "^FTSEMIB"))
    euro_symbol, euro = first_hist(("^STOXX50E", "EXSA.DE"))
    vol_symbol, vol = first_hist(("^V2TX", "^VIX"))

    def state(df: pd.DataFrame) -> Dict[str, Any]:
        if df.empty or len(df) < 200:
            return {"price": None, "sma50": None, "sma200": None, "trend": "N/D"}
        close = df["Close"].dropna()
        price = safe_float(close.iloc[-1])
        sma50 = safe_float(close.rolling(50).mean().iloc[-1])
        sma200 = safe_float(close.rolling(200).mean().iloc[-1])
        sma50_prev = safe_float(close.rolling(50).mean().iloc[-21]) if len(close) >= 71 else None
        slope50 = None if sma50 is None or sma50_prev in (None, 0) else (sma50 / sma50_prev - 1) * 100
        if price is None or sma50 is None or sma200 is None:
            trend = "N/D"
        elif price > sma50 > sma200 and (slope50 or 0) >= 0:
            trend = "BULL"
        elif price < sma50 < sma200:
            trend = "BEAR"
        else:
            trend = "MIXED"
        return {"price": price, "sma50": sma50, "sma200": sma200, "slope50": slope50, "trend": trend}

    ftse_s = state(ftse)
    euro_s = state(euro)
    vol_close = safe_float(vol["Close"].dropna().iloc[-1]) if not vol.empty else None

    points = 0
    if ftse_s["trend"] == "BULL":
        points += 2
    elif ftse_s["trend"] == "BEAR":
        points -= 2

    if euro_s["trend"] == "BULL":
        points += 1
    elif euro_s["trend"] == "BEAR":
        points -= 1

    # Se disponibile VSTOXX/Risk Vol: soglie volutamente non aggressive.
    if vol_close is not None:
        if vol_close < 20:
            points += 1
        elif vol_close > 35:
            points -= 2
        elif vol_close > 28:
            points -= 1

    if points >= 3:
        regime = "RISK-ON"
        rr_min = MIN_NET_RR_NORMAL
        new_buy_cap = 2
    elif points >= 1:
        regime = "NORMAL"
        rr_min = MIN_NET_RR_NORMAL
        new_buy_cap = 2
    elif points >= -1:
        regime = "CAUTION"
        rr_min = MIN_NET_RR_CAUTION
        new_buy_cap = 1
    else:
        regime = "RISK-OFF"
        rr_min = MIN_NET_RR_RISKOFF
        new_buy_cap = 1

    return {
        "regime": regime,
        "min_net_rr": rr_min,
        "max_new_buys": new_buy_cap,
        "ftsemib_symbol": ftse_symbol,
        "ftsemib": ftse_s,
        "europe_symbol": euro_symbol,
        "europe": euro_s,
        "risk_vol_symbol": vol_symbol,
        "vix": vol_close,  # alias retrocompatibile nel template
        "benchmark_name": "FTSE MIB",
    }


# =============================================================================
# TECHNICAL / VALUE TRAP / ENTRY / RISK
# =============================================================================

def classify_technical_state(c: Dict[str, Any]) -> str:
    price = c.get("price")
    ma20 = c.get("ma20")
    ma50 = c.get("ma50")
    ma200 = c.get("ma200")
    slope50 = c.get("slope50_1m")
    rsi = c.get("rsi")
    atr = c.get("atr")

    if price is None or ma50 is None or ma200 is None:
        return "N/D"

    if price < ma50 < ma200 and (slope50 or 0) < 0:
        return "SEVERE_DOWNTREND"

    if price > ma50 > ma200:
        # Extended se troppo lontano dalla SMA50 in unità ATR.
        if atr and atr > 0 and (price - ma50) / atr >= 3.0:
            return "EXTENDED"
        if rsi is not None and rsi >= 78:
            return "EXTENDED"
        return "STRONG_TREND"

    if price >= ma200 and ma50 is not None:
        if price <= ma50 * 1.02:
            return "HEALTHY_PULLBACK"
        if ma20 is not None and price >= ma20 and (slope50 or 0) >= -1:
            return "BASE_ACCUMULATION"
        return "REVERSAL_OR_BASE"

    if price < ma200 and ma50 >= ma200 and (slope50 or 0) >= 0:
        return "REVERSAL"

    return "WEAK"


def classify_rs(c: Dict[str, Any]) -> str:
    vals = [c.get("rs_1m"), c.get("rs_3m"), c.get("rs_6m")]
    vals = [v for v in vals if v is not None]
    if not vals:
        return "N/D"
    avg = sum(vals) / len(vals)
    if avg >= 5:
        return "STRONG"
    if avg >= -3:
        return "MEDIUM"
    return "WEAK"


def value_trap_engine(c: Dict[str, Any]) -> Dict[str, Any]:
    risk = 0
    reasons: List[str] = []

    rev = c.get("revenue_growth")
    eps = c.get("eps_growth")
    fcf = c.get("free_cashflow")
    fcfg = c.get("fcf_growth")
    de = c.get("debt_to_equity")
    nd = c.get("net_debt_ebitda")
    tech = c.get("technical_state")
    financial = is_financial_sector_value(c.get("sector"))

    if rev is not None and rev < -7:
        risk += 2
        reasons.append("ricavi in calo")
    if eps is not None and eps < -12:
        risk += 2
        reasons.append("EPS in forte calo")

    # FCF, D/E e Net Debt/EBITDA non sono confrontabili allo stesso modo
    # per banche/assicurazioni: non usarli come value-trap automatico.
    if not financial:
        if fcf is not None and fcf <= 0:
            risk += 2
            reasons.append("FCF non positivo")
        if fcfg is not None and fcfg < -20:
            risk += 1
            reasons.append("FCF deteriorato")
        if de is not None and de > 2.5:
            risk += 2
            reasons.append("leva elevata")
        if nd is not None and nd > 3.5:
            risk += 2
            reasons.append("Net Debt/EBITDA elevato")

    if tech == "SEVERE_DOWNTREND":
        risk += 1
        reasons.append("downtrend severo")

    if risk >= 6:
        label = "EXTREME"
    elif risk >= 4:
        label = "HIGH"
    elif risk >= 2:
        label = "MEDIUM"
    else:
        label = "LOW"

    return {
        "value_trap_risk": label,
        "value_trap_reasons": reasons,
        "value_trap_points": risk,
        "sector_adjusted": financial,
    }


def build_entry_plan(c: Dict[str, Any]) -> Dict[str, Any]:
    price = c.get("price")
    atr = c.get("atr")
    ma50 = c.get("ma50")
    ma200 = c.get("ma200")
    low20 = c.get("low20")
    low63 = c.get("low63")
    high20 = c.get("high20")
    high63 = c.get("high63")
    high52 = c.get("high52")
    target_mean = c.get("target_mean")
    tech = c.get("technical_state")

    if price is None:
        return {}

    supports = [x for x in [low20, ma50, ma200] if x is not None and 0 < x <= price * 1.02]
    support_ref = max(supports) if supports else price * 0.97

    if tech == "EXTENDED" and ma50 is not None:
        ideal = min(support_ref, ma50)
    elif tech in {"HEALTHY_PULLBACK", "BASE_ACCUMULATION", "REVERSAL"}:
        ideal = min(price, support_ref)
    else:
        ideal = support_ref

    if atr is None or atr <= 0:
        atr = max(price * 0.025, 0.01)

    buy_low = max(0.01, ideal - 0.35 * atr)
    buy_high = ideal + 0.35 * atr
    max_buy = ideal + 0.65 * atr

    structure_low = min([x for x in [low20, low63] if x is not None] or [ideal - 1.5 * atr])
    stop = min(structure_low - 0.25 * atr, ideal - 1.25 * atr)
    stop = max(0.01, stop)

    resistances = sorted([x for x in [high20, high63] if x is not None and x > ideal])
    tp1 = resistances[0] if resistances else ideal + 2.0 * atr

    tp2_candidates = [x for x in [high63, high52, target_mean] if x is not None and x > tp1]
    tp2 = min(tp2_candidates) if tp2_candidates else max(tp1 + 1.5 * atr, ideal + 3.0 * atr)

    current_in_buy_zone = buy_low <= price <= buy_high
    current_above_max_buy = price > max_buy

    distance_to_entry_pct = None if ideal <= 0 else (price / ideal - 1) * 100
    distance_to_max_buy_pct = None if max_buy <= 0 else (price / max_buy - 1) * 100
    distance_to_buy_zone_pct = 0.0
    if price > buy_high:
        distance_to_buy_zone_pct = (price / buy_high - 1) * 100
    elif price < buy_low:
        distance_to_buy_zone_pct = (price / buy_low - 1) * 100

    distance_to_max_buy_atr = None
    if current_above_max_buy and atr > 0:
        distance_to_max_buy_atr = (price - max_buy) / atr

    if current_in_buy_zone:
        trigger = "BUY ZONE raggiunta: attendere trigger confermato"
    elif current_above_max_buy:
        trigger = "NON INSEGUIRE: attendere pullback verso Max Buy/Buy Zone"
    else:
        trigger = "Attendere conferma price action"

    return {
        "ideal_entry": ideal,
        "buy_zone_low": buy_low,
        "buy_zone_high": buy_high,
        "max_buy": max_buy,
        "stop": stop,
        "tp1": tp1,
        "tp2": tp2,
        "trigger": trigger,
        "in_buy_zone": current_in_buy_zone,
        "above_max_buy": current_above_max_buy,
        "distance_to_entry_pct": distance_to_entry_pct,
        "distance_to_max_buy_pct": distance_to_max_buy_pct,
        "distance_to_buy_zone_pct": distance_to_buy_zone_pct,
        "distance_to_max_buy_atr": distance_to_max_buy_atr,
    }


def trigger_engine(c: Dict[str, Any]) -> Dict[str, Any]:
    """
    Trigger volutamente semplice e auditabile.
    CONFIRMED solo in Buy Zone e con reazione positiva:
      - close > open e close > previous close
      - volume relativo >= 0.80
    oppure:
      - close > SMA20 e volume relativo >= 1.00
    INVALID se la struttura è severamente deteriorata.
    In tutti gli altri casi WAITING.
    """
    if c.get("technical_state") == "SEVERE_DOWNTREND":
        return {"trigger_state": "INVALID", "trigger_reason": "Downtrend severo"}

    if not c.get("in_buy_zone"):
        return {"trigger_state": "WAITING", "trigger_reason": "Prezzo non ancora in Buy Zone"}

    price = c.get("price")
    last_open = c.get("last_open")
    prev_close = c.get("prev_close")
    ma20 = c.get("ma20")
    rel_vol = c.get("relative_volume")

    candle_positive = (
        price is not None
        and last_open is not None
        and prev_close is not None
        and price > last_open
        and price > prev_close
    )
    volume_ok = rel_vol is not None and rel_vol >= 0.80
    ma20_reclaim = price is not None and ma20 is not None and price > ma20
    volume_strong = rel_vol is not None and rel_vol >= 1.00

    if (candle_positive and volume_ok) or (ma20_reclaim and volume_strong):
        return {
            "trigger_state": "CONFIRMED",
            "trigger_reason": "Reazione positiva confermata da price action/volume",
        }

    return {
        "trigger_state": "WAITING",
        "trigger_reason": "Buy Zone raggiunta ma trigger price action/volume non confermato",
    }



def data_anomaly_engine(c: Dict[str, Any]) -> Dict[str, Any]:
    """
    Separa:
    - anomalie statistiche/fondamentali (EXTREME_GROWTH_METRICS, outlier);
    - possibili discontinuità/corporate action sui prezzi.

    Nessuna anomalia viene chiamata automaticamente "split".
    Un titolo che richiede review non può diventare BUY operativo finché non verificato.
    """
    flags: List[str] = []
    categories: List[str] = []
    extreme_growth_flags: List[str] = []

    peg = c.get("peg")
    roe = c.get("roe")
    roic = c.get("roic")
    epsg = c.get("eps_growth")
    fcfg = c.get("fcf_growth")
    netm = c.get("net_margin")

    if peg is not None and peg > 20:
        flags.append(f"PEG outlier ({peg:.2f})")
        categories.append("VALUATION_OUTLIER")
    if roe is not None and abs(roe) > 100:
        flags.append(f"ROE da verificare ({roe:.1f}%)")
        categories.append("QUALITY_OUTLIER")
    if roic is not None and abs(roic) > 100:
        flags.append(f"ROIC da verificare ({roic:.1f}%)")
        categories.append("QUALITY_OUTLIER")
    if epsg is not None and abs(epsg) > 300:
        msg = f"EPS growth estremo ({epsg:.1f}%)"
        flags.append(msg)
        extreme_growth_flags.append(msg)
    if fcfg is not None and abs(fcfg) > 500:
        msg = f"FCF growth estremo ({fcfg:.1f}%)"
        flags.append(msg)
        extreme_growth_flags.append(msg)
    if netm is not None and abs(netm) > 60:
        flags.append(f"Net margin one-off check ({netm:.1f}%)")
        categories.append("MARGIN_OUTLIER")

    extreme_growth = bool(extreme_growth_flags)
    if extreme_growth:
        categories.append("EXTREME_GROWTH_METRICS")

    possible_ca = bool(c.get("possible_corporate_action"))
    ca_reason = c.get("corporate_action_reason")
    if possible_ca:
        categories.append("POSSIBLE_CORPORATE_ACTION")
        flags.append(
            "Possibile corporate action/discontinuità prezzo"
            + (f": {ca_reason}" if ca_reason else "")
        )

    # Review richiesta per metriche estreme o corporate-action non verificata.
    # Il blocco è operativo, non un secondo malus arbitrario sullo score.
    data_review_required = extreme_growth or possible_ca

    return {
        "data_anomaly_flags": flags,
        "data_anomaly_categories": sorted(set(categories)),
        "extreme_growth_flags": extreme_growth_flags,
        "extreme_growth_metrics": extreme_growth,
        "has_data_anomalies": bool(flags),
        "possible_corporate_action": possible_ca,
        "data_review_required": data_review_required,
    }

def max_shares_by_cap(entry: float) -> int:
    if entry <= 0:
        return 0
    available = max(0.0, MAX_POSITION_SIZE - COMMISSION_PER_SIDE)
    return max(0, math.floor(available / entry))


def position_sizing(entry: Optional[float], stop: Optional[float]) -> Dict[str, Any]:
    if entry is None or stop is None or entry <= stop or entry <= 0:
        return {"shares": 0, "risk_sizing_configured": TRADING_CAPITAL > 0}

    cap_shares = max_shares_by_cap(entry)
    if cap_shares <= 0:
        return {"shares": 0, "risk_sizing_configured": TRADING_CAPITAL > 0}

    technical_risk_per_share = entry - stop

    # V5.1: nessuna size operativa fittizia se il capitale trading non è configurato.
    if TRADING_CAPITAL <= 0:
        return {
            "shares": 0,
            "invested": None,
            "buy_commission": COMMISSION_PER_SIDE,
            "round_trip_commission": ROUND_TRIP_COMMISSION,
            "cost_per_share": None,
            "technical_risk_per_share": technical_risk_per_share,
            "net_risk_total": None,
            "risk_budget": None,
            "risk_pct_trading_capital": None,
            "risk_sizing_configured": False,
            "sizing_warning": "Sizing non risk-based: TRADING_CAPITAL non configurato",
            # Solo per calcolare un R/R comparabile al netto dei costi.
            # NON è una quantità consigliata.
            "rr_reference_shares": cap_shares,
        }

    risk_budget = TRADING_CAPITAL * RISK_PCT_PER_TRADE
    budget_after_commission = max(0.0, risk_budget - ROUND_TRIP_COMMISSION)
    preliminary = math.floor(budget_after_commission / technical_risk_per_share) if technical_risk_per_share > 0 else 0
    shares = min(cap_shares, max(0, preliminary))

    while shares > 0:
        net_risk = shares * technical_risk_per_share + ROUND_TRIP_COMMISSION
        if net_risk <= risk_budget + 1e-9:
            break
        shares -= 1

    if shares <= 0:
        return {
            "shares": 0,
            "risk_budget": risk_budget,
            "risk_sizing_configured": True,
            "sizing_warning": "Nessuna quantità compatibile con il Risk Budget",
            "rr_reference_shares": cap_shares,
        }

    invested = shares * entry
    net_risk = shares * technical_risk_per_share + ROUND_TRIP_COMMISSION
    cost_per_share = ROUND_TRIP_COMMISSION / shares
    risk_pct_capital = net_risk / TRADING_CAPITAL * 100 if TRADING_CAPITAL > 0 else None

    return {
        "shares": shares,
        "invested": invested,
        "buy_commission": COMMISSION_PER_SIDE,
        "round_trip_commission": ROUND_TRIP_COMMISSION,
        "cost_per_share": cost_per_share,
        "technical_risk_per_share": technical_risk_per_share,
        "net_risk_total": net_risk,
        "risk_budget": risk_budget,
        "risk_pct_trading_capital": risk_pct_capital,
        "risk_sizing_configured": True,
        "sizing_warning": None,
        "rr_reference_shares": shares,
    }


def compute_gross_rr(
    entry: Optional[float],
    stop: Optional[float],
    tp: Optional[float],
) -> Optional[float]:
    """
    R/R puramente strutturale, indipendente da size e commissioni.
    Serve a distinguere la geometria del setup dal drag dei costi Fineco.
    """
    if None in (entry, stop, tp):
        return None
    assert entry is not None and stop is not None and tp is not None
    if entry <= stop or tp <= entry:
        return None
    risk = entry - stop
    reward = tp - entry
    if risk <= 0 or reward <= 0:
        return None
    return reward / risk


def compute_net_rr(entry: Optional[float], stop: Optional[float], tp: Optional[float], shares: int) -> Optional[float]:
    if None in (entry, stop, tp) or shares <= 0:
        return None
    assert entry is not None and stop is not None and tp is not None
    if entry <= stop or tp <= entry:
        return None
    cost_per_share = ROUND_TRIP_COMMISSION / shares
    risk = (entry - stop) + cost_per_share
    reward = (tp - entry) - cost_per_share
    if risk <= 0 or reward <= 0:
        return None
    return reward / risk


# =============================================================================
# PORTFOLIO FIT
# =============================================================================

def parse_portfolio_positions() -> List[Dict[str, Any]]:
    if not PORTFOLIO_POSITIONS_JSON:
        return []
    try:
        raw = json.loads(PORTFOLIO_POSITIONS_JSON)
        if not isinstance(raw, list):
            return []
        return [x for x in raw if isinstance(x, dict)]
    except Exception:
        return []


def get_portfolio_sectors() -> Dict[str, int]:
    counts: Dict[str, int] = {}

    positions = parse_portfolio_positions()
    if positions:
        for p in positions:
            sector = p.get("sector")
            ticker = str(p.get("ticker") or "").upper()
            if not sector and ticker:
                try:
                    sector = (yf.Ticker(to_yfinance_ticker(ticker)).info or {}).get("sector")
                except Exception:
                    sector = None
            sector = sector or "Unknown"
            counts[sector] = counts.get(sector, 0) + 1
        return counts

    for ticker in PORTFOLIO_TICKERS:
        try:
            info = yf.Ticker(to_yfinance_ticker(ticker)).info or {}
            sector = info.get("sector") or "Unknown"
        except Exception:
            sector = "Unknown"
        counts[sector] = counts.get(sector, 0) + 1
    return counts


def portfolio_fit_score(candidate_sector: str, portfolio_sectors: Dict[str, int]) -> Tuple[Optional[float], str]:
    if not portfolio_sectors:
        return None, "N/D - portafoglio non configurato"
    total = sum(portfolio_sectors.values())
    same = portfolio_sectors.get(candidate_sector, 0)
    projected = (same + 1) / (total + 1)
    if projected > MAX_SECTOR_EXPOSURE:
        return 0.25, f"Concentrazione settore elevata ({projected:.0%})"
    if projected > MAX_SECTOR_EXPOSURE * 0.8:
        return 0.60, f"Concentrazione settore moderata ({projected:.0%})"
    return 1.0, "Diversificazione accettabile"


def portfolio_heat_engine() -> Dict[str, Any]:
    """
    Heat = somma perdita teorica agli stop / capitale trading.
    Calcolabile solo se TRADING_CAPITAL e posizioni con shares/current-or-entry/stop sono disponibili.
    """
    positions = parse_portfolio_positions()
    if TRADING_CAPITAL <= 0 or not positions:
        return {
            "portfolio_heat": None,
            "portfolio_heat_pct": None,
            "portfolio_heat_status": "N/D",
            "portfolio_heat_note": "Capitale trading o posizioni con stop non configurati",
        }

    total_risk = 0.0
    valid = 0
    for p in positions:
        shares = safe_float(p.get("shares"))
        basis = first_not_none(safe_float(p.get("current_price")), safe_float(p.get("entry")))
        stop = safe_float(p.get("stop"))
        if shares is None or basis is None or stop is None or shares <= 0 or basis <= stop:
            continue
        total_risk += shares * (basis - stop)
        valid += 1

    if valid == 0:
        return {
            "portfolio_heat": None,
            "portfolio_heat_pct": None,
            "portfolio_heat_status": "N/D",
            "portfolio_heat_note": "Nessuna posizione con stop valido",
        }

    heat = total_risk / TRADING_CAPITAL
    status = "OK" if heat <= MAX_PORTFOLIO_HEAT else "HIGH"
    return {
        "portfolio_heat": heat,
        "portfolio_heat_pct": heat * 100,
        "portfolio_heat_status": status,
        "portfolio_heat_note": f"{valid} posizioni incluse",
    }


# =============================================================================
# SCORING
# =============================================================================

COMPONENT_MAX_POSSIBLE = {
    "valuation": 12.0,
    "business_quality": 10.0,
    "growth_quality": 6.0,
    "financial_strength": 9.0,
    "earnings_quality": 6.0,
    "catalyst_expectations": 7.0,
    "volume_rs": 5.0,
}


def coverage_cap(score_value: float, coverage: float, weight: int) -> float:
    """Impedisce a una componente con pochi dati di prendere punteggio pieno."""
    coverage = clamp(coverage, 0.0, 1.0)
    if coverage < 0.50:
        max_ratio = 0.60
    elif coverage < 0.75:
        max_ratio = 0.80
    else:
        max_ratio = 1.00
    return min(score_value, weight * max_ratio)


def score_valuation(c: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    points = 0.0
    possible = 0.0
    pe = c.get("pe")
    fpe = c.get("forward_pe")
    peg = c.get("peg")
    pfcf = c.get("p_fcf")
    ev = c.get("ev_ebitda")
    fcfy = c.get("fcf_yield")
    financial = is_financial_sector_value(c.get("sector"))

    if pe is not None:
        possible += 3
        points += 3 if 4 <= pe <= 14 else 2 if pe <= 20 else 1 if pe <= 28 else 0
    if fpe is not None:
        possible += 2
        points += 2 if 4 <= fpe <= 14 else 1 if fpe <= 20 else 0
    if peg is not None and peg > 0:
        possible += 1 if financial else 2
        points += (1 if peg <= 1.5 else 0.5 if peg <= 2.0 else 0) if financial else (2 if peg <= 1 else 1 if peg <= 1.5 else 0)

    # Per banche e assicurazioni P/FCF ed EV/EBITDA sono spesso poco significativi.
    if not financial:
        if pfcf is not None and pfcf > 0:
            possible += 2
            points += 2 if pfcf <= 14 else 1 if pfcf <= 20 else 0
        if ev is not None and ev > 0:
            possible += 2
            points += 2 if ev <= 10 else 1 if ev <= 15 else 0
        if fcfy is not None:
            possible += 1
            points += 1 if fcfy >= 4 else 0.5 if fcfy >= 2 else 0

    return point_score_ratio(points, possible, WEIGHTS["valuation"]), {
        "raw": points,
        "possible": possible,
        "max_possible": 6.0 if financial else 12.0,
        "sector_adjusted": financial,
    }


def score_business_quality(c: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    points = 0.0
    possible = 0.0
    roe = c.get("roe")
    roic = c.get("roic")
    opm = c.get("operating_margin")
    netm = c.get("net_margin")
    fscore = c.get("f_score")

    if roe is not None:
        possible += 2
        points += 2 if roe >= 20 else 1.5 if roe >= 15 else 1 if roe >= 10 else 0
    if roic is not None:
        possible += 3
        points += 3 if roic >= 20 else 2 if roic >= 15 else 1 if roic >= 10 else 0
    if opm is not None:
        possible += 2
        points += 2 if opm >= 20 else 1 if opm >= 10 else 0
    if netm is not None:
        possible += 1
        points += 1 if netm >= 10 else 0.5 if netm >= 5 else 0
    if fscore is not None:
        possible += 2
        points += 2 if fscore >= 8 else 1 if fscore >= 6 else 0

    return point_score_ratio(points, possible, WEIGHTS["business_quality"]), {"raw": points, "possible": possible}


def score_growth_quality(c: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    points = 0.0
    possible = 0.0
    for key in ("revenue_growth", "eps_growth", "fcf_growth"):
        v = c.get(key)
        if v is not None:
            possible += 2
            # Non premiare linearmente crescite astronomiche: saturazione a 20%.
            points += 2 if v >= 15 else 1.5 if v >= 8 else 1 if v >= 3 else 0 if v >= -5 else -0.5
    points = max(0.0, points)
    return point_score_ratio(points, possible, WEIGHTS["growth_quality"]), {"raw": points, "possible": possible}


def score_financial_strength(c: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    points = 0.0
    possible = 0.0
    financial = is_financial_sector_value(c.get("sector"))

    if financial:
        roe = c.get("roe")
        roa = c.get("roa")
        fscore = c.get("f_score")
        if roe is not None:
            possible += 3
            points += 3 if roe >= 15 else 2 if roe >= 10 else 1 if roe >= 7 else 0
        if roa is not None:
            possible += 2
            points += 2 if roa >= 1.2 else 1 if roa >= 0.7 else 0
        if fscore is not None:
            possible += 2
            points += 2 if fscore >= 7 else 1 if fscore >= 5 else 0
        return point_score_ratio(points, possible, WEIGHTS["financial_strength"]), {
            "raw": points, "possible": possible, "max_possible": 7.0, "sector_adjusted": True
        }

    cr = c.get("current_ratio")
    de = c.get("debt_to_equity")
    nd = c.get("net_debt_ebitda")
    ic = c.get("interest_coverage")
    alt = c.get("altman_z")

    if cr is not None:
        possible += 2
        points += 2 if cr >= 1.4 else 1 if cr >= 1.0 else 0
    if de is not None:
        possible += 2
        points += 2 if de < 0.7 else 1.5 if de < 1.2 else 0.5 if de < 2.5 else 0
    if nd is not None:
        possible += 2
        points += 2 if nd < 1.5 else 1.5 if nd < 2.5 else 0.5 if nd < 3.5 else 0
    if ic is not None:
        possible += 2
        points += 2 if ic >= 6 else 1.5 if ic >= 3 else 0.5 if ic >= 1.8 else 0
    if alt is not None:
        possible += 1
        points += 1 if alt >= 3 else 0.5 if alt >= 1.8 else 0

    return point_score_ratio(points, possible, WEIGHTS["financial_strength"]), {
        "raw": points, "possible": possible, "max_possible": 9.0, "sector_adjusted": False
    }


def score_earnings_quality(c: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    points = 0.0
    possible = 0.0
    financial = is_financial_sector_value(c.get("sector"))

    if financial:
        epsg = c.get("eps_growth")
        revg = c.get("revenue_growth")
        fscore = c.get("f_score")
        if epsg is not None:
            possible += 2
            points += 2 if epsg >= 8 else 1 if epsg >= 0 else 0
        if revg is not None:
            possible += 2
            points += 2 if revg >= 5 else 1 if revg >= 0 else 0
        if fscore is not None:
            possible += 2
            points += 2 if fscore >= 7 else 1 if fscore >= 5 else 0
        return point_score_ratio(points, possible, WEIGHTS["earnings_quality"]), {
            "raw": points, "possible": possible, "max_possible": 6.0, "sector_adjusted": True
        }

    ocf = c.get("operating_cashflow")
    fcf = c.get("free_cashflow")
    sbc_ratio = c.get("sbc_to_fcf")

    if ocf is not None:
        possible += 2
        points += 2 if ocf > 0 else 0
    if fcf is not None:
        possible += 2
        points += 2 if fcf > 0 else 0
    if sbc_ratio is not None:
        possible += 2
        points += 2 if sbc_ratio <= 15 else 1 if sbc_ratio <= 35 else 0

    return point_score_ratio(points, possible, WEIGHTS["earnings_quality"]), {
        "raw": points, "possible": possible, "max_possible": 6.0, "sector_adjusted": False
    }


def score_catalyst_expectations(c: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    """
    Proxy quantitativo, non un vero catalyst engine qualitativo.
    Usa crescita, forward PE vs trailing PE, upside consenso e recommendationMean.
    L'email lo dichiara esplicitamente come proxy.
    """
    points = 0.0
    possible = 0.0

    pe = c.get("pe")
    fpe = c.get("forward_pe")
    target = c.get("target_mean")
    price = c.get("price")
    rec = c.get("recommendation_mean")
    revg = c.get("revenue_growth")
    epsg = c.get("eps_growth")

    if pe and fpe and pe > 0:
        possible += 2
        compression = (pe - fpe) / pe * 100
        points += 2 if compression >= 15 else 1 if compression >= 5 else 0

    if target and price and target > price:
        possible += 2
        upside = (target / price - 1) * 100
        points += 2 if upside >= 20 else 1 if upside >= 10 else 0.5 if upside >= 5 else 0

    if rec is not None:
        possible += 1
        # Yahoo: tipicamente 1 strong buy, 2 buy, 3 hold, 4 sell, 5 strong sell.
        points += 1 if rec <= 2.0 else 0.5 if rec <= 2.7 else 0

    if revg is not None:
        possible += 1
        points += 1 if revg >= 8 else 0.5 if revg >= 3 else 0
    if epsg is not None:
        possible += 1
        points += 1 if epsg >= 8 else 0.5 if epsg >= 3 else 0

    return point_score_ratio(points, possible, WEIGHTS["catalyst_expectations"]), {"raw": points, "possible": possible, "proxy": True}


def score_technical(c: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    state = c.get("technical_state")
    mapping = {
        "STRONG_TREND": 1.0,
        "HEALTHY_PULLBACK": 1.0,
        "BASE_ACCUMULATION": 0.85,
        "REVERSAL": 0.75,
        "REVERSAL_OR_BASE": 0.65,
        "EXTENDED": 0.45,
        "WEAK": 0.30,
        "SEVERE_DOWNTREND": 0.0,
        "N/D": 0.0,
    }
    ratio = mapping.get(state, 0.0)
    return ratio * WEIGHTS["technical_setup"], {"state": state, "ratio": ratio}


def score_volume_rs(c: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    points = 0.0
    possible = 0.0
    rs = c.get("rs_state")
    rv = c.get("relative_volume")
    adv = c.get("avg_dollar_volume20")

    if rs != "N/D":
        possible += 3
        points += 3 if rs == "STRONG" else 2 if rs == "MEDIUM" else 0.5
    if rv is not None:
        possible += 1
        points += 1 if 0.7 <= rv <= 2.5 else 0.5
    if adv is not None:
        possible += 1
        points += 1 if adv >= MIN_AVG_DOLLAR_VOLUME else 0.5 if adv >= MIN_AVG_DOLLAR_VOLUME_SOFT else 0

    return point_score_ratio(points, possible, WEIGHTS["volume_rs"]), {"raw": points, "possible": possible}


def score_entry_rr(c: Dict[str, Any], rr_min: float) -> Tuple[float, Dict[str, Any]]:
    rr1 = c.get("net_rr_tp1")
    rr2 = c.get("net_rr_tp2")
    above = c.get("above_max_buy")
    in_zone = c.get("in_buy_zone")

    if rr1 is None and rr2 is None:
        return 0.0, {"rr1": None, "rr2": None, "possible": 0.0}

    # TP1 è il target operativo primario, TP2 è esteso.
    primary_ratio = 0.0
    if rr1 is not None:
        primary_ratio = 1.0 if rr1 >= 2.0 else 0.8 if rr1 >= MIN_NET_RR_TP1 else 0.4 if rr1 >= 1.0 else 0.0

    extended_ratio = 0.0
    if rr2 is not None:
        extended_ratio = 1.0 if rr2 >= max(3.0, rr_min) else 0.8 if rr2 >= rr_min else 0.4 if rr2 >= 1.5 else 0.0

    rr_ratio = 0.60 * primary_ratio + 0.40 * extended_ratio

    if above:
        rr_ratio *= 0.45
    elif in_zone:
        rr_ratio *= 1.0
    else:
        rr_ratio *= 0.75

    return rr_ratio * WEIGHTS["entry_rr"], {
        "rr1": rr1,
        "rr2": rr2,
        "ratio": rr_ratio,
        "possible": 1.0,
    }


def calculate_total_score(c: Dict[str, Any], rr_min: float, portfolio_sectors: Dict[str, int]) -> Dict[str, Any]:
    components: Dict[str, Optional[float]] = {}
    meta: Dict[str, Any] = {}
    coverage_map: Dict[str, float] = {}

    for name, fn in [
        ("valuation", score_valuation),
        ("business_quality", score_business_quality),
        ("growth_quality", score_growth_quality),
        ("financial_strength", score_financial_strength),
        ("earnings_quality", score_earnings_quality),
        ("catalyst_expectations", score_catalyst_expectations),
        ("technical_setup", score_technical),
        ("volume_rs", score_volume_rs),
    ]:
        val, detail = fn(c)

        if name in COMPONENT_MAX_POSSIBLE:
            possible = safe_float(detail.get("possible"), 0.0) or 0.0
            max_possible = safe_float(detail.get("max_possible"), COMPONENT_MAX_POSSIBLE[name]) or COMPONENT_MAX_POSSIBLE[name]
            coverage = possible / max_possible
        elif name == "technical_setup":
            coverage = 0.0 if c.get("technical_state") == "N/D" else 1.0
        else:
            coverage = 1.0

        coverage = clamp(coverage, 0.0, 1.0)
        val = coverage_cap(val, coverage, WEIGHTS[name])
        components[name] = val
        detail["coverage"] = coverage
        meta[name] = detail
        coverage_map[name] = coverage

    entry_val, entry_meta = score_entry_rr(c, rr_min)
    entry_coverage = 1.0 if (c.get("net_rr_tp1") is not None or c.get("net_rr_tp2") is not None) else 0.0
    entry_val = coverage_cap(entry_val, entry_coverage, WEIGHTS["entry_rr"])
    entry_meta["coverage"] = entry_coverage
    components["entry_rr"] = entry_val
    meta["entry_rr"] = entry_meta
    coverage_map["entry_rr"] = entry_coverage

    pf_ratio, pf_note = portfolio_fit_score(c.get("sector") or "Unknown", portfolio_sectors)
    if pf_ratio is None:
        components["portfolio_fit"] = None
        coverage_map["portfolio_fit"] = 0.0
        meta["portfolio_fit"] = {"ratio": None, "note": pf_note, "coverage": 0.0}
    else:
        components["portfolio_fit"] = pf_ratio * WEIGHTS["portfolio_fit"]
        coverage_map["portfolio_fit"] = 1.0
        meta["portfolio_fit"] = {"ratio": pf_ratio, "note": pf_note, "coverage": 1.0}

    # Score normalizzato sui pesi realmente disponibili.
    raw_sum = sum(v for v in components.values() if v is not None)
    available_weight = sum(
        WEIGHTS[k] for k, v in components.items() if v is not None
    )
    base = 0.0 if available_weight <= 0 else raw_sum / available_weight * 100.0

    penalties: List[Dict[str, Any]] = []
    value_trap = c.get("value_trap_risk")
    if value_trap == "MEDIUM":
        penalties.append({"name": "Value trap MEDIUM", "points": -4})
    elif value_trap == "HIGH":
        penalties.append({"name": "Value trap HIGH", "points": -10})
    elif value_trap == "EXTREME":
        penalties.append({"name": "Value trap EXTREME", "points": -20})

    if c.get("technical_state") == "EXTENDED":
        penalties.append({"name": "Prezzo esteso", "points": -6})
    if c.get("technical_state") == "SEVERE_DOWNTREND":
        penalties.append({"name": "Downtrend severo", "points": -12})

    dte = c.get("days_to_earnings")
    if dte is not None:
        if 0 <= dte < 7:
            penalties.append({"name": "Earnings <7 giorni", "points": -12})
        elif 7 <= dte <= 14:
            penalties.append({"name": "Earnings 7-14 giorni", "points": -5})

    adv = c.get("avg_dollar_volume20")
    if adv is not None and adv < MIN_AVG_DOLLAR_VOLUME:
        penalties.append({"name": "Liquidità sotto target", "points": -4})

    if c.get("has_data_anomalies"):
        penalties.append({"name": "Dati anomali da verificare", "points": -3})

    total_penalty = sum(p["points"] for p in penalties)
    total = int(round(clamp(base + total_penalty, 0, 100)))

    # Coverage totale pesata (portfolio N/D non viene contato come dato disponibile).
    covered_weight = sum(WEIGHTS[k] * coverage_map.get(k, 0.0) for k in WEIGHTS)
    data_coverage_pct = covered_weight / sum(WEIGHTS.values()) * 100.0

    # Quality Score separato: qualità business, crescita, solidità e qualità utili.
    quality_raw = sum(
        components.get(k) or 0.0
        for k in QUALITY_COMPONENT_KEYS
    )
    quality_weight = sum(
        WEIGHTS[k]
        for k in QUALITY_COMPONENT_KEYS
        if components.get(k) is not None
    )
    quality_score = (
        0
        if quality_weight <= 0
        else int(round(clamp(quality_raw / quality_weight * 100.0, 0, 100)))
    )

    # Opportunity Score = score operativo complessivo già depurato da penalità.
    opportunity_score = total

    return {
        "score": opportunity_score,  # alias retrocompatibile
        "quality_score": quality_score,
        "opportunity_score": opportunity_score,
        "score_base": round(base, 1),
        "score_components": {
            k: (None if v is None else round(v, 1))
            for k, v in components.items()
        },
        "score_meta": meta,
        "component_coverage": {k: round(v * 100, 1) for k, v in coverage_map.items()},
        "data_coverage_pct": round(data_coverage_pct, 1),
        "penalties": penalties,
        "penalty_total": total_penalty,
    }


# =============================================================================
# DECISION ENGINE
# =============================================================================

def decision_engine(c: Dict[str, Any], regime: Dict[str, Any]) -> Dict[str, Any]:
    score = c.get("opportunity_score") or c.get("score") or 0
    rr1 = c.get("net_rr_tp1")
    rr2 = c.get("net_rr_tp2")
    rr_min = regime["min_net_rr"]
    trap = c.get("value_trap_risk")
    tech = c.get("technical_state")
    dte = c.get("days_to_earnings")
    data_quality = c.get("data_quality")
    trigger_state = c.get("trigger_state")
    rs_state = c.get("rs_state")

    hard_veto: List[str] = []
    warnings_list: List[str] = []

    if data_quality == "POOR":
        hard_veto.append("Data quality insufficiente")
    if c.get("data_review_required"):
        cats = ", ".join(c.get("data_anomaly_categories") or [])
        hard_veto.append(
            "Data review richiesta"
            + (f" ({cats})" if cats else "")
        )
    if trap == "EXTREME":
        hard_veto.append("Value trap risk EXTREME")
    if tech == "SEVERE_DOWNTREND":
        hard_veto.append("Downtrend severo")
    if dte is not None and 0 <= dte < 7:
        hard_veto.append(f"Earnings entro 7 giorni ({dte}g)")
    if regime["regime"] == "RISK-OFF":
        hard_veto.append("Market regime RISK-OFF")
    if trigger_state == "INVALID":
        hard_veto.append("Trigger tecnico INVALID")

    if rs_state == "WEAK":
        warnings_list.append("Forza relativa vs FTSE MIB debole")
    if c.get("has_data_anomalies"):
        warnings_list.append("Metriche anomale da verificare")
    if c.get("possible_corporate_action"):
        warnings_list.append("Possibile corporate action/discontinuità prezzo: verifica manuale")
    if not c.get("risk_sizing_configured"):
        warnings_list.append("Sizing non risk-based: TRADING_CAPITAL non configurato")

    if hard_veto:
        if "Data quality insufficiente" in hard_veto:
            decision = "DATA_INSUFFICIENT"
        elif trap == "EXTREME" or tech == "SEVERE_DOWNTREND":
            decision = "AVOID"
        else:
            decision = "WAIT"
        return {"decision": decision, "veto_reasons": hard_veto, "warnings": warnings_list}

    if score < MIN_SCORE_WATCH:
        return {
            "decision": "AVOID",
            "veto_reasons": [f"Score insufficiente ({score}<{MIN_SCORE_WATCH})"],
            "warnings": warnings_list,
        }

    # Senza sizing risk-based nessun segnale viene presentato come BUY operativo.
    sizing_ready = bool(c.get("risk_sizing_configured")) and (c.get("shares") or 0) > 0

    rr2_ok = rr2 is not None and rr2 >= rr_min
    rr1_ok = rr1 is not None and rr1 >= MIN_NET_RR_TP1
    score_ok = score >= MIN_SCORE_BUY

    failed: List[str] = []
    if not score_ok:
        failed.append(f"Score insufficiente ({score}<{MIN_SCORE_BUY})")
    if not rr2_ok:
        failed.append(f"R/R TP2 insufficiente ({fmt_num(rr2,2)}<{rr_min:.2f})")
    if not rr1_ok:
        failed.append(f"R/R TP1 insufficiente ({fmt_num(rr1,2)}<{MIN_NET_RR_TP1:.2f})")
    if not sizing_ready:
        failed.append("Risk sizing non configurato/compatibile")

    # Prezzo sopra Max Buy: LIMIT soltanto se davvero vicino.
    if c.get("above_max_buy"):
        dist_pct = c.get("distance_to_max_buy_pct")
        dist_atr = c.get("distance_to_max_buy_atr")
        close_enough = (
            (dist_pct is not None and dist_pct <= MAX_LIMIT_DISTANCE_PCT)
            or (dist_atr is not None and dist_atr <= MAX_LIMIT_DISTANCE_ATR)
        )
        if score_ok and rr2_ok and rr1_ok and sizing_ready and close_enough:
            return {
                "decision": "BUY_LIMIT",
                "veto_reasons": [f"LIMIT vicino al Max Buy ({fmt_pct(dist_pct)})"],
                "warnings": warnings_list,
            }
        reason = f"NON INSEGUIRE: prezzo sopra Max Buy di {fmt_pct(dist_pct)}"
        return {"decision": "WATCH", "veto_reasons": [reason] + failed, "warnings": warnings_list}

    # BUY NOW richiede trigger confermato, oltre a score/RR/sizing.
    if c.get("in_buy_zone"):
        if score_ok and rr2_ok and rr1_ok and sizing_ready and trigger_state == "CONFIRMED":
            return {"decision": "BUY_NOW", "veto_reasons": [], "warnings": warnings_list}

        reasons = []
        if trigger_state != "CONFIRMED":
            reasons.append(f"Trigger non confermato ({trigger_state or 'N/D'})")
        reasons.extend(failed)
        return {"decision": "WAIT", "veto_reasons": reasons, "warnings": warnings_list}

    # Fuori Buy Zone ma sotto Max Buy: possibile LIMIT solo se tutti i gate sono validi.
    if score_ok and rr2_ok and rr1_ok and sizing_ready:
        return {
            "decision": "BUY_LIMIT",
            "veto_reasons": ["Setup valido, attendere Buy Zone"],
            "warnings": warnings_list,
        }

    return {
        "decision": "WATCH",
        "veto_reasons": failed or ["Titolo interessante ma non operativo ora"],
        "warnings": warnings_list,
    }


# =============================================================================
# DATA QUALITY
# =============================================================================

def data_quality_engine(c: Dict[str, Any]) -> Dict[str, Any]:
    critical = [
        "price",
        "market_cap",
        "avg_dollar_volume20",
        "ma50",
        "ma200",
        "atr",
        "pe",
        "revenue_growth",
    ]
    optional = [
        "forward_pe",
        "peg",
        "p_fcf",
        "roic",
        "current_ratio",
        "debt_to_equity",
        "f_score",
        "free_cashflow",
        "earnings_date",
    ]

    missing_critical = [k for k in critical if c.get(k) is None]
    missing_optional = [k for k in optional if c.get(k) is None]

    if len(missing_critical) >= 3:
        quality = "POOR"
    elif missing_critical:
        quality = "FAIR"
    elif len(missing_optional) >= 5:
        quality = "FAIR"
    else:
        quality = "GOOD"

    # Un outlier non è automaticamente falso, ma impedisce GOOD finché non verificato.
    if c.get("has_data_anomalies") and quality == "GOOD":
        quality = "FAIR"

    return {
        "data_quality": quality,
        "missing_critical": missing_critical,
        "missing_optional": missing_optional,
    }


# =============================================================================
# BUILD CANDIDATES / SURVIVAL FILTERS
# =============================================================================

def is_otc_like(exchange: Optional[str], ticker: str) -> bool:
    ex = (exchange or "").upper()
    if "OTC" in ex or "PNK" in ex:
        return True
    # Non usare il suffisso come veto assoluto, ma alcuni simboli OTC USA terminano F/Y.
    return False


def passes_survival(c: Dict[str, Any]) -> Tuple[bool, List[str]]:
    reasons: List[str] = []
    price = c.get("price")
    cap = c.get("market_cap")
    adv = c.get("avg_dollar_volume20")

    if price is None or price <= MIN_PRICE:
        reasons.append("Prezzo <= €1 o N/D")
    if cap is None or cap < MIN_MARKET_CAP:
        reasons.append("Market Cap < €200M o N/D")
    if adv is None or adv < MIN_AVG_DOLLAR_VOLUME_SOFT:
        reasons.append("Controvalore medio < €0,75M o N/D")
    if is_otc_like(c.get("exchange"), c.get("ticker", "")):
        reasons.append("OTC/illiquido")

    return len(reasons) == 0, reasons



def is_gem_foreign_listing(ticker: str) -> bool:
    """
    Filtro minimo e trasparente per i simboli GEM/foreign listing come 1LOGN, 1NFLX.
    Non usa l'ISIN come veto assoluto: TEN/STLAM/CPR e altri titoli primari italiani
    con domicilio estero devono restare analizzabili.
    """
    t = (ticker or "").strip().upper()
    return bool(re.fullmatch(r"\d+[A-Z]+", t))


def build_universe_exclusion_candidate(row: pd.Series, reason: str) -> Dict[str, Any]:
    ticker = str(row.get("name", "")).strip().upper()
    return {
        "ticker": ticker,
        "yf_ticker": to_yfinance_ticker(ticker),
        "tv_symbol": to_tv_symbol(ticker),
        "company_name": row.get("description") or ticker,
        "sector": row.get("sector") or "Unknown",
        "exchange": row.get("exchange"),
        "screen_source": row.get("screen_source") or "N/D",
        "price": safe_float(row.get("close")),
        "market_cap": safe_float(row.get("market_cap_basic")),
        "score": 0,
        "quality_score": 0,
        "opportunity_score": 0,
        "data_quality": "N/D",
        "data_coverage_pct": 0.0,
        "decision": "AVOID",
        "operational_state": "AVOID",
        "veto_reasons": [reason],
        "warnings": [],
        "passes_survival": False,
        "survival_fail_reasons": [reason],
        "universe_exclusion_reason": reason,
        "data_anomaly_flags": [],
        "data_anomaly_categories": [],
        "has_data_anomalies": False,
        "data_review_required": False,
    }

def build_candidate(row: pd.Series, benchmark_hist: pd.DataFrame, portfolio_sectors: Dict[str, int], regime: Dict[str, Any]) -> Dict[str, Any]:
    ticker = str(row.get("name", "")).strip().upper()
    yf_ticker = to_yfinance_ticker(ticker)
    yf_d = get_yfinance_details(yf_ticker, benchmark_hist=benchmark_hist)

    price = first_not_none(safe_float(row.get("close")), safe_float(yf_d.get("yf_price")))
    market_cap = first_not_none(safe_float(row.get("market_cap_basic")), safe_float(yf_d.get("market_cap_yf")))

    c: Dict[str, Any] = {
        "ticker": ticker,
        "yf_ticker": yf_ticker,
        "tv_symbol": to_tv_symbol(ticker),
        "company_name": yf_d.get("company_name") or row.get("description") or ticker,
        "sector": row.get("sector") or "Unknown",
        "exchange": row.get("exchange") or yf_d.get("exchange_yf"),
        "screen_source": row.get("screen_source") or "N/D",
        "price": price,
        "market_cap": market_cap,
        "currency": yf_d.get("currency") or "EUR",
        # valuation
        "pe": safe_float(row.get("price_earnings_ttm")),
        "forward_pe": first_not_none(safe_float(row.get("price_earnings_forward_fy")), safe_float(yf_d.get("forward_pe_yf"))),
        "peg": safe_float(yf_d.get("peg_yf")),
        "p_fcf": first_not_none(safe_float(row.get("price_free_cash_flow_ttm")), safe_float(yf_d.get("p_fcf_yf"))),
        "ev_ebitda": first_not_none(safe_float(row.get("enterprise_value_ebitda_ttm")), safe_float(yf_d.get("ev_ebitda_yf"))),
        "fcf_yield": safe_float(yf_d.get("fcf_yield")),
        # quality
        "roe": first_not_none(safe_float(row.get("return_on_equity")), safe_float(yf_d.get("roe_yf"))),
        "roic": safe_float(row.get("return_on_invested_capital")),
        "roa": safe_float(yf_d.get("roa_yf")),
        "gross_margin": safe_float(yf_d.get("gross_margin_yf")),
        "operating_margin": first_not_none(safe_float(row.get("operating_margin")), safe_float(yf_d.get("operating_margin_yf"))),
        "net_margin": first_not_none(safe_float(row.get("net_margin")), safe_float(yf_d.get("net_margin_yf"))),
        "f_score": safe_float(row.get("piotroski_f_score_fy")),
        # growth
        "eps_growth": first_not_none(safe_float(row.get("earnings_per_share_diluted_yoy_growth_ttm")), safe_float(yf_d.get("eps_growth_yf"))),
        "revenue_growth": first_not_none(safe_float(row.get("total_revenue_yoy_growth_ttm")), safe_float(yf_d.get("revenue_growth_yf"))),
        "fcf_growth": safe_float(row.get("free_cash_flow_yoy_growth_ttm")),
        # strength
        "current_ratio": first_not_none(safe_float(row.get("current_ratio_fq")), safe_float(yf_d.get("current_ratio_yf"))),
        "quick_ratio": safe_float(yf_d.get("quick_ratio_yf")),
        "debt_to_equity": first_not_none(safe_float(row.get("debt_to_equity_fq")), safe_float(yf_d.get("debt_to_equity_yf"))),
        "net_debt_ebitda": safe_float(row.get("net_debt_to_ebitda_fq")),
        "interest_coverage": safe_float(row.get("interest_coverage_fy")),
        "altman_z": safe_float(row.get("altman_z_score_fy")),
        # cash quality
        "free_cashflow": safe_float(yf_d.get("free_cashflow")),
        "operating_cashflow": safe_float(yf_d.get("operating_cashflow")),
        "stock_based_compensation": safe_float(yf_d.get("stock_based_compensation")),
        "sbc_to_fcf": safe_float(yf_d.get("sbc_to_fcf")),
        # technicals
        "ma20": safe_float(yf_d.get("ma20")),
        "ma50": safe_float(yf_d.get("ma50")),
        "ma200": safe_float(yf_d.get("ma200")),
        "slope50_1m": safe_float(yf_d.get("slope50_1m")),
        "slope200_1m": safe_float(yf_d.get("slope200_1m")),
        "low20": safe_float(yf_d.get("low20")),
        "low63": safe_float(yf_d.get("low63")),
        "low52": safe_float(yf_d.get("low52")),
        "high20": safe_float(yf_d.get("high20")),
        "high63": safe_float(yf_d.get("high63")),
        "high52": safe_float(yf_d.get("high52")),
        "atr": safe_float(yf_d.get("atr")),
        "atr_pct": safe_float(yf_d.get("atr_pct")),
        "rsi": first_not_none(safe_float(row.get("RSI")), safe_float(yf_d.get("rsi_yf"))),
        "perf1m": first_not_none(safe_float(row.get("Perf.1M")), safe_float(yf_d.get("perf1m_yf"))),
        "perf3m": first_not_none(safe_float(row.get("Perf.3M")), safe_float(yf_d.get("perf3m_yf"))),
        "perf6m": first_not_none(safe_float(row.get("Perf.6M")), safe_float(yf_d.get("perf6m_yf"))),
        "avg_volume20": safe_float(yf_d.get("avg_volume20")),
        "avg_volume50": safe_float(yf_d.get("avg_volume50")),
        "avg_dollar_volume20": safe_float(yf_d.get("avg_dollar_volume20")),
        "relative_volume": safe_float(yf_d.get("relative_volume")),
        "rs_1m": safe_float(yf_d.get("rs_1m")),
        "rs_3m": safe_float(yf_d.get("rs_3m")),
        "rs_6m": safe_float(yf_d.get("rs_6m")),
        # expectations / event
        "target_mean": safe_float(yf_d.get("target_mean")),
        "target_low": safe_float(yf_d.get("target_low")),
        "target_high": safe_float(yf_d.get("target_high")),
        "recommendation_mean": safe_float(yf_d.get("recommendation_mean")),
        "beta": safe_float(yf_d.get("beta")),
        "short_percent_float": safe_float(yf_d.get("short_percent_float")),
        "insider_ownership": safe_float(yf_d.get("insider_ownership")),
        "institutional_ownership": safe_float(yf_d.get("institutional_ownership")),
        "earnings_date": yf_d.get("earnings_date"),
        "days_to_earnings": yf_d.get("days_to_earnings"),
        "data_error": yf_d.get("data_error"),
        "possible_corporate_action": bool(yf_d.get("possible_corporate_action")),
        "corporate_action_status": yf_d.get("corporate_action_status"),
        "corporate_action_reason": yf_d.get("corporate_action_reason"),
        "recent_split_metadata": bool(yf_d.get("recent_split_metadata")),
        "max_raw_adjusted_return_gap_pct": safe_float(yf_d.get("max_raw_adjusted_return_gap_pct")),
        "max_adjusted_jump_63d_pct": safe_float(yf_d.get("max_adjusted_jump_63d_pct")),
        "last_open": safe_float(yf_d.get("last_open")),
        "last_high": safe_float(yf_d.get("last_high")),
        "last_low": safe_float(yf_d.get("last_low")),
        "prev_close": safe_float(yf_d.get("prev_close")),
        "last_volume": safe_float(yf_d.get("last_volume")),
    }

    c["technical_state"] = classify_technical_state(c)
    c["rs_state"] = classify_rs(c)
    c.update(value_trap_engine(c))
    c.update(build_entry_plan(c))
    c.update(data_anomaly_engine(c))
    c.update(trigger_engine(c))

    sizing = position_sizing(c.get("ideal_entry"), c.get("stop"))
    c.update(sizing)

    # R/R LORDO: proprietà della struttura entry/stop/target, indipendente dalla size.
    c["gross_rr_tp1"] = compute_gross_rr(c.get("ideal_entry"), c.get("stop"), c.get("tp1"))
    c["gross_rr_tp2"] = compute_gross_rr(c.get("ideal_entry"), c.get("stop"), c.get("tp2"))
    c["gross_rr_current_tp1"] = compute_gross_rr(c.get("price"), c.get("stop"), c.get("tp1"))
    c["gross_rr_current_tp2"] = compute_gross_rr(c.get("price"), c.get("stop"), c.get("tp2"))

    # R/R NETTO: include il drag commissionale Fineco.
    # Se il sizing operativo non è configurato si usa SOLO una size teorica di riferimento,
    # esplicitamente non operativa, per mostrare l'impatto dei costi.
    rr_shares = c.get("rr_reference_shares") or c.get("shares") or 0
    c["rr_reference_shares_used"] = rr_shares if rr_shares > 0 else None
    c["net_rr_tp1"] = compute_net_rr(c.get("ideal_entry"), c.get("stop"), c.get("tp1"), rr_shares)
    c["net_rr_tp2"] = compute_net_rr(c.get("ideal_entry"), c.get("stop"), c.get("tp2"), rr_shares)
    c["net_rr_current_tp1"] = compute_net_rr(c.get("price"), c.get("stop"), c.get("tp1"), rr_shares)
    c["net_rr_current_tp2"] = compute_net_rr(c.get("price"), c.get("stop"), c.get("tp2"), rr_shares)

    shares = c.get("shares") or 0
    if shares and c.get("tp1") and c.get("ideal_entry"):
        c["profit_tp1_net"] = shares * (c["tp1"] - c["ideal_entry"]) - ROUND_TRIP_COMMISSION
    else:
        c["profit_tp1_net"] = None

    if shares and c.get("tp2") and c.get("ideal_entry"):
        c["profit_tp2_net"] = shares * (c["tp2"] - c["ideal_entry"]) - ROUND_TRIP_COMMISSION
    else:
        c["profit_tp2_net"] = None

    c.update(data_quality_engine(c))
    c.update(calculate_total_score(c, regime["min_net_rr"], portfolio_sectors))
    c.update(decision_engine(c, regime))

    passed, survival_reasons = passes_survival(c)
    c["passes_survival"] = passed
    c["survival_fail_reasons"] = survival_reasons

    return c


def get_ftsemib_benchmark_hist() -> pd.DataFrame:
    """Storico FTSE MIB per Relative Strength, con fallback Yahoo."""
    for symbol in ("FTSEMIB.MI", "^FTSEMIB"):
        df = fetch_market_hist(symbol)
        if df is not None and not df.empty and "Close" in df.columns and len(df) >= 130:
            return df
    return pd.DataFrame()



def build_candidates(df_tv: pd.DataFrame, regime: Dict[str, Any]) -> List[Dict[str, Any]]:
    portfolio_sectors = get_portfolio_sectors()
    benchmark_hist = get_ftsemib_benchmark_hist()
    candidates: List[Dict[str, Any]] = []

    if benchmark_hist.empty:
        print("⚠️ Benchmark FTSE MIB non disponibile: RS 1M/3M/6M resterà N/D")

    for i, (_, row) in enumerate(df_tv.iterrows(), start=1):
        ticker = str(row.get("name", "")).strip().upper()
        if not ticker:
            continue

        # Universe cleanup Italia: GEM/foreign listing tipo 1LOGN, 1NFLX.
        # Viene escluso prima delle chiamate Yahoo per evitare lavoro inutile,
        # ma resta tracciato tra le esclusioni con motivo esplicito.
        if is_gem_foreign_listing(ticker):
            c = build_universe_exclusion_candidate(row, "GEM_FOREIGN_LISTING")
            candidates.append(c)
            print(f"  [{i}/{len(df_tv)}] {ticker}... excluded=GEM_FOREIGN_LISTING")
            continue

        print(f"  [{i}/{len(df_tv)}] {ticker}...", end=" ", flush=True)
        c = build_candidate(row, benchmark_hist, portfolio_sectors, regime)
        candidates.append(c)
        print(f"score={c.get('score')} decision={c.get('decision')}")
        time.sleep(0.10)

    return candidates

def operational_rank_key(c: Dict[str, Any]) -> Tuple[Any, ...]:
    """
    Ranking operativo:
    1) decisione;
    2) numero di gate superati;
    3) stato operativo;
    4) distanza dal gate di score quando marginale;
    5) opportunity / quality / R/R.
    """
    g = gate_status(c)
    op_state = operational_state(c)

    state_rank = {
        "BUY_NOW": 100,
        "LIMIT_READY": 95,
        "READY_FOR_TRIGGER": 90,
        "SCORE_MARGINAL": 85,
        "APPROACHING": 75,
        "WAIT_PRICE": 70,
        "WAIT_TRIGGER": 68,
        "WAIT_SCORE": 65,
        "WAIT_RR": 60,
        "WAIT_CONFIG": 55,
        "DATA_REVIEW": 52,
        "WATCH": 50,
        "AVOID": 10,
        "DATA_INSUFFICIENT": 0,
    }

    score = c.get("opportunity_score") or c.get("score") or 0
    score_gap = max(0, MIN_SCORE_BUY - score)
    dist_zone = abs(c.get("distance_to_buy_zone_pct") or 0.0)

    return (
        DECISION_RANK.get(c.get("decision"), 0),
        g["gates_passed"],
        state_rank.get(op_state, 40),
        -score_gap,
        -dist_zone,
        score,
        c.get("quality_score") or 0,
        c.get("net_rr_tp1") or -999,
        c.get("net_rr_tp2") or -999,
    )


def select_ranked(candidates: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    eligible = [c for c in candidates if c.get("passes_survival")]
    rejected = [c for c in candidates if not c.get("passes_survival")]

    # Attach gate diagnostics prima del ranking.
    for c in eligible:
        c.update(gate_status(c))
        c["operational_state"] = operational_state(c)

    ordered = sorted(eligible, key=operational_rank_key, reverse=True)

    selected: List[Dict[str, Any]] = []
    sector_count: Dict[str, int] = {}
    for c in ordered:
        sector = c.get("sector") or "Unknown"
        if sector_count.get(sector, 0) >= MAX_PER_SECTOR:
            continue
        if (c.get("opportunity_score") or c.get("score") or 0) < MIN_SCORE_WATCH and c.get("decision") not in {"BUY_NOW", "BUY_LIMIT"}:
            continue
        selected.append(c)
        sector_count[sector] = sector_count.get(sector, 0) + 1
        if len(selected) >= TOP_CANDIDATES_EMAIL:
            break

    return selected, rejected


# =============================================================================
# SQLITE HISTORY / CHANGE ENGINE
# =============================================================================


def history_health() -> Dict[str, Any]:
    """Verifica se esiste davvero uno storico riutilizzabile nel run corrente."""
    if not DB_PATH.exists():
        return {
            "history_status": "EMPTY",
            "history_runs": 0,
            "history_candidates": 0,
            "history_note": "Database storico assente: il run potrebbe mostrare tutti i titoli come NEW.",
        }

    try:
        with sqlite3.connect(DB_PATH) as con:
            runs = con.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
            snaps = con.execute("SELECT COUNT(*) FROM candidate_snapshots").fetchone()[0]
        if runs > 0 and snaps > 0:
            return {
                "history_status": "OK",
                "history_runs": runs,
                "history_candidates": snaps,
                "history_note": "Storico SQLite disponibile nel run corrente.",
            }
        return {
            "history_status": "EMPTY",
            "history_runs": runs,
            "history_candidates": snaps,
            "history_note": "Primo run o storico non ripristinato: database presente ma senza snapshot precedenti.",
        }
    except Exception as e:
        return {
            "history_status": "ERROR",
            "history_runs": 0,
            "history_candidates": 0,
            "history_note": f"Errore lettura storico: {e}",
        }


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    JSON_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                run_ts TEXT NOT NULL,
                strategy_version TEXT NOT NULL,
                market_regime TEXT,
                payload_json TEXT NOT NULL
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS candidate_snapshots (
                run_id TEXT NOT NULL,
                run_ts TEXT NOT NULL,
                ticker TEXT NOT NULL,
                score INTEGER,
                decision TEXT,
                operational_state TEXT,
                change_state TEXT,
                selected INTEGER NOT NULL DEFAULT 0,
                price REAL,
                payload_json TEXT NOT NULL,
                PRIMARY KEY (run_id, ticker)
            )
            """
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_snap_ticker_ts ON candidate_snapshots(ticker, run_ts)")
        con.commit()


def get_previous_snapshot(ticker: str) -> Optional[Dict[str, Any]]:
    if not DB_PATH.exists():
        return None
    with sqlite3.connect(DB_PATH) as con:
        row = con.execute(
            """
            SELECT payload_json
            FROM candidate_snapshots
            WHERE ticker = ?
            ORDER BY run_ts DESC
            LIMIT 1
            """,
            (ticker,),
        ).fetchone()
    if not row:
        return None
    try:
        return json.loads(row[0])
    except Exception:
        return None


def get_previous_selected_tickers() -> List[str]:
    if not DB_PATH.exists():
        return []
    with sqlite3.connect(DB_PATH) as con:
        row = con.execute("SELECT run_id FROM runs ORDER BY run_ts DESC LIMIT 1").fetchone()
        if not row:
            return []
        run_id = row[0]
        rows = con.execute(
            "SELECT ticker FROM candidate_snapshots WHERE run_id=? AND selected=1",
            (run_id,),
        ).fetchall()
    return [r[0] for r in rows]


def gate_status(c: Dict[str, Any], rr_min: Optional[float] = None) -> Dict[str, Any]:
    """
    Gate espliciti per l'operatività.
    Non cambia score o soglie: rende auditabile perché un titolo è o non è pronto.
    """
    rr_min = MIN_NET_RR_NORMAL if rr_min is None else rr_min

    score = c.get("opportunity_score") or c.get("score") or 0
    rr1 = c.get("net_rr_tp1")
    rr2 = c.get("net_rr_tp2")
    trigger_state = c.get("trigger_state")
    data_quality = c.get("data_quality")
    dte = c.get("days_to_earnings")
    trap = c.get("value_trap_risk")
    tech = c.get("technical_state")

    score_ok = score >= MIN_SCORE_BUY
    score_marginal = (MIN_SCORE_BUY - SCORE_MARGINAL_GAP) <= score < MIN_SCORE_BUY
    rr1_ok = rr1 is not None and rr1 >= MIN_NET_RR_TP1
    rr2_ok = rr2 is not None and rr2 >= rr_min
    trigger_ok = trigger_state == "CONFIRMED"
    sizing_ok = bool(c.get("risk_sizing_configured")) and (c.get("shares") or 0) > 0
    data_ok = data_quality != "POOR" and not bool(c.get("data_review_required"))
    earnings_ok = dte is None or dte >= 7
    structure_ok = trap != "EXTREME" and tech != "SEVERE_DOWNTREND" and trigger_state != "INVALID"

    gates = {
        "score": score_ok,
        "rr_tp1": rr1_ok,
        "rr_tp2": rr2_ok,
        "trigger": trigger_ok,
        "sizing": sizing_ok,
        "data": data_ok,
        "earnings": earnings_ok,
        "structure": structure_ok,
    }
    passed = sum(1 for v in gates.values() if v)
    failed = [k for k, v in gates.items() if not v]

    return {
        "gate_status": gates,
        "gates_passed": passed,
        "gates_total": len(gates),
        "failed_gates": failed,
        "score_marginal": score_marginal,
    }


def operational_state(c: Dict[str, Any]) -> str:
    decision = c.get("decision")
    g = gate_status(c)

    if decision == "BUY_NOW":
        return "BUY_NOW"
    if decision == "BUY_LIMIT":
        return "LIMIT_READY"
    if decision == "AVOID":
        return "AVOID"
    if decision == "DATA_INSUFFICIENT":
        return "DATA_INSUFFICIENT"
    if c.get("data_review_required"):
        return "DATA_REVIEW"

    gates = g["gate_status"]
    score_marginal = g["score_marginal"]

    # READY_FOR_TRIGGER è volutamente stretto:
    # score + RR + data + earnings + structure + sizing sono OK;
    # manca SOLO il trigger.
    if c.get("in_buy_zone"):
        non_trigger_ok = all(
            gates[k]
            for k in ("score", "rr_tp1", "rr_tp2", "sizing", "data", "earnings", "structure")
        )
        if non_trigger_ok and not gates["trigger"]:
            return "READY_FOR_TRIGGER"

        # SCORE_MARGINAL è una categoria diversa:
        # score entro 2 punti, RR già validi e nessun problema strutturale.
        if (
            score_marginal
            and gates["rr_tp1"]
            and gates["rr_tp2"]
            and gates["data"]
            and gates["earnings"]
            and gates["structure"]
        ):
            return "SCORE_MARGINAL"

        if not gates["rr_tp1"] or not gates["rr_tp2"]:
            return "WAIT_RR"
        if not gates["score"]:
            return "WAIT_SCORE"
        if not gates["sizing"]:
            return "WAIT_CONFIG"
        if not gates["trigger"]:
            return "WAIT_TRIGGER"
        return "BUY_ZONE"

    if c.get("above_max_buy"):
        return "WAIT_PRICE"

    price = c.get("price")
    buy_high = c.get("buy_zone_high")
    atr = c.get("atr")
    if price is not None and buy_high is not None and atr and 0 < price - buy_high <= atr:
        return "APPROACHING"

    if decision == "WAIT":
        if not gates["rr_tp1"] or not gates["rr_tp2"]:
            return "WAIT_RR"
        if not gates["score"]:
            return "WAIT_SCORE"
        if not gates["sizing"]:
            return "WAIT_CONFIG"
        if not gates["trigger"]:
            return "WAIT_TRIGGER"
        return "WAIT"

    return decision or "WATCH"


def change_state(c: Dict[str, Any], prev: Optional[Dict[str, Any]]) -> str:
    if prev is None:
        return "NEW"

    prev_score = prev.get("opportunity_score") or prev.get("score") or 0
    score = c.get("opportunity_score") or c.get("score") or 0
    prev_dec = prev.get("decision")
    dec = c.get("decision")

    prev_price = prev.get("price")
    prev_buy_high = prev.get("buy_zone_high")
    if c.get("in_buy_zone") and prev_price is not None and prev_buy_high is not None and prev_price > prev_buy_high:
        return "ENTERED_BUY_ZONE"

    if prev.get("value_trap_risk") != c.get("value_trap_risk") and c.get("value_trap_risk") in {"HIGH", "EXTREME"}:
        return "THESIS_CHANGED"

    if DECISION_RANK.get(dec, 0) > DECISION_RANK.get(prev_dec, 0) or score - prev_score >= SCORE_CHANGE_MATERIAL:
        return "UPGRADE"

    if DECISION_RANK.get(dec, 0) < DECISION_RANK.get(prev_dec, 0) or prev_score - score >= SCORE_CHANGE_MATERIAL:
        return "DOWNGRADE"

    return "REPEAT"


def attach_history_states(candidates: List[Dict[str, Any]]) -> None:
    for c in candidates:
        prev = get_previous_snapshot(c["ticker"])
        c["previous_snapshot"] = {
            "score": prev.get("score"),
            "decision": prev.get("decision"),
            "price": prev.get("price"),
        } if prev else None
        c["operational_state"] = operational_state(c)
        c["change_state"] = change_state(c, prev)


def json_safe(obj: Any) -> Any:
    if obj is None or isinstance(obj, (str, int, float, bool)):
        if isinstance(obj, float) and not math.isfinite(obj):
            return None
        return obj
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        v = float(obj)
        return v if math.isfinite(v) else None
    if isinstance(obj, (datetime, pd.Timestamp)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {str(k): json_safe(v) for k, v in obj.items() if k != "spy_hist"}
    if isinstance(obj, (list, tuple, set)):
        return [json_safe(v) for v in obj]
    return str(obj)


def save_run(
    run_id: str,
    regime: Dict[str, Any],
    all_candidates: List[Dict[str, Any]],
    selected: List[Dict[str, Any]],
    removed_fields: List[str],
    dropped: List[str],
) -> Path:
    init_db()
    ts = now_utc_iso()
    selected_tickers = {c["ticker"] for c in selected}

    payload = {
        "run_metadata": {
            "run_id": run_id,
            "run_ts": ts,
            "strategy_version": STRATEGY_VERSION,
            "report_name": REPORT_NAME,
        },
        "market_regime": {k: v for k, v in regime.items() if k != "spy_hist"},
        "removed_fields": removed_fields,
        "dropped_from_previous_selected": dropped,
        "candidates": all_candidates,
    }
    payload_safe = json_safe(payload)

    json_path = JSON_DIR / f"{run_id}.json"
    json_path.write_text(json.dumps(payload_safe, indent=2, ensure_ascii=False), encoding="utf-8")

    with sqlite3.connect(DB_PATH) as con:
        con.execute(
            "INSERT INTO runs(run_id, run_ts, strategy_version, market_regime, payload_json) VALUES(?,?,?,?,?)",
            (run_id, ts, STRATEGY_VERSION, regime.get("regime"), json.dumps(payload_safe, ensure_ascii=False)),
        )

        for c in all_candidates:
            c_safe = json_safe(c)
            con.execute(
                """
                INSERT INTO candidate_snapshots(
                    run_id, run_ts, ticker, score, decision, operational_state,
                    change_state, selected, price, payload_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    run_id,
                    ts,
                    c.get("ticker"),
                    c.get("score"),
                    c.get("decision"),
                    c.get("operational_state"),
                    c.get("change_state"),
                    1 if c.get("ticker") in selected_tickers else 0,
                    c.get("price"),
                    json.dumps(c_safe, ensure_ascii=False),
                ),
            )
        con.commit()

    return json_path


# =============================================================================
# EMAIL HTML
# =============================================================================

CHANGE_ICONS = {
    "NEW": "🆕",
    "REPEAT": "🔁",
    "UPGRADE": "⬆️",
    "DOWNGRADE": "⬇️",
    "ENTERED_BUY_ZONE": "🎯",
    "THESIS_CHANGED": "⚠️",
}

DECISION_ICONS = {
    "BUY_NOW": "🟢 BUY NOW",
    "BUY_LIMIT": "🟢 BUY LIMIT",
    "WAIT": "🟡 WAIT",
    "WATCH": "🟠 WATCH",
    "AVOID": "🔴 AVOID",
    "DATA_INSUFFICIENT": "⚫ DATA INSUFFICIENT",
}


def tv_chart_url(ticker: str) -> str:
    return f"https://www.tradingview.com/chart/?symbol={to_tv_symbol(ticker)}"


def action_needed_text(c: Dict[str, Any]) -> str:
    state = c.get("operational_state") or operational_state(c)
    mapping = {
        "BUY_NOW": "Verificare ordine ed esecuzione",
        "LIMIT_READY": "Valutare LIMIT al livello indicato",
        "READY_FOR_TRIGGER": "Attendere solo conferma price action/volume",
        "SCORE_MARGINAL": "RR valido; score vicino soglia, attendere miglioramento/trigger",
        "APPROACHING": "Prezzo vicino alla Buy Zone: monitorare",
        "WAIT_PRICE": "Prezzo troppo alto: non inseguire",
        "WAIT_TRIGGER": "Attendere conferma tecnica",
        "WAIT_SCORE": "Opportunity Score insufficiente",
        "WAIT_RR": "R/R insufficiente al prezzo/struttura attuale",
        "WAIT_CONFIG": "Configurare capitale/sizing prima di agire",
        "WATCH": "Nessuna azione; monitorare",
        "AVOID": "Scartare",
        "DATA_REVIEW": "Verifica manuale dati/anomalie prima di qualsiasi BUY",
        "DATA_INSUFFICIENT": "Dati insufficienti",
    }
    return mapping.get(state, "Monitorare")


def build_action_board(selected: List[Dict[str, Any]], limit: int = 5) -> str:
    """
    Cruscotto operativo compatto.
    Usa lo stesso ranking gate-based della selezione, così la mail non contraddice il motore.
    """
    if not selected:
        return "<p>Nessun candidato operativo.</p>"

    board = sorted(selected, key=operational_rank_key, reverse=True)[:limit]
    rows = ""
    for c in board:
        state = c.get("operational_state") or operational_state(c)
        failed = c.get("failed_gates") or gate_status(c).get("failed_gates", [])
        missing_txt = ", ".join(failed) if failed else "nessuno"
        rr1_g = c.get("gross_rr_tp1")
        rr1_n = c.get("net_rr_tp1")
        rr2_g = c.get("gross_rr_tp2")
        rr2_n = c.get("net_rr_tp2")

        rows += f"""
        <tr>
          <td style='padding:7px'><b>{html_escape(c.get('ticker'))}</b></td>
          <td style='padding:7px'><b>{html_escape(state)}</b></td>
          <td style='padding:7px'>{c.get('opportunity_score', c.get('score', '—'))}</td>
          <td style='padding:7px'>{'N/D' if rr1_g is None else f'{rr1_g:.2f}'} / {'N/D' if rr1_n is None else f'{rr1_n:.2f}'}</td>
          <td style='padding:7px'>{'N/D' if rr2_g is None else f'{rr2_g:.2f}'} / {'N/D' if rr2_n is None else f'{rr2_n:.2f}'}</td>
          <td style='padding:7px'>{html_escape(missing_txt)}</td>
          <td style='padding:7px'>{html_escape(action_needed_text(c))}</td>
        </tr>
        """

    return f"""
    <div style='background:#ffffff;border:2px solid #2563eb;border-radius:10px;padding:14px;margin-top:14px'>
      <div style='font-size:18px;font-weight:800;color:#1e3a5f;margin-bottom:8px'>⚡ ACTION BOARD</div>
      <table style='width:100%;border-collapse:collapse;font-size:12px'>
        <thead style='background:#eff6ff'>
          <tr>
            <th>Ticker</th><th>Stato</th><th>Opportunity</th>
            <th>R/R TP1 G/N</th><th>R/R TP2 G/N</th>
            <th>Gate mancanti</th><th>Azione</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
      <div style='font-size:11px;color:#6b7280;margin-top:7px'>
        G/N = lordo / netto commissioni Fineco. Il ranking privilegia gate superati e vicinanza a un trade eseguibile.
      </div>
    </div>
    """


def generate_html(
    selected: List[Dict[str, Any]],
    rejected: List[Dict[str, Any]],
    regime: Dict[str, Any],
    removed_fields: List[str],
    dropped: List[str],
) -> str:
    today = datetime.now().strftime("%d/%m/%Y")

    buy_now_count = sum(1 for c in selected if c.get("decision") == "BUY_NOW")
    limit_count = sum(1 for c in selected if c.get("decision") == "BUY_LIMIT")
    ready_trigger_count = sum(1 for c in selected if c.get("operational_state") == "READY_FOR_TRIGGER")
    score_marginal_count = sum(1 for c in selected if c.get("operational_state") == "SCORE_MARGINAL")
    watch_count = sum(
        1 for c in selected
        if c.get("operational_state") not in {"BUY_NOW", "LIMIT_READY", "READY_FOR_TRIGGER", "SCORE_MARGINAL"}
    )
    new_count = sum(1 for c in selected if c.get("change_state") == "NEW")

    if buy_now_count:
        day_decision = f"{buy_now_count} BUY CONFERMATO/I - VERIFICARE ORDINE"
    elif limit_count:
        day_decision = f"NESSUN BUY NOW - {limit_count} LIMIT PRONTO/I"
    elif ready_trigger_count:
        day_decision = f"NESSUN BUY - {ready_trigger_count} READY FOR TRIGGER"
    elif score_marginal_count:
        day_decision = f"NESSUN BUY - {score_marginal_count} SCORE MARGINAL"
    elif selected:
        day_decision = "NESSUN BUY CONFERMATO - ASPETTA"
    else:
        day_decision = "NON COMPRARE"

    change_rows = ""
    material_states = {"NEW", "UPGRADE", "DOWNGRADE", "ENTERED_BUY_ZONE", "THESIS_CHANGED"}
    material = [c for c in selected if c.get("change_state") in material_states]
    repeats = [c for c in selected if c.get("change_state") == "REPEAT"]

    for c in material + repeats[:3]:
        prev = c.get("previous_snapshot") or {}
        change_rows += f"""
        <tr>
          <td style='padding:8px'>{CHANGE_ICONS.get(c.get('change_state'), '')} {html_escape(c.get('change_state'))}</td>
          <td style='padding:8px'><b>{html_escape(c.get('ticker'))}</b></td>
          <td style='padding:8px'>{prev.get('score', '—')}</td>
          <td style='padding:8px'><b>Q {c.get('quality_score', '—')} / O {c.get('opportunity_score', c.get('score', '—'))}</b></td>
          <td style='padding:8px'>{DECISION_ICONS.get(c.get('decision'), c.get('decision'))}</td>
          <td style='padding:8px'>{html_escape(c.get('operational_state'))}</td>
        </tr>
        """

    top_rows = ""
    for i, c in enumerate(selected[:TOP_N], 1):
        rr1_g = c.get("gross_rr_tp1")
        rr1 = c.get("net_rr_tp1")
        rr2_g = c.get("gross_rr_tp2")
        rr2 = c.get("net_rr_tp2")
        risk_pct = c.get("risk_pct_trading_capital")
        top_rows += f"""
        <tr>
          <td style='padding:8px'>#{i}</td>
          <td style='padding:8px'><b>{html_escape(c['ticker'])}</b><br><span style='color:#6b7280;font-size:11px'>{html_escape(c.get('company_name'))}</span></td>
          <td style='padding:8px'><b>{c.get('quality_score')}</b></td><td style='padding:8px'><b>{c.get('opportunity_score', c.get('score'))}</b></td>
          <td style='padding:8px'>{fmt_price(c.get('price'))}</td>
          <td style='padding:8px'>{fmt_price(c.get('buy_zone_low'))} - {fmt_price(c.get('buy_zone_high'))}</td>
          <td style='padding:8px'>{fmt_pct(c.get('distance_to_buy_zone_pct'))}</td>
          <td style='padding:8px'>{html_escape(c.get('trigger_state'))}</td>
          <td style='padding:8px'>{'N/D' if rr1_g is None else f'{rr1_g:.2f}'} / {'N/D' if rr1 is None else f'{rr1:.2f}'}</td>
          <td style='padding:8px'>{'N/D' if rr2_g is None else f'{rr2_g:.2f}'} / {'N/D' if rr2 is None else f'{rr2:.2f}'}</td>
          <td style='padding:8px'>{fmt_price(c.get('net_risk_total'))}</td>
          <td style='padding:8px'>{fmt_pct(risk_pct)}</td>
          <td style='padding:8px'>{fmt_num(c.get('data_coverage_pct'),1)}%</td>
          <td style='padding:8px'><b>{DECISION_ICONS.get(c.get('decision'), c.get('decision'))}</b></td>
        </tr>
        """

    details = ""
    for i, c in enumerate(selected[:TOP_N], 1):
        penalties = ", ".join(f"{p['name']} ({p['points']})" for p in c.get("penalties", [])) or "Nessuna penalità materiale"
        veto = "; ".join(c.get("veto_reasons", [])) or "Nessun veto"
        missing = ", ".join(c.get("missing_critical", [])) or "nessuno"
        comp = c.get("score_components", {})
        earnings = c.get("earnings_date") or "N/D"
        rr1_g = c.get("gross_rr_tp1")
        rr2_g = c.get("gross_rr_tp2")
        rr1 = c.get("net_rr_tp1")
        rr2 = c.get("net_rr_tp2")
        rr1_current_g = c.get("gross_rr_current_tp1")
        rr2_current_g = c.get("gross_rr_current_tp2")
        rr1_current = c.get("net_rr_current_tp1")
        rr2_current = c.get("net_rr_current_tp2")
        warnings_txt = "; ".join(c.get("warnings", [])) or "nessuno"
        anomalies_txt = "; ".join(c.get("data_anomaly_flags", [])) or "nessuna"
        sizing_warning = c.get("sizing_warning") or "nessuno"
        portfolio_component = comp.get("portfolio_fit")
        portfolio_display = "N/D" if portfolio_component is None else str(portfolio_component)

        details += f"""
        <div style='background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:18px;margin:16px 0'>
          <div style='font-size:20px;font-weight:800'>#{i} {html_escape(c['ticker'])} · {html_escape(c.get('company_name'))}</div>
          <div style='margin:5px 0 12px;font-weight:700'>{CHANGE_ICONS.get(c.get('change_state'), '')} {html_escape(c.get('change_state'))} · {DECISION_ICONS.get(c.get('decision'), c.get('decision'))} · Quality {c.get('quality_score')}/100 · Opportunity {c.get('opportunity_score', c.get('score'))}/100</div>

          <table style='width:100%;border-collapse:collapse;font-size:12px'>
            <tr>
              <td><b>Prezzo</b><br>{fmt_price(c.get('price'))}</td>
              <td><b>Entry ideale</b><br>{fmt_price(c.get('ideal_entry'))}</td>
              <td><b>Buy Zone</b><br>{fmt_price(c.get('buy_zone_low'))} - {fmt_price(c.get('buy_zone_high'))}</td>
              <td><b>Max Buy</b><br>{fmt_price(c.get('max_buy'))}</td>
            </tr>
            <tr>
              <td><b>Stop</b><br>{fmt_price(c.get('stop'))}</td>
              <td><b>TP1</b><br>{fmt_price(c.get('tp1'))}</td>
              <td><b>TP2</b><br>{fmt_price(c.get('tp2'))}</td>
              <td><b>R/R Entry lordo/netto</b><br>
              TP1 {'N/D' if rr1_g is None else f'{rr1_g:.2f}'} / {'N/D' if rr1 is None else f'{rr1:.2f}'} ·
              TP2 {'N/D' if rr2_g is None else f'{rr2_g:.2f}'} / {'N/D' if rr2 is None else f'{rr2:.2f}'}</td>
            </tr>
          </table>

          <div style='margin-top:12px;font-size:12px;line-height:1.7'>
            <b>Setup:</b> {html_escape(c.get('technical_state'))} ·
            <b>RS vs FTSE MIB:</b> {html_escape(c.get('rs_state'))} ·
            <b>Value Trap:</b> {html_escape(c.get('value_trap_risk'))} ·
            <b>Data Quality:</b> {html_escape(c.get('data_quality'))}<br>
            <b>Trigger:</b> {html_escape(c.get('trigger'))} · <b>Trigger State:</b> {html_escape(c.get('trigger_state'))}<br>
            <b>Trigger reason:</b> {html_escape(c.get('trigger_reason'))}<br>
            <b>Distanza Buy Zone:</b> {fmt_pct(c.get('distance_to_buy_zone_pct'))} · <b>Distanza Max Buy:</b> {fmt_pct(c.get('distance_to_max_buy_pct'))}<br>
            <b>Earnings:</b> {html_escape(earnings)} · <b>giorni:</b> {c.get('days_to_earnings') if c.get('days_to_earnings') is not None else 'N/D'}<br>
            <b>Quantità risk-based:</b> {c.get('shares', 0)} · <b>Capitale:</b> {fmt_price(c.get('invested'))} · <b>Rischio €:</b> {fmt_price(c.get('net_risk_total'))} · <b>Risk % Trading Capital:</b> {fmt_pct(c.get('risk_pct_trading_capital'))}<br>
            <b>Sizing:</b> {html_escape(sizing_warning)}<br>
            <b>Profitto netto TP1:</b> {fmt_price(c.get('profit_tp1_net'))} · <b>TP2:</b> {fmt_price(c.get('profit_tp2_net'))}<br>
            <b>R/R ENTRY TP1 lordo/netto:</b> {'N/D' if rr1_g is None else f'{rr1_g:.2f}'} / {'N/D' if rr1 is None else f'{rr1:.2f}'} ·
            <b>TP2:</b> {'N/D' if rr2_g is None else f'{rr2_g:.2f}'} / {'N/D' if rr2 is None else f'{rr2:.2f}'}<br>
            <b>R/R CURRENT TP1 lordo/netto:</b> {'N/D' if rr1_current_g is None else f'{rr1_current_g:.2f}'} / {'N/D' if rr1_current is None else f'{rr1_current:.2f}'} ·
            <b>TP2:</b> {'N/D' if rr2_current_g is None else f'{rr2_current_g:.2f}'} / {'N/D' if rr2_current is None else f'{rr2_current:.2f}'}<br>
            <b>Size teorica usata solo per R/R netto:</b> {c.get('rr_reference_shares_used') or 'N/D'}<br>
            <b>Data Coverage:</b> {fmt_num(c.get('data_coverage_pct'),1)}% · <b>Anomalie:</b> {html_escape(anomalies_txt)}<br>
            <b>Data Review:</b> {'SI' if c.get('data_review_required') else 'NO'} ·
            <b>Corporate Action:</b> {html_escape(c.get('corporate_action_status') or 'N/D')}<br>
            <b>Warning:</b> {html_escape(warnings_txt)}<br>
            <b>Penalità:</b> {html_escape(penalties)}<br>
            <b>Veto/Reason:</b> {html_escape(veto)}<br>
            <b>Campi critici mancanti:</b> {html_escape(missing)}
          </div>

          <hr style='border:0;border-top:1px solid #e5e7eb;margin:14px 0'>

          <div style='font-size:12px;line-height:1.8;color:#374151'>
            <b>P/E:</b> {fmt_num(c.get('pe'))} ·
            <b>Forward P/E:</b> {fmt_num(c.get('forward_pe'))} ·
            <b>PEG:</b> {fmt_num(c.get('peg'))} ·
            <b>P/FCF:</b> {fmt_num(c.get('p_fcf'))} ·
            <b>EV/EBITDA:</b> {fmt_num(c.get('ev_ebitda'))}<br>
            <b>ROE:</b> {fmt_pct(c.get('roe'))} ·
            <b>ROIC:</b> {fmt_pct(c.get('roic'))} ·
            <b>Op Margin:</b> {fmt_pct(c.get('operating_margin'))} ·
            <b>Net Margin:</b> {fmt_pct(c.get('net_margin'))}<br>
            <b>Revenue growth:</b> {fmt_pct(c.get('revenue_growth'))} ·
            <b>EPS growth:</b> {fmt_pct(c.get('eps_growth'))} ·
            <b>FCF growth:</b> {fmt_pct(c.get('fcf_growth'))}<br>
            <b>D/E:</b> {fmt_num(c.get('debt_to_equity'))} ·
            <b>Net Debt/EBITDA:</b> {fmt_num(c.get('net_debt_ebitda'))} ·
            <b>F-Score:</b> {fmt_num(c.get('f_score'), 0)}<br>
            <b>RSI:</b> {fmt_num(c.get('rsi'), 1)} ·
            <b>ATR%:</b> {fmt_pct(c.get('atr_pct'))} ·
            <b>RS 1M/3M/6M:</b> {fmt_pct(c.get('rs_1m'))} / {fmt_pct(c.get('rs_3m'))} / {fmt_pct(c.get('rs_6m'))}
          </div>

          <div style='margin-top:10px;font-size:12px'>
            <b>Score components:</b>
            Val {comp.get('valuation','—')} · Quality {comp.get('business_quality','—')} · Growth {comp.get('growth_quality','—')} ·
            Strength {comp.get('financial_strength','—')} · EarningsQ {comp.get('earnings_quality','—')} ·
            Catalyst Proxy {comp.get('catalyst_expectations','—')} · Technical {comp.get('technical_setup','—')} ·
            Volume/RS {comp.get('volume_rs','—')} · Entry/RR {comp.get('entry_rr','—')} · Portfolio {portfolio_display}
          </div>

          <div style='margin-top:14px'>
            <a href='{tv_chart_url(c['ticker'])}' style='display:inline-block;padding:9px 13px;background:#2563eb;color:white;text-decoration:none;border-radius:7px;font-weight:700'>📈 Grafico TradingView</a>
          </div>
        </div>
        """

    dropped_html = ""
    if dropped:
        dropped_html = "<p><b>❌ DROPPED rispetto alla precedente Top:</b> " + ", ".join(map(html_escape, dropped)) + "</p>"

    removed_html = ""
    if removed_fields:
        removed_html = "<p><b>Campi TradingView rimossi automaticamente:</b> " + ", ".join(map(html_escape, removed_fields)) + "</p>"

    rejected_sorted = sorted(rejected, key=lambda c: c.get("score") or 0, reverse=True)[:5]
    rejected_html = ""
    if rejected_sorted:
        lis = "".join(
            f"<li><b>{html_escape(c.get('ticker'))}</b>: {html_escape(', '.join(c.get('survival_fail_reasons', [])))}</li>"
            for c in rejected_sorted
        )
        rejected_html = f"<ul>{lis}</ul>"

    return f"""
    <!doctype html>
    <html>
    <body style='font-family:Arial,Helvetica,sans-serif;background:#f3f4f6;padding:20px;color:#111827'>
      <div style='max-width:1180px;margin:auto'>
        <div style='background:#172554;color:white;padding:22px;border-radius:12px'>
          <div style='font-size:24px;font-weight:800'>{REPORT_NAME}</div>
          <div style='margin-top:5px;color:#bfdbfe'>{today} · Strategy {STRATEGY_VERSION} · 3-6 mesi</div>
          <div style='margin-top:12px;font-size:18px;font-weight:800'>🎯 DECISIONE DI OGGI: {day_decision}</div>
        </div>

        <div style='background:white;padding:14px;border-radius:10px;margin-top:14px'>
          <b>🌎 MARKET REGIME ITALIA:</b> {html_escape(regime.get('regime'))} ·
          <b>Risk Vol:</b> {fmt_num(regime.get('vix'),1)} ·
          <b>Net R/R minimo:</b> {fmt_num(regime.get('min_net_rr'),1)} ·
          <b>Max nuovi BUY:</b> {regime.get('max_new_buys')} ·
          <b>Portfolio Heat:</b> {fmt_pct(regime.get('portfolio_heat_pct'))} ({html_escape(regime.get('portfolio_heat_status'))})<br>
          <span style='font-size:12px;color:#6b7280'>Il regime modifica l'asticella d'ingresso; Portfolio Heat è N/D se capitale/stop delle posizioni non sono configurati.</span>
        </div>

        {build_action_board(selected)}

        <h2>🔔 Cosa è cambiato</h2>
        <div style='background:white;border-radius:10px;overflow:auto'>
          <table style='width:100%;border-collapse:collapse;font-size:12px'>
            <thead style='background:#312e81;color:white'><tr><th>Stato</th><th>Ticker</th><th>Score prec.</th><th>Quality / Opportunity</th><th>Decisione</th><th>Operational</th></tr></thead>
            <tbody>{change_rows or '<tr><td colspan="6" style="padding:10px">Nessun cambiamento materiale.</td></tr>'}</tbody>
          </table>
        </div>
        {dropped_html}

        <h2>🏆 Top opportunities</h2>
        <div style='background:white;border-radius:10px;overflow:auto'>
          <table style='width:100%;border-collapse:collapse;font-size:12px'>
            <thead style='background:#1e3a5f;color:white'>
              <tr><th>#</th><th>Ticker</th><th>Quality</th><th>Opportunity</th><th>Prezzo</th><th>Buy Zone</th><th>Dist. Zone</th><th>Trigger</th><th>R/R TP1 G/N</th><th>R/R TP2 G/N</th><th>Risk €</th><th>Risk %</th><th>Coverage</th><th>Decisione</th></tr>
            </thead>
            <tbody>{top_rows or '<tr><td colspan="14" style="padding:10px"><b>NESSUN TITOLO MERITA UN ACQUISTO / WATCH OPERATIVA OGGI.</b></td></tr>'}</tbody>
          </table>
        </div>

        <h2>📋 Analisi dettagliata</h2>
        {details}

        <div style='background:#fff;padding:14px;border-radius:10px;margin-top:16px;font-size:12px'>
          <b>🚫 Esclusioni Survival Filter (prime 5):</b>{rejected_html or ' nessuna'}
          {removed_html}
          <p><b>Data quality:</b> un dato mancante resta N/D. Non viene sostituito con una stima silenziosa.</p>
          <p><b>* Catalyst Proxy:</b> nella v1.0 è un proxy quantitativo. Non sostituisce la lettura di guidance, conference call o catalyst qualitativi verificati.</p>
          <p><b>Risk sizing:</b> se TRADING_CAPITAL non è configurato, nessuna quantità viene presentata come operativa e nessun BUY viene approvato.</p>
          <p><b>R/R:</b> il lordo misura solo struttura entry/stop/target; il netto include le commissioni Fineco usando la size operativa oppure, se il capitale non è configurato, una size teorica dichiarata esclusivamente per stimare il drag dei costi.</p>
          <p><b>Data anomaly:</b> gli outlier restano visibili e abbassano la qualità dati; non vengono corretti o eliminati silenziosamente.</p>
          <p><b>Forward test:</b> ogni run viene salvato in SQLite + JSON. La persistenza tra GitHub Actions richiede che il workflow conservi/ripristini la cartella data.</p>
          <p><b>Backtest:</b> l'eventuale backtest OHLCV valida timing/gestione, non valida da solo la selezione fondamentale.</p>
          <p><b>Storico:</b> {html_escape(regime.get('history_status'))} · {html_escape(regime.get('history_note'))}</p>
          <p><b>Proprietà:</b> Copyright © 2026 Antonio Larocca. Tutti i diritti riservati. Qualsiasi utilizzo, copia, modifica, distribuzione o riutilizzo totale o parziale da parte di terzi richiede preventiva autorizzazione scritta del proprietario.</p>
        </div>

        <div style='text-align:center;color:#9ca3af;font-size:11px;padding:18px'>
          Report automatico informativo. Nessun BUY è obbligatorio: la liquidità è una posizione valida.<br>© 2026 Antonio Larocca · Uso riservato · Riproduzione o riutilizzo previa autorizzazione.
        </div>
      </div>
    </body>
    </html>
    """


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    start = datetime.now()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    session = italian_market_session_status()
    if ENFORCE_MARKET_SESSION and not FORCE_RUN_OUTSIDE_SESSION and not session["market_session_open"]:
        print(f"⏸️ Borsa Italiana chiusa / fuori sessione: {session['market_local_time']}")
        print("Nessuna email inviata.")
        return

    print("=" * 80)
    print(f"🇮🇹 {REPORT_NAME} · {STRATEGY_VERSION}")
    print("=" * 80)
    print(start.strftime("%d/%m/%Y %H:%M:%S"))

    init_db()
    history = history_health()
    previous_selected = set(get_previous_selected_tickers())

    print("\n🇮🇹 Market regime Italia...")
    regime = market_regime_engine()
    regime.update(portfolio_heat_engine())
    regime.update(history)
    print(
        f"  {regime['regime']} | FTSE MIB={regime.get('ftsemib_symbol')} | RiskVol={regime.get('vix')} | min Net R/R={regime['min_net_rr']} | "
        f"Portfolio Heat={fmt_pct(regime.get('portfolio_heat_pct'))}"
    )

    df_tv, removed_fields = run_tradingview_discovery()
    if df_tv.empty:
        subject = f"🇮🇹 Italia Opportunities | {datetime.now().strftime('%d/%m/%Y')} | nessun candidato"
        html = (
            f"<h2>{REPORT_NAME}</h2><p>Nessun candidato restituito da TradingView.</p>"
            f"<p>Campi rimossi: {', '.join(removed_fields) if removed_fields else 'nessuno'}</p>"
        )
        send_email(subject, html, is_html=True)
        return

    print(f"\n📊 Arricchimento di {len(df_tv)} candidati...")
    candidates = build_candidates(df_tv, regime)

    # Prima selezione con decisioni grezze.
    selected, rejected = select_ranked(candidates)

    # Cap nuovi BUY del Market Regime: applicato PRIMA dello storico.
    actionable = [c for c in selected if c.get("decision") in {"BUY_NOW", "BUY_LIMIT"}]
    if len(actionable) > regime["max_new_buys"]:
        allowed = set(c["ticker"] for c in actionable[: regime["max_new_buys"]])
        for c in selected:
            if c.get("decision") in {"BUY_NOW", "BUY_LIMIT"} and c["ticker"] not in allowed:
                c["decision"] = "WAIT"
                c.setdefault("veto_reasons", []).append("Cap nuovi BUY imposto dal Market Regime")

    # Stati operativi e Change Engine DEVONO riflettere la decisione finale.
    attach_history_states(candidates)

    current_selected = {c["ticker"] for c in selected}
    dropped = sorted(previous_selected - current_selected)

    print("\n🏆 TOP")
    for i, c in enumerate(selected[:TOP_N], 1):
        rr2_val = c.get("net_rr_tp2")
        rr2_str = "N/D" if rr2_val is None else f"{rr2_val:.2f}"
        print(
            f"#{i} {c['ticker']:6} | Q={c.get('quality_score',0):3} | O={c.get('opportunity_score', c.get('score',0)):3} | {c['decision']:10} | "
            f"price={fmt_price(c.get('price'))} | entry={fmt_price(c.get('ideal_entry'))} | "
            f"RR2={rr2_str} | {c.get('change_state')}"
        )

    json_path = save_run(run_id, regime, candidates, selected, removed_fields, dropped)
    print(f"\n💾 Snapshot: {json_path}")
    print(f"💾 Database: {DB_PATH}")

    html = generate_html(selected, rejected, regime, removed_fields, dropped)
    buy_now_count = sum(1 for c in selected if c.get("decision") == "BUY_NOW")
    limit_count = sum(1 for c in selected if c.get("decision") == "BUY_LIMIT")
    ready_trigger_count = sum(1 for c in selected if c.get("operational_state") == "READY_FOR_TRIGGER")
    score_marginal_count = sum(1 for c in selected if c.get("operational_state") == "SCORE_MARGINAL")
    watch_count = sum(
        1 for c in selected
        if c.get("operational_state") not in {"BUY_NOW", "LIMIT_READY", "READY_FOR_TRIGGER", "SCORE_MARGINAL"}
    )
    new_count = sum(1 for c in selected if c.get("change_state") == "NEW")
    today = datetime.now().strftime("%d/%m/%Y")
    subject = (
        f"🇮🇹 Italia Opportunities | {today} | {buy_now_count} BUY NOW · "
        f"{limit_count} LIMIT READY · {ready_trigger_count} READY TRIGGER · "
        f"{score_marginal_count} SCORE MARGINAL · {watch_count} WATCH · {new_count} NEW"
    )

    print("\n📧 Invio email...", end=" ")
    ok = send_email(subject, html, is_html=True)
    print("OK" if ok else "KO")

    elapsed = (datetime.now() - start).total_seconds()
    print(f"⏱️ Completato in {elapsed:.1f}s")


if __name__ == "__main__":
    main()