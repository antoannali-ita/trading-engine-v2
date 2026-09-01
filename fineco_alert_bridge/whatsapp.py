from __future__ import annotations

import os
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import urlopen


class CallMeBotRejected(RuntimeError):
    """The provider answered, but explicitly rejected the WhatsApp message."""


_POSITIVE_MARKERS = (
    "message queued",
    "message sent",
    "sent successfully",
    "successfully queued",
    "message received",
    "api message received",
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
    """Validate CallMeBot without rejecting legitimate 2xx responses.

    CallMeBot's own examples treat a successful HTTP status as acceptance and the
    provider has changed response wording over time.  We therefore reject explicit
    provider errors, accept known success markers, and otherwise accept any non-error
    2xx response instead of creating false negatives that leave alerts stuck forever.
    """
    if status >= 400:
        raise CallMeBotRejected(f"CallMeBot HTTP {status}")

    normalized = " ".join((body or "").lower().split())
    if any(marker in normalized for marker in _NEGATIVE_MARKERS):
        raise CallMeBotRejected("CallMeBot ha risposto ma ha rifiutato il messaggio")

    if any(marker in normalized for marker in _POSITIVE_MARKERS):
        return "PROVIDER_ACCEPTED"

    # Provider response text is not a stable API contract.  For HTTP 2xx with no
    # explicit rejection, regard the request as accepted.  This matches CallMeBot's
    # documented PHP examples, which use the HTTP status as the success signal.
    if 200 <= status < 300:
        return "PROVIDER_ACCEPTED_2XX"

    raise CallMeBotRejected(f"CallMeBot HTTP inatteso {status}")


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
    """Send one WhatsApp alert and return after provider acceptance.

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
