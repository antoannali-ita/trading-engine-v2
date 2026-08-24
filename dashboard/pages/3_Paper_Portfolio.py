from pathlib import Path
import runpy

runpy.run_path(str(Path(__file__).resolve().parents[2] / "pages" / "3_Paper_Portfolio.py"), run_name="__main__")
