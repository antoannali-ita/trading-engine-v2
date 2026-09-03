import pandas as pd
import pytest

from lab import market_data as md


def _fake_ohlcv(rows: int = 5) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=rows, freq="D")
    return pd.DataFrame(
        {"Open": 1.0, "High": 1.0, "Low": 1.0, "Close": 1.0, "Volume": 100},
        index=idx,
    )


@pytest.fixture(autouse=True)
def _clear_cache():
    md.clear_cache()
    yield
    md.clear_cache()


def test_retries_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            raise md.MarketDataError("No price data returned")  # simulates a transient empty response
        return _fake_ohlcv()

    monkeypatch.setattr(md, "_download_once", lambda request: flaky())
    monkeypatch.setattr(md.time, "sleep", lambda _: None)

    result = md.download_prices(md.MarketDataRequest(symbol="AAPL", start="2024-01-01"), max_attempts=3, backoff_seconds=0.01)
    assert not result.empty
    assert calls["n"] == 3


def test_gives_up_after_max_attempts_and_raises(monkeypatch):
    calls = {"n": 0}

    def always_fails(request):
        calls["n"] += 1
        raise md.MarketDataError("boom")

    monkeypatch.setattr(md, "_download_once", always_fails)
    monkeypatch.setattr(md.time, "sleep", lambda _: None)

    with pytest.raises(md.MarketDataError):
        md.download_prices(md.MarketDataRequest(symbol="AAPL", start="2024-01-01"), max_attempts=3, backoff_seconds=0.01)
    assert calls["n"] == 3


def test_cache_avoids_second_network_call(monkeypatch):
    calls = {"n": 0}

    def counted(request):
        calls["n"] += 1
        return _fake_ohlcv()

    monkeypatch.setattr(md, "_download_once", counted)

    req = md.MarketDataRequest(symbol="MSFT", start="2024-01-01")
    first = md.download_prices(req)
    second = md.download_prices(req)

    assert calls["n"] == 1
    pd.testing.assert_frame_equal(first, second)


def test_cache_can_be_bypassed(monkeypatch):
    calls = {"n": 0}

    def counted(request):
        calls["n"] += 1
        return _fake_ohlcv()

    monkeypatch.setattr(md, "_download_once", counted)

    req = md.MarketDataRequest(symbol="MSFT", start="2024-01-01")
    md.download_prices(req)
    md.download_prices(req, use_cache=False)

    assert calls["n"] == 2


def test_different_symbols_are_cached_independently(monkeypatch):
    monkeypatch.setattr(md, "_download_once", lambda request: _fake_ohlcv())

    a = md.download_prices(md.MarketDataRequest(symbol="AAPL", start="2024-01-01"))
    b = md.download_prices(md.MarketDataRequest(symbol="MSFT", start="2024-01-01"))
    assert a is not b
