"""
tests/test_scraper.py
---------------------
Unit tests for scraper.py — covers validate_ticker() caching behaviour,
get_ticker_name() fallback chain, get_ticker_news() limit and field mapping,
and fetch_stock_prices() success/failure paths.

All yfinance and requests calls are mocked so no network access is needed.
"""
import sys
import os
from unittest.mock import patch, MagicMock, call
from datetime import datetime

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import scraper


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_df(n: int = 5) -> pd.DataFrame:
    """Return a minimal yfinance-style OHLCV DataFrame (index named 'Date' like yfinance)."""
    dates = pd.date_range("2024-01-01", periods=n, freq="B", name="Date")
    return pd.DataFrame({
        "Open":   [150.0 + i for i in range(n)],
        "High":   [152.0 + i for i in range(n)],
        "Low":    [148.0 + i for i in range(n)],
        "Close":  [151.0 + i for i in range(n)],
        "Volume": [1_000_000] * n,
    }, index=dates)


# ── validate_ticker ───────────────────────────────────────────────────────────

class TestValidateTicker:
    def setup_method(self):
        scraper._ticker_cache.clear()

    def test_returns_true_for_valid_ticker(self):
        with patch("scraper._yfinance_history", return_value=_make_df()):
            assert scraper.validate_ticker("AAPL") is True

    def test_returns_false_for_empty_dataframe(self):
        with patch("scraper._yfinance_history", return_value=pd.DataFrame()):
            assert scraper.validate_ticker("FAKEXYZ") is False

    def test_result_is_cached(self):
        with patch("scraper.yf.Ticker") as mock_cls:
            mock_inst = MagicMock()
            mock_inst.history.return_value = _make_df()
            mock_cls.return_value = mock_inst

            scraper.validate_ticker("AAPL")
            scraper.validate_ticker("AAPL")   # second call hits cache

            # yf.Ticker().history() should only have been called once
            assert mock_inst.history.call_count == 1

    def test_exception_returns_false_and_caches_false(self):
        with patch("scraper.yf.Ticker", side_effect=Exception("network error")):
            result = scraper.validate_ticker("ERR")
        assert result is False
        assert scraper._ticker_cache.get("ERR", (True,))[0] is False

    def test_different_tickers_cached_independently(self):
        df_real  = _make_df()
        df_empty = pd.DataFrame()

        def side_effect(ticker, period):
            return df_real if ticker == "AAPL" else df_empty

        with patch("scraper._yfinance_history", side_effect=side_effect):
            assert scraper.validate_ticker("AAPL")    is True
            assert scraper.validate_ticker("FAKEXYZ") is False


# ── get_ticker_name ───────────────────────────────────────────────────────────

class TestGetTickerName:
    def _mock_ticker(self, info: dict):
        mock_inst = MagicMock()
        mock_inst.info = info
        mock_cls = MagicMock(return_value=mock_inst)
        return mock_cls

    def test_returns_short_name(self):
        with patch("scraper.yf.Ticker", self._mock_ticker({"shortName": "Apple Inc.", "longName": "Apple Inc. Long"})):
            assert scraper.get_ticker_name("AAPL") == "Apple Inc."

    def test_falls_back_to_long_name(self):
        with patch("scraper.yf.Ticker", self._mock_ticker({"shortName": None, "longName": "Long Name Corp"})):
            assert scraper.get_ticker_name("XYZ") == "Long Name Corp"

    def test_falls_back_to_ticker_when_no_name(self):
        with patch("scraper.yf.Ticker", self._mock_ticker({})):
            assert scraper.get_ticker_name("XYZ") == "XYZ"

    def test_falls_back_to_ticker_on_exception(self):
        with patch("scraper.yf.Ticker", side_effect=Exception("boom")):
            assert scraper.get_ticker_name("AAPL") == "AAPL"


# ── get_ticker_news ───────────────────────────────────────────────────────────

class TestGetTickerNews:
    def _mock_news(self, items):
        mock_inst = MagicMock()
        mock_inst.news = items
        return MagicMock(return_value=mock_inst)

    def test_returns_correct_fields(self):
        items = [{"title": "Test", "publisher": "Reuters",
                  "link": "http://x.com", "providerPublishTime": 12345}]
        with patch("scraper.yf.Ticker", self._mock_news(items)):
            result = scraper.get_ticker_news("AAPL", limit=5)
        assert len(result) == 1
        assert result[0] == {"title": "Test", "publisher": "Reuters",
                              "link": "http://x.com", "published_at": 12345}

    def test_respects_limit(self):
        items = [{"title": f"N{i}", "publisher": "X",
                  "link": f"http://x/{i}", "providerPublishTime": i}
                 for i in range(10)]
        with patch("scraper.yf.Ticker", self._mock_news(items)):
            result = scraper.get_ticker_news("AAPL", limit=3)
        assert len(result) == 3

    def test_returns_empty_list_on_none_news(self):
        with patch("scraper.yf.Ticker", self._mock_news(None)):
            result = scraper.get_ticker_news("AAPL")
        assert result == []

    def test_returns_empty_list_on_exception(self):
        with patch("scraper.yf.Ticker", side_effect=Exception("boom")):
            result = scraper.get_ticker_news("AAPL")
        assert result == []

    def test_missing_fields_default_to_empty(self):
        items = [{}]   # item with no keys at all
        with patch("scraper.yf.Ticker", self._mock_news(items)):
            result = scraper.get_ticker_news("AAPL")
        assert result[0]["title"]        == ""
        assert result[0]["publisher"]    == ""
        assert result[0]["link"]         == ""
        assert result[0]["published_at"] == 0


# ── fetch_stock_prices ────────────────────────────────────────────────────────

class TestFetchStockPrices:
    def test_returns_true_on_success(self):
        df = _make_df(30)
        with patch("scraper._yfinance_history", return_value=df), \
             patch("scraper.database.insert_stock_prices", return_value=True):
            assert scraper.fetch_stock_prices("AAPL", "1mo") is True

    def test_returns_false_when_df_is_empty(self):
        with patch("scraper._yfinance_history", return_value=pd.DataFrame()):
            assert scraper.fetch_stock_prices("AAPL", "1mo") is False

    def test_returns_false_on_db_failure(self):
        df = _make_df(30)
        with patch("scraper._yfinance_history", return_value=df), \
             patch("scraper.database.insert_stock_prices", return_value=False):
            assert scraper.fetch_stock_prices("AAPL", "1mo") is False

    def test_returns_false_on_exception(self):
        with patch("scraper._yfinance_history", side_effect=Exception("network error")):
            assert scraper.fetch_stock_prices("AAPL", "1mo") is False

    def test_passes_ticker_and_df_to_insert(self):
        df = _make_df(5)
        with patch("scraper._yfinance_history", return_value=df), \
             patch("scraper.database.insert_stock_prices", return_value=True) as mock_insert:
            scraper.fetch_stock_prices("NVDA", "5d")
        mock_insert.assert_called_once()
        args = mock_insert.call_args
        assert args[0][0] == "NVDA"           # ticker arg
        assert "close" in args[0][1].columns  # DataFrame has close column
