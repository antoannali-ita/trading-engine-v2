from pathlib import Path
import os
import runpy
import sys

# TEMPORARY: autenticazione dashboard sospesa.
os.environ["DASHBOARD_PASSWORD"] = ""

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Wrapper Streamlit: espone LAB-FEAT-001 nel menu della dashboard principale.
runpy.run_path(str(ROOT / "pages" / "2_Feature_Enrichment.py"), run_name="__main__")
