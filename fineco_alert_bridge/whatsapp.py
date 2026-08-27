import os
from urllib.parse import quote
from urllib.request import urlopen


def send_callmebot(message: str) -> None:
    phone = os.environ["WHATSAPP_NUMBER"]
    apikey = os.environ["CALLMEBOT_APIKEY"]
    url = (
        "https://api.callmebot.com/whatsapp.php"
        f"?phone={quote(phone)}&text={quote(message)}&apikey={quote(apikey)}"
    )
    with urlopen(url, timeout=30) as response:
        body = response.read().decode("utf-8", errors="replace")
        if response.status >= 400:
            raise RuntimeError(f"CallMeBot HTTP {response.status}: {body[:200]}")
