from engine.market_rules import presentation_state


class FakeUsaReference:
    @staticmethod
    def display_state(candidate):
        return "PRE-BUY"


def test_italy_does_not_silently_gain_prebuy_display():
    cfg = {"market": "ITALY", "prebuy_enabled": False}
    c = {"decision": "WAIT"}
    assert presentation_state(FakeUsaReference, cfg, c) == "WAIT"


def test_usa_can_use_native_prebuy_display():
    cfg = {"market": "USA", "prebuy_enabled": True}
    c = {"decision": "WAIT"}
    assert presentation_state(FakeUsaReference, cfg, c) == "PRE-BUY"
