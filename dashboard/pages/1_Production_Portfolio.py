from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

runpy.run_path(str(ROOT / "pages" / "1_Portafoglio_Reale.py"), run_name="__main__")
