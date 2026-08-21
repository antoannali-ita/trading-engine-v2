from __future__ import annotations

import gzip
from pathlib import Path

_payload = Path(__file__).with_name("app_v4.py.gz")
_source = gzip.open(_payload, "rt", encoding="utf-8").read()
exec(compile(_source, str(_payload), "exec"), globals(), globals())
