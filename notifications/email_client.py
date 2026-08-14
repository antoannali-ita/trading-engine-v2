from __future__ import annotations
import os, re, smtplib, ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def _recipients(raw): return [x.strip() for x in re.split(r"[;,]",raw or "") if x.strip()]

def send_email(subject: str, body: str, is_html: bool=True) -> bool:
    sender=os.getenv("GMAIL_SENDER","").strip(); rec=_recipients(os.getenv("GMAIL_RECIPIENT","")); pwd=os.getenv("GMAIL_PASSWORD","").strip()
    if not sender or not rec or not pwd:
        print("Email non inviata: configurare GMAIL_SENDER/GMAIL_RECIPIENT/GMAIL_PASSWORD")
        return False
    msg=MIMEMultipart("alternative"); msg["Subject"]=subject; msg["From"]=sender; msg["To"]=', '.join(rec)
    msg.attach(MIMEText(body,"html" if is_html else "plain","utf-8"))
    try:
        with smtplib.SMTP(os.getenv("SMTP_HOST","smtp.gmail.com"),int(os.getenv("SMTP_PORT","587")),timeout=30) as s:
            s.ehlo(); s.starttls(context=ssl.create_default_context()); s.ehlo(); s.login(sender,pwd); s.sendmail(sender,rec,msg.as_string())
        return True
    except Exception as e:
        print(f"Email error: {type(e).__name__}: {e}"); return False
