from pathlib import Path
import runpy

runpy.run_path(str(Path(__file__).resolve().parents[2] / "pages" / "1_Portafoglio_Reale.py"), run_name="__main__")
