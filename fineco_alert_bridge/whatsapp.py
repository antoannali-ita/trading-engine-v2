from __future__ import annotations

import os
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import urlopen


class CallMeBotRejected(RuntimeError):
    """The provider answered, but did not accept the WhatsApp message."""


_POSITIVE_MARKERS = (
    "message queued",
    "message sent",
    "sent successfully",
    "successfully queued",
)

_NEGATIVE_MARKERS = (
    "error",
    "invalid",
    "not authorized",
    "not authorised",
    "not allowed",
    "not activated",
    "failed",
    "failure",
)


def _validate_provider_response(status: int, body: str) -> str:
    """Validate that CallMeBot actually accepted the request.

    CallMeBot may answer HTTP 200 even when the body contains a provider-level
    rejection.  A green HTTP status is therefore not enough.
    """
    if status >= 400:
        raise CallMeBotRejected(f"CallMeBot HTTP {status}")

    normalized = " ".join((body or "").lower().split())
    if not normalized:
        raise CallMeBotRejected("CallMeBot response body vuoto: accettazione non verificabile")

    if any(marker in normalized for marker in _NEGATIVE_MARKERS):
        raise CallMeBotRejected("CallMeBot ha risposto ma ha rifiutato il messaggio")

    if not any(marker in normalized for marker in _POSITIVE_MARKERS):
        raise CallMeBotRejected("Risposta CallMeBot non riconosciuta: accettazione non verificabile")

    return "PROVIDER_ACCEPTED"


def _send_once(message: str) -> str:
    phone = os.environ["WHATSAPP_NUMBER"]
    apikey = os.environ["CALLMEBOT_APIKEY"]
    url = (
        "https://api.callmebot.com/whatsapp.php"
        f"?phone={quote(phone)}&text={quote(message)}&apikey={quote(apikey)}"
    )

    with urlopen(url, timeout=30) as response:
        body = response.read().decode("utf-8", errors="replace")
        return _validate_provider_response(response.status, body)


def send_callmebot(message: str, *, attempts: int = 3, retry_delay_seconds: float = 5.0) -> str:
    """Send one WhatsApp alert and return only after provider acceptance.

    Network/transport failures are retried. Explicit provider rejection is not
    retried because invalid credentials/authorization do not improve by waiting.
    Secrets and the provider response body are intentionally not logged here.
    """
    attempts = max(1, int(attempts))
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            return _send_once(message)
        except CallMeBotRejected:
            raise
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt >= attempts:
                break
            print(f"WHATSAPP_RETRY attempt={attempt}/{attempts} reason={type(exc).__name__}")
            time.sleep(max(0.0, retry_delay_seconds))

    raise RuntimeError(
        f"CallMeBot transport failure dopo {attempts} tentativi: {type(last_error).__name__ if last_error else 'unknown'}"
    ) from last_error
