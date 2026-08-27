import re
from dataclasses import dataclass


@dataclass
class FinecoAlert:
    titolo: str
    mercato: str
    prezzo: str
    data: str
    ora: str


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


def format_whatsapp(alert: FinecoAlert) -> str:
    return (
        "🚨 FINECO ALERT\n\n"
        f"{alert.titolo} | {alert.mercato}\n"
        f"💵 Prezzo: {alert.prezzo}\n"
        f"🕐 {alert.data} {alert.ora}\n\n"
        "Alert Fineco scattato. Verificare il titolo prima di operare."
    )
