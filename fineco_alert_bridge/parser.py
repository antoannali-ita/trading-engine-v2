import re
from dataclasses import dataclass


@dataclass
class FinecoAlert:
    titolo: str
    mercato: str
    prezzo: str
    data: str
    ora: str


@dataclass
class TradingViewData:
    prezzo_attuale: str | None = None
    segnale: str | None = None
    range_min: str | None = None
    range_max: str | None = None
    entry_ideale: str | None = None
    stop_loss: str | None = None
    tp1: str | None = None
    tp1_pct: str | None = None
    tp2: str | None = None
    tp2_pct: str | None = None
    tp3: str | None = None
    tp3_pct: str | None = None
    prezzo_in_buy_zone: str | None = None
    azione: str | None = None


def parse_fineco_alert(text: str) -> FinecoAlert | None:
    """Estrae i campi principali dal corpo testuale di una mail Fineco Alert."""
    patterns = {
        "titolo": r"Titolo:\s*([^\r\n]+)",
        "mercato": r"Mercato:\s*([^\r\n]+)",
        "prezzo": r"Ultimo prezzo:\s*([^\r\n]+)",
        "data": r"Data:\s*([^\r\n]+)",
        "ora": r"Ora:\s*([^\r\n]+)",
    }
    values = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            return None
        values[key] = match.group(1).strip()
    return FinecoAlert(**values)


def _v(value: str | None) -> str:
    return value if value not in (None, "") else "n.d."


def format_whatsapp(alert: FinecoAlert, tv: TradingViewData | None = None) -> str:
    """Formatta l'alert Fineco e, se disponibili, aggiunge i dati tecnici TradingView."""
    header = (
        "🚨 ALERT PREZZO FINECO\n\n"
        f"{alert.titolo} | {alert.mercato}\n"
        f"Alert Fineco scattato a: {alert.prezzo}\n"
        f"🕐 {alert.data} {alert.ora}\n"
    )

    if tv is None:
        return (
            header
            + "\n📊 ANALISI TRADINGVIEW\n\n"
            + "Dati TradingView non ancora disponibili per questo alert.\n\n"
            + "Fonte alert: Fineco\n"
            + "Dati tecnici: TradingView (non ancora collegati)"
        )

    return (
        header
        + "\n📊 ANALISI TRADINGVIEW\n\n"
        + f"Prezzo attuale: {_v(tv.prezzo_attuale)}\n"
        + f"Segnale tecnico: {_v(tv.segnale)}\n\n"
        + "🟢 ZONA DI INGRESSO\n"
        + f"Range: {_v(tv.range_min)} - {_v(tv.range_max)}\n"
        + f"Entry ideale: {_v(tv.entry_ideale)}\n\n"
        + "🛑 STOP LOSS\n"
        + f"SL: {_v(tv.stop_loss)}\n\n"
        + "🎯 TARGET\n"
        + f"TP1: {_v(tv.tp1)}  ({_v(tv.tp1_pct)})\n"
        + f"TP2: {_v(tv.tp2)}  ({_v(tv.tp2_pct)})\n"
        + f"TP3: {_v(tv.tp3)}  ({_v(tv.tp3_pct)})\n\n"
        + "📈 VALUTAZIONE\n"
        + f"Prezzo nella Buy Zone: {_v(tv.prezzo_in_buy_zone)}\n"
        + f"Azione: {_v(tv.azione)}\n\n"
        + "Fonte alert: Fineco\n"
        + "Dati tecnici: TradingView"
    )
