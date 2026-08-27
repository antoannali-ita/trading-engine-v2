from __future__ import annotations

# Accesso completo alla dashboard storica. Viene mantenuto come ultima voce del menu
# durante la migrazione progressiva delle funzioni più utili verso pagine dedicate.
try:
    from dashboard.ui_v7 import *  # noqa: F401,F403
except ModuleNotFoundError:
    from ui_v7 import *  # type: ignore  # noqa: F401,F403
