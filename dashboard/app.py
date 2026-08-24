from __future__ import annotations

import os

# TEMPORARY: autenticazione dashboard sospesa su richiesta.
# Per riattivarla rimuovere questa riga e ripristinare DASHBOARD_PASSWORD.
os.environ["DASHBOARD_PASSWORD"] = ""

try:
    from dashboard.ui_v7 import *  # noqa: F401,F403
except ModuleNotFoundError:
    from ui_v7 import *  # noqa: F401,F403
