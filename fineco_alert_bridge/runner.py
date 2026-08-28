from __future__ import annotations

import email
import imaplib
import os
import time
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


def _fetch_without_marking_seen(mail: imaplib.IMAP4_SSL, msg_id: bytes):
    """Fetch the full message without consuming the UNSEEN checkpoint."""
    status, raw_data = mail.fetch(msg_id, "(BODY.PEEK[])")
    if status != "OK" or not raw_data or not isinstance(raw_data[0], tuple):
        raise RuntimeError(f"IMAP fetch PEEK fallito per msg_id={msg_id.decode(errors='replace')}")
    return raw_data[0][1]


def _mark_seen(mail: imaplib.IMAP4_SSL, msg_id: bytes, attempts: int = 3) -> None:
    """Commit the Gmail checkpoint only after provider acceptance."""
    for attempt in range(1, attempts + 1):
        status, _ = mail.store(msg_id, "+FLAGS", "\\Seen")
        if status == "OK":
            return
        if attempt < attempts:
            print(f"MAIL_SEEN_RETRY attempt={attempt}/{attempts}")
            time.sleep(1)
    raise RuntimeError(f"Impossibile marcare come letta la mail {msg_id.decode(errors='replace')}")


def process_unread_alerts() -> int:
    gmail_user = os.environ["GMAIL_SENDER"]
    gmail_password = os.environ["GMAIL_PASSWORD"]

    processed = 0
    failures: list[str] = []
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
            msg_label = msg_id.decode(errors="replace")
            try:
                # RFC822 può impostare \\Seen in IMAP. BODY.PEEK[] mantiene invece
                # la mail UNSEEN finché WhatsApp non è stato accettato dal provider.
                raw_email = _fetch_without_marking_seen(mail, msg_id)
                msg = email.message_from_bytes(raw_email)
                subject = _decode_subject(msg)
                if FINECO_SUBJECT.lower() not in subject.lower():
                    print(f"SKIP {msg_label}: oggetto non Fineco ({subject})")
                    continue

                text = _extract_text(msg)
                alert = parse_fineco_alert(text)
                if not alert:
                    print(f"PARSE_ERROR {msg_label}: formato Fineco non riconosciuto; mail lasciata UNSEEN")
                    failures.append(f"{msg_label}:PARSE_ERROR")
                    continue

                print(f"FINECO_MAIL_FOUND {alert.titolo} {alert.mercato} {alert.prezzo}")

                # TradingView viene interrogato SOLO quando esiste un nuovo alert Fineco valido.
                tv = None
                try:
                    print(f"TRADINGVIEW_LOOKUP {alert.titolo} | {alert.mercato}")
                    tv = fetch_tradingview_data(alert)
                    if tv is None:
                        print("TRADINGVIEW_ND: invio comunque alert Fineco")
                    else:
                        print(
                            f"TRADINGVIEW_OK prezzo={tv.prezzo_attuale} "
                            f"1H={tv.segnale_1h} 4H={tv.segnale_4h} 1D={tv.segnale_1d}"
                        )
                except Exception as exc:
                    print(f"TRADINGVIEW_ERROR {type(exc).__name__}: {exc}")

                # Il checkpoint Gmail viene committato SOLO dopo che CallMeBot
                # ha esplicitamente accettato il messaggio.
                print(f"WHATSAPP_REQUEST_SENT {alert.titolo}")
                provider_status = send_callmebot(format_whatsapp(alert, tv))
                print(f"WHATSAPP_CONFIRMED {alert.titolo} status={provider_status}")

                _mark_seen(mail, msg_id)
                print(f"MAIL_MARKED_SEEN {alert.titolo}")
                processed += 1
                print(f"DONE {alert.titolo} {alert.mercato} {alert.prezzo}")
            except Exception as exc:
                # BODY.PEEK[] ensures that failed messages remain UNSEEN and are
                # automatically eligible for the next scheduled retry.
                print(f"ALERT_FAILED msg_id={msg_label} reason={type(exc).__name__}: {exc}")
                print(f"MAIL_LEFT_UNREAD msg_id={msg_label}")
                failures.append(f"{msg_label}:{type(exc).__name__}")

        if failures:
            raise RuntimeError(
                f"Fineco bridge completato con {len(failures)} alert falliti; "
                "le mail restano UNSEEN per il retry successivo"
            )
    finally:
        try:
            mail.logout()
        except Exception:
            pass

    return processed


if __name__ == "__main__":
    count = process_unread_alerts()
    print(f"Fineco alerts confermati: {count}")
