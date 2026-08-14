from types import SimpleNamespace
from reports.email_report import REPORT_FUNCTIONS, bind


def _dummy_reference():
    return SimpleNamespace(**{name: (lambda *a, _name=name, **k: _name) for name in REPORT_FUNCTIONS})


def test_report_binding_exposes_all_functions():
    ref = _dummy_reference()
    bound = bind(ref)
    assert set(bound) == set(REPORT_FUNCTIONS)
    for name in REPORT_FUNCTIONS:
        assert bound[name] is getattr(ref, name)


def test_report_binding_fails_loudly_if_baseline_is_incomplete():
    ref = _dummy_reference()
    delattr(ref, "generate_html")
    try:
        bind(ref)
    except AttributeError as exc:
        assert "generate_html" in str(exc)
    else:
        raise AssertionError("bind() deve fallire se manca una funzione report")
