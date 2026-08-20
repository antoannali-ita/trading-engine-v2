from datetime import datetime, timezone
import sys
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent
SRC = LAB_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lab.db import get_supabase_client


supabase = get_supabase_client()

run_id = f"TEST_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

data = {
    "run_id": run_id,
    "market": "USA",
    "horizon": "TEST",
    "engine_version": "2.0-test",
    "config_version": "2.0-initial",
    "universe_size": 1,
    "candidates_count": 1,
    "notes": "Test connection Python -> Supabase",
}

response = supabase.table("engine_runs").insert(data).execute()
print(response.data)
