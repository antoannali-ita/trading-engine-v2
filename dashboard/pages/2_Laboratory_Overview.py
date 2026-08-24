from pathlib import Path
import os
import runpy

# TEMPORARY: autenticazione dashboard sospesa.
os.environ["DASHBOARD_PASSWORD"] = ""
runpy.run_path(str(Path(__file__).resolve().parents[2] / "pages" / "2_Laboratory_Overview.py"), run_name="__main__")
