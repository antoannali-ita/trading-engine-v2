from pathlib import Path
import os
import runpy
import sys

os.environ["DASHBOARD_PASSWORD"] = ""
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

runpy.run_path(str(ROOT / "pages" / "5_Trade_Committee.py"), run_name="__main__")
