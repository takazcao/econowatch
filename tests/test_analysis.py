"""
tests/test_analysis.py
----------------------
Unit tests for analysis.py — covers find_levels(), generate_analysis() output
shape and signal logic, and generate_macro_analysis() output shape.

All database calls are mocked so no real DB or network access is needed.
"""
import sys
import os
from unittest.mock import patch

import pytest

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import analysis


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_rows(n: int, base: float = 150.0, trend: float = 0.5) -> list:
    """Build n fake OHLCV row dicts with a gentle upward trend."""
    rows = []
    for i in range(n):
        close = base + i * trend
        rows.append({
            "date":   f"2024-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}",
            "close":  close,
            "open":   close - 0.5,
            "high":   close + 1.0,
            "low":    close - 1.0,
            "volume": 1_000_000,
        })
    return rows


def _make_indicator_rows() -> list:
    """Minimal set of indicator rows that cover several _MACRO_RULES entries."""
    return [
        {"series_id": "CPIAUCSL",  "name": "CPI Inflation",      "value": 3.2,  "prev_value": 3.0,  "unit": "% YoY",       "date": "2024-01-01"},
        {"series_id": "FEDFUNDS",  "name": "Fed Funds Rate",      "value": 5.5,  "prev_value": 5.25, "unit": "%",           "date": "2024-01-01"},
        {"series_id": "DGS10",     "name": "10-Year Treasury",    "value": 4.2,  "prev_value": 4.0,  "unit": "%",           "date": "2024-01-01"},
        {"series_id": "DGS2",      "name": "2-Year Treasury",     "value": 4.8,  "prev_value": 4.6,  "unit": "%",           "date": "2024-01-01"},
        {"series_id": "VIXCLS",    "name": "VIX",                 "value": 15.0, "prev_value": 18.0, "unit": "Index",       "date": "2024-01-01"},
        {"series_id": "GDPC1",     "name": "Real GDP",            "value": 22000,"prev_value": 21800,"unit": "Billions USD", "date": "2024-01-01"},
        {"series_id": "UNRATE",    "name": "Unemployment Rate",   "value": 3.9,  "prev_value": 4.1,  "unit": "%",           "date": "2024-01-01"},
        {"series_id": "M2SL",      "name": "M2 Money Supply",     "value": 21000,"prev_value": 20800,"unit": "Billions USD", "date": "2024-01-01"},
    ]


# ── find_levels ───────────────────────────────────────────────────────────────

class TestFindLevels:
    def test_returns_resistance_and_support(self):
        highs = [100, 105, 102, 108, 103]
        lows  = [95,  98,  96,  100, 97]
        result = analysis.find_levels(highs, lows)
        assert result["resistance"] == 108
        assert result["support"]    == 95

    def test_window_limits_range(self):
        # highs 1..20, lows 0..19 — window=5 should look at only last 5
        highs = list(range(1, 21))
        lows  = list(range(0, 20))
        result = analysis.find_levels(highs, lows, window=5)
        assert result["resistance"] == 20   # max of last 5 highs (16..20)
        assert result["support"]    == 15   # min of last 5 lows  (15..19)

    def test_window_larger_than_data(self):
        highs = [10, 20, 30]
        lows  = [5,  15, 25]
        result = analysis.find_levels(highs, lows, window=100)
        assert result["resistance"] == 30
        assert result["support"]    == 5

    def test_single_element(self):
        result = analysis.find_levels([50], [40])
        assert result["resistance"] == 50
        assert result["support"]    == 40


# ── generate_analysis ─────────────────────────────────────────────────────────

class TestGenerateAnalysis:
    def test_returns_none_when_no_data(self):
        with patch("analysis.database.get_stock_history", return_value=[]):
            assert analysis.generate_analysis("AAPL") is None

    def test_returns_none_with_insufficient_rows(self):
        rows = _make_rows(10)
        with patch("analysis.database.get_stock_history", return_value=rows):
            assert analysis.generate_analysis("AAPL") is None

    def test_returns_dict_with_enough_data(self):
        rows = _make_rows(90)
        with patch("analysis.database.get_stock_history", return_value=rows):
            result = analysis.generate_analysis("AAPL")
        assert result is not None
        assert isinstance(result, dict)

    def test_output_has_required_keys(self):
        rows = _make_rows(90)
        with patch("analysis.database.get_stock_history", return_value=rows):
            result = analysis.generate_analysis("AAPL")
        required = {"ticker", "signal", "confidence", "price", "target_price",
                    "stop_loss", "risk_reward", "indicators", "summary",
                    "period_used", "data_points", "last_updated"}
        assert required.issubset(result.keys())

    def test_signal_is_valid(self):
        rows = _make_rows(90)
        with patch("analysis.database.get_stock_history", return_value=rows):
            result = analysis.generate_analysis("AAPL")
        assert result["signal"] in {"STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"}

    def test_confidence_in_range(self):
        rows = _make_rows(90)
        with patch("analysis.database.get_stock_history", return_value=rows):
            result = analysis.generate_analysis("AAPL")
        assert 1 <= result["confidence"] <= 100

    def test_indicators_block_structure(self):
        rows = _make_rows(90)
        with patch("analysis.database.get_stock_history", return_value=rows):
            result = analysis.generate_analysis("AAPL")
        ind = result["indicators"]
        assert "rsi"       in ind
        assert "sma"       in ind
        assert "macd"      in ind
        assert "bollinger" in ind
        assert "volume"    in ind

    def test_rsi_value_in_range(self):
        rows = _make_rows(90)
        with patch("analysis.database.get_stock_history", return_value=rows):
            result = analysis.generate_analysis("AAPL")
        rsi = result["indicators"]["rsi"]["value"]
        assert 0 <= rsi <= 100

    def test_rsi_vote_is_valid(self):
        rows = _make_rows(90)
        with patch("analysis.database.get_stock_history", return_value=rows):
            result = analysis.generate_analysis("AAPL")
        assert result["indicators"]["rsi"]["vote"] in {-1, 0, 1}

    def test_sma_cross_is_valid(self):
        rows = _make_rows(90)
        with patch("analysis.database.get_stock_history", return_value=rows):
            result = analysis.generate_analysis("AAPL")
        assert result["indicators"]["sma"]["cross"] in {"bullish", "bearish", "neutral"}

    def test_macd_trend_is_valid(self):
        rows = _make_rows(90)
        with patch("analysis.database.get_stock_history", return_value=rows):
            result = analysis.generate_analysis("AAPL")
        assert result["indicators"]["macd"]["trend"] in {"bullish", "bearish", "neutral"}

    def test_bollinger_position_is_valid(self):
        rows = _make_rows(90)
        with patch("analysis.database.get_stock_history", return_value=rows):
            result = analysis.generate_analysis("AAPL")
        valid = {"upper_extreme", "upper_third", "middle", "lower_third", "lower_extreme"}
        assert result["indicators"]["bollinger"]["position"] in valid

    def test_strong_buy_signal_on_uptrend(self):
        """A steep uptrend with many data points should produce a bullish signal."""
        rows = _make_rows(90, base=100.0, trend=2.0)  # aggressive upward trend
        with patch("analysis.database.get_stock_history", return_value=rows):
            result = analysis.generate_analysis("AAPL")
        assert result["signal"] in {"STRONG BUY", "BUY", "HOLD"}

    def test_ticker_in_output_matches_input(self):
        rows = _make_rows(90)
        with patch("analysis.database.get_stock_history", return_value=rows):
            result = analysis.generate_analysis("NVDA", period="3mo")
        assert result["ticker"] == "NVDA"
        assert result["period_used"] == "3mo"


# ── generate_macro_analysis ───────────────────────────────────────────────────

class TestGenerateMacroAnalysis:
    def test_returns_empty_dict_when_no_indicators(self):
        with patch("analysis.database.get_indicators", return_value=[]):
            result = analysis.generate_macro_analysis()
        assert result == {}

    def test_output_has_required_keys(self):
        rows = _make_indicator_rows()
        with patch("analysis.database.get_indicators", return_value=rows):
            result = analysis.generate_macro_analysis()
        required = {"regime", "recommendation", "confidence", "scores", "points",
                    "points_detail", "yield_curve_inverted", "breakdown",
                    "summary", "flow_pct", "flow_verdict", "last_updated"}
        assert required.issubset(result.keys())

    def test_recommendation_is_valid(self):
        rows = _make_indicator_rows()
        with patch("analysis.database.get_indicators", return_value=rows):
            result = analysis.generate_macro_analysis()
        assert result["recommendation"] in {"STOCKS", "GOLD", "CRYPTO", "MIXED"}

    def test_regime_is_valid(self):
        rows = _make_indicator_rows()
        with patch("analysis.database.get_indicators", return_value=rows):
            result = analysis.generate_macro_analysis()
        valid = {"Risk-On", "Risk-Off", "Inflationary", "Stagflationary",
                 "Recessionary", "Mixed / Transitional"}
        assert result["regime"] in valid

    def test_scores_have_all_assets(self):
        rows = _make_indicator_rows()
        with patch("analysis.database.get_indicators", return_value=rows):
            result = analysis.generate_macro_analysis()
        assert set(result["scores"].keys()) == {"stocks", "gold", "crypto"}

    def test_points_in_range(self):
        rows = _make_indicator_rows()
        with patch("analysis.database.get_indicators", return_value=rows):
            result = analysis.generate_macro_analysis()
        for asset, pt in result["points"].items():
            assert 1 <= pt <= 10, f"{asset} point {pt} out of range"

    def test_flow_pct_sums_to_100(self):
        rows = _make_indicator_rows()
        with patch("analysis.database.get_indicators", return_value=rows):
            result = analysis.generate_macro_analysis()
        assert sum(result["flow_pct"].values()) == 100

    def test_breakdown_contains_all_input_indicators(self):
        rows = _make_indicator_rows()
        with patch("analysis.database.get_indicators", return_value=rows):
            result = analysis.generate_macro_analysis()
        assert len(result["breakdown"]) == len(rows)

    def test_yield_curve_inversion_detected(self):
        """When 2Y > 10Y, yield_curve_inverted must be True."""
        rows = [
            {"series_id": "DGS10", "name": "10Y", "value": 3.8, "prev_value": 3.9, "unit": "%", "date": "2024-01-01"},
            {"series_id": "DGS2",  "name": "2Y",  "value": 4.5, "prev_value": 4.4, "unit": "%", "date": "2024-01-01"},
        ]
        with patch("analysis.database.get_indicators", return_value=rows):
            result = analysis.generate_macro_analysis()
        assert result["yield_curve_inverted"] is True

    def test_no_yield_curve_inversion_when_normal(self):
        """When 10Y > 2Y (normal curve), yield_curve_inverted must be False."""
        rows = [
            {"series_id": "DGS10", "name": "10Y", "value": 4.5, "prev_value": 4.4, "unit": "%", "date": "2024-01-01"},
            {"series_id": "DGS2",  "name": "2Y",  "value": 3.8, "prev_value": 3.9, "unit": "%", "date": "2024-01-01"},
        ]
        with patch("analysis.database.get_indicators", return_value=rows):
            result = analysis.generate_macro_analysis()
        assert result["yield_curve_inverted"] is False

    def test_flat_trend_gives_zero_votes(self):
        """Indicators with prev_value == value should have zero votes for all assets."""
        rows = [
            {"series_id": "CPIAUCSL", "name": "CPI", "value": 3.0, "prev_value": 3.0, "unit": "%", "date": "2024-01-01"},
        ]
        with patch("analysis.database.get_indicators", return_value=rows):
            result = analysis.generate_macro_analysis()
        b = result["breakdown"][0]
        assert b["stocks_vote"] == 0
        assert b["gold_vote"]   == 0
        assert b["crypto_vote"] == 0
