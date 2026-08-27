import email
import imaplib
import os
from email.header import decode_header, make_header

from fineco_alert_bridge.parser import format_whatsapp, parse_fineco_alert
from fineco_alert_bridge.tradingview import fetch_tradingview_data
from fineco_alert_bridge.whatsapp import send_callmebot

IMAP_HOST = os.getenv("FINECO_IMAP_HOST", "imap.gmail.com")
FINECO_SENDER = os.getenv("FINECO_SENDER", "service@finecobank.com")
FINECO_SUBJECT = os.getenv("FINECO_SUBJECT", "Alert da FinecoBank")
FINECO_LABEL = os.getenv("FINECO_LABEL", "BANCHE")


def _decode_subject(msg) -> str:
    raw = msg.get("Subject", "")
    return str(make_header(decode_header(raw)))


def _extract_text(msg) -> str:
    if msg.is_multipart():
        parts = []
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition", ""))
            if ctype == "text/plain" and "attachment" not in disp.lower():
                payload = part.get_payload(decode=True) or b""
                charset = part.get_content_charset() or "utf-8"
                parts.append(payload.decode(charset, errors="replace"))
        return "\n".join(parts)
    payload = msg.get_payload(decode=True) or b""
    charset = msg.get_content_charset() or "utf-8"
    return payload.decode(charset, errors="replace")


def _select_mailbox(mail: imaplib.IMAP4_SSL) -> str:
    """Preferisce l'etichetta BANCHE; fallback su Tutti i messaggi."""
    status, boxes = mail.list()
    decoded = [raw.decode("utf-8", errors="replace") for raw in (boxes or [])] if status == "OK" else []

    for line in decoded:
        if FINECO_LABEL.lower() in line.lower():
            mailbox = line.split('"/"')[-1].strip() if '"/"' in line else line.split()[-1]
            status, _ = mail.select(mailbox)
            if status == "OK":
                return mailbox

    for line in decoded:
        if "\\All" in line:
            mailbox = line.split('"/"')[-1].strip() if '"/"' in line else line.split()[-1]
            status, _ = mail.select(mailbox)
            if status == "OK":
                return mailbox

    for mailbox in ('"[Gmail]/All Mail"', '"[Google Mail]/All Mail"'):
        status, _ = mail.select(mailbox)
        if status == "OK":
            return mailbox

    raise RuntimeError("Impossibile selezionare l'etichetta BANCHE o Tutti i messaggi")


def process_unread_alerts() -> int:
    gmail_user = os.environ["GMAIL_SENDER"]
    gmail_password = os.environ["GMAIL_PASSWORD"]

    processed = 0
    mail = imaplib.IMAP4_SSL(IMAP_HOST)
    try:
        mail.login(gmail_user, gmail_password)
        mailbox = _select_mailbox(mail)
        print(f"Mailbox selezionata: {mailbox}")
        status, data = mail.search(None, "UNSEEN", "FROM", f'"{FINECO_SENDER}"')
        if status != "OK":
            raise RuntimeError("Ricerca IMAP non riuscita")

        msg_ids = data[0].split()
        print(f"Alert Fineco non letti trovati: {len(msg_ids)}")

        for msg_id in msg_ids:
            status, raw_data = mail.fetch(msg_id, "(RFC822)")
            if status != "OK":
                continue
            raw_email = raw_data[0][1]
            msg = email.message_from_bytes(raw_email)
            subject = _decode_subject(msg)
            if FINECO_SUBJECT.lower() not in subject.lower():
                print(f"SKIP {msg_id.decode()}: oggetto non Fineco ({subject})")
                continue

            text = _extract_text(msg)
            alert = parse_fineco_alert(text)
            if not alert:
                print(f"SKIP {msg_id.decode()}: formato Fineco non riconosciuto")
                continue

            # TradingView viene interrogato SOLO quando esiste un nuovo alert Fineco valido.
            tv = None
            try:
                print(f"TradingView lookup: {alert.titolo} | {alert.mercato}")
                tv = fetch_tradingview_data(alert)
                if tv is None:
                    print("TradingView: dati non disponibili, invio comunque alert Fineco")
                else:
                    print(
                        f"TradingView OK: prezzo={tv.prezzo_attuale} "
                        f"1H={tv.segnale_1h} 4H={tv.segnale_4h} 1D={tv.segnale_1d}"
                    )
            except Exception as exc:
                print(f"TradingView ERROR: {type(exc).__name__}: {exc}")

            # L'alert Fineco non viene perso se TradingView è temporaneamente indisponibile.
            send_callmebot(format_whatsapp(alert, tv))
            mail.store(msg_id, "+FLAGS", "\\Seen")
            processed += 1
            print(f"SENT {alert.titolo} {alert.mercato} {alert.prezzo}")
    finally:
        try:
            mail.logout()
        except Exception:
            pass
    return processed


if __name__ == "__main__":
    count = process_unread_alerts()
    print(f"Fineco alerts inviati: {count}")
