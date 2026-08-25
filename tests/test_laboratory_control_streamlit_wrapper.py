from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "dashboard" / "pages" / "2_Laboratory_Control.py"


def test_laboratory_control_wrapper_adds_repo_root_to_sys_path():
    source = WRAPPER.read_text(encoding="utf-8")
    assert "sys.path.insert(0, str(ROOT))" in source
    assert "runpy.run_path" in source
    assert 'ROOT / "pages" / "2_Laboratory_Control.py"' in source
