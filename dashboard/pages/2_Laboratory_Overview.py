from pathlib import Path
import runpy

runpy.run_path(str(Path(__file__).resolve().parents[2] / "pages" / "2_Laboratory_Overview.py"), run_name="__main__")
