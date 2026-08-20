import os
from pathlib import Path

from dotenv import load_dotenv
from supabase import Client, create_client


def _load_environment() -> None:
    """Load laboratory/.env when running locally without overriding existing env vars."""
    lab_root = Path(__file__).resolve().parents[2]
    load_dotenv(lab_root / ".env", override=False)


def get_supabase_client() -> Client:
    _load_environment()

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SECRET_KEY")

    if not url or not key:
        raise RuntimeError(
            "Missing SUPABASE_URL or SUPABASE_SECRET_KEY. "
            "Create laboratory/.env from laboratory/.env.example."
        )

    return create_client(url, key)
