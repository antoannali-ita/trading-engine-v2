from __future__ import annotations
import os, urllib.parse, urllib.request

def send_whatsapp(message: str) -> bool:
    number=os.getenv("WHATSAPP_NUMBER","").strip(); key=os.getenv("CALLMEBOT_APIKEY","").strip()
    if not number or not key:
        print("WhatsApp disabilitato: WHATSAPP_NUMBER/CALLMEBOT_APIKEY mancanti"); return False
    params=urllib.parse.urlencode({"phone":number,"text":message,"apikey":key})
    url="https://api.callmebot.com/whatsapp.php?"+params
    try:
        with urllib.request.urlopen(url,timeout=20) as r: return 200 <= r.status < 300
    except Exception as e:
        print(f"WhatsApp error: {type(e).__name__}: {e}"); return False
