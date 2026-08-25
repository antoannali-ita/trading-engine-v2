from pathlib import Path
import os
import runpy
import sys

# TEMPORARY: autenticazione dashboard sospesa.
os.environ["DASHBOARD_PASSWORD"] = ""

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

runpy.run_path(str(ROOT / "pages" / "2_Laboratory_Control.py"), run_name="__main__")
