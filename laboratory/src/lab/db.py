import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import Client, create_client


def _enable_system_trust_store() -> None:
    """Use the operating system certificate store for local HTTPS connections.

    Corporate Windows environments often install their internal proxy/CA only in
    the Windows trust store, while Python/httpx defaults to certifi. truststore
    bridges that gap without disabling TLS verification.
    """
    if sys.platform != "win32":
        return
    try:
        import truststore

        truststore.inject_into_ssl()
    except ImportError as exc:
        raise RuntimeError(
            "Windows system trust store support is required. "
            "Run: pip install -r requirements.txt"
        ) from exc


def _load_environment() -> None:
    """Load laboratory/.env when running locally without overriding existing env vars."""
    lab_root = Path(__file__).resolve().parents[2]
    load_dotenv(lab_root / ".env", override=False)


def get_supabase_client() -> Client:
    _enable_system_trust_store()
    _load_environment()

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SECRET_KEY")

    if not url or not key:
        raise RuntimeError(
            "Missing SUPABASE_URL or SUPABASE_SECRET_KEY. "
            "Create laboratory/.env from laboratory/.env.example."
        )

    return create_client(url, key)
