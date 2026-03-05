"""
analysis.py
-----------
Technical analysis engine for EconoWatch. Computes RSI, SMA crossovers, MACD,
Bollinger Bands, ATR, and generates buy/sell/hold signals with price targets.

Functions:
    compute_rsi(closes, period) -> float: Compute RSI indicator
    compute_sma(closes, period) -> float | None: Compute simple moving average
    compute_ema(closes, period) -> list[float]: Compute EMA series
    compute_macd(closes) -> dict: Compute MACD line, signal, histogram
    compute_bollinger(closes, period) -> dict: Compute Bollinger Bands
    compute_atr(highs, lows, closes, period) -> float: Compute Average True Range
    find_levels(highs, lows, window) -> dict: Find support and resistance levels
    generate_analysis(ticker, period) -> dict | None: Full TA analysis for a ticker
"""
import logging
import math
import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

import database

# ── Constants ────────────────────────────────────────
load_dotenv()
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
MIN_DATA_POINTS = 52  # need at least 52 rows for SMA50 + buffer

PERIOD_TO_DAYS = {
    "5d":  5,
    "1mo": 30,
    "3mo": 90,
    "6mo": 180,
    "1y":  365,
}

logger = logging.getLogger(__name__)


def compute_rsi(closes: list, period: int = 14) -> float:
    """
    Compute the Relative Strength Index (RSI) for a series of closing prices.

    Args:
        closes: List of closing prices, oldest first.
        period: RSI lookback period. Defaults to 14.

    Returns:
        RSI value between 0 and 100, or 50.0 if insufficient data.
    """
    if len(closes) < period + 1:
        return 50.0

    gains = []
    losses = []
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        if delta > 0:
            gains.append(delta)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(abs(delta))

    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def compute_sma(closes: list, period: int) -> float:
    """
    Compute the Simple Moving Average for the last `period` closes.

    Args:
        closes: List of closing prices, oldest first.
        period: Number of periods to average.

    Returns:
        SMA value rounded to 2 decimal places, or None if insufficient data.
    """
    if len(closes) < period:
        return None
    return round(sum(closes[-period:]) / period, 2)


def compute_ema(closes: list, period: int) -> list:
    """
    Compute the Exponential Moving Average series for a list of closes.

    Args:
        closes: List of closing prices, oldest first.
        period: EMA lookback period.

    Returns:
        List of EMA values (length = len(closes) - period + 1), or empty list if insufficient data.
    """
    if len(closes) < period:
        return []

    k = 2 / (period + 1)
    ema_series = [sum(closes[:period]) / period]  # seed with first SMA
    for price in closes[period:]:
        ema_series.append(price * k + ema_series[-1] * (1 - k))
    return ema_series


def compute_macd(closes: list) -> dict:
    """
    Compute MACD line, signal line, histogram, and trend direction.

    Uses standard 12/26/9 EMA parameters.

    Args:
        closes: List of closing prices, oldest first.

    Returns:
        Dict with keys: macd, signal_line, histogram, trend.
        Returns neutral dict if insufficient data.
    """
    neutral = {"macd": 0.0, "signal_line": 0.0, "histogram": 0.0, "trend": "neutral"}

    ema12 = compute_ema(closes, 12)
    ema26 = compute_ema(closes, 26)

    if not ema12 or not ema26:
        return neutral

    # ema12 has len(closes)-11 values, ema26 has len(closes)-25 values
    # align by taking the tail of ema12 that matches ema26 length
    offset = len(ema12) - len(ema26)
    if offset < 0:
        return neutral

    macd_line = [ema12[offset + i] - ema26[i] for i in range(len(ema26))]

    signal_ema = compute_ema(macd_line, 9)
    if not signal_ema:
        return neutral

    macd_val = round(macd_line[-1], 4)
    signal_val = round(signal_ema[-1], 4)
    histogram = round(macd_val - signal_val, 4)
    trend = "bullish" if histogram > 0 else ("bearish" if histogram < 0 else "neutral")

    return {
        "macd":        macd_val,
        "signal_line": signal_val,
        "histogram":   histogram,
        "trend":       trend,
    }


def compute_bollinger(closes: list, period: int = 20) -> dict:
    """
    Compute Bollinger Bands for a series of closing prices.

    Args:
        closes: List of closing prices, oldest first.
        period: Lookback period for the middle band SMA. Defaults to 20.

    Returns:
        Dict with keys: upper, middle, lower, pct_b, position.
        Returns neutral dict if insufficient data.
    """
    neutral = {"upper": 0.0, "middle": 0.0, "lower": 0.0, "pct_b": 0.5, "position": "middle"}

    if len(closes) < period:
        return neutral

    window = closes[-period:]
    middle = sum(window) / period
    variance = sum((x - middle) ** 2 for x in window) / period
    std = math.sqrt(variance)

    upper = round(middle + 2 * std, 2)
    lower = round(middle - 2 * std, 2)
    middle = round(middle, 2)

    current = closes[-1]
    band_range = upper - lower
    pct_b = round((current - lower) / band_range, 4) if band_range > 0 else 0.5

    if pct_b > 0.8:
        position = "upper_extreme"
    elif pct_b > 0.6:
        position = "upper_third"
    elif pct_b < 0.2:
        position = "lower_extreme"
    elif pct_b < 0.4:
        position = "lower_third"
    else:
        position = "middle"

    return {
        "upper":    upper,
        "middle":   middle,
        "lower":    lower,
        "pct_b":    pct_b,
        "position": position,
    }


def compute_atr(highs: list, lows: list, closes: list, period: int = 14) -> float:
    """
    Compute the Average True Range (ATR).

    Args:
        highs: List of daily high prices, oldest first.
        lows: List of daily low prices, oldest first.
        closes: List of daily close prices, oldest first.
        period: ATR lookback period. Defaults to 14.

    Returns:
        ATR value rounded to 4 decimal places, or 0.0 if insufficient data.
    """
    if len(closes) < period + 1:
        return 0.0

    true_ranges = []
    for i in range(1, len(closes)):
        high_low   = highs[i] - lows[i]
        high_prev  = abs(highs[i] - closes[i - 1])
        low_prev   = abs(lows[i]  - closes[i - 1])
        true_ranges.append(max(high_low, high_prev, low_prev))

    atr = sum(true_ranges[-period:]) / period
    return round(atr, 4)


def find_levels(highs: list, lows: list, window: int = 60) -> dict:
    """
    Find support (rolling low) and resistance (rolling high) levels.

    Args:
        highs: List of daily high prices, oldest first.
        lows: List of daily low prices, oldest first.
        window: Number of recent days to consider. Defaults to 60.

    Returns:
        Dict with keys: support, resistance.
    """
    recent_highs = highs[-window:] if len(highs) >= window else highs
    recent_lows  = lows[-window:]  if len(lows)  >= window else lows

    return {
        "support":    round(min(recent_lows),  2),
        "resistance": round(max(recent_highs), 2),
    }


def _volume_vote(volumes: list, closes: list) -> tuple:
    """
    Compute a vote for volume trend by comparing 5-day vs 10-day average volume.

    Args:
        volumes: List of volume values, oldest first.
        closes: List of closing prices, oldest first.

    Returns:
        Tuple of (vote: int, trend_label: str).
    """
    if len(volumes) < 10 or len(closes) < 2:
        return 0, "neutral"

    avg5  = sum(volumes[-5:])  / 5
    avg10 = sum(volumes[-10:]) / 10
    rising = avg5 > avg10

    price_up = closes[-1] > closes[-5] if len(closes) >= 5 else closes[-1] > closes[-2]

    if rising and price_up:
        return 1, "rising"
    if rising and not price_up:
        return -1, "rising"
    return 0, "flat"


def _build_summary(
    ticker: str,
    signal: str,
    rsi: float,
    macd_data: dict,
    boll_data: dict,
    sma20,
    sma50,
    price: float,
) -> str:
    """
    Generate a plain-English summary string for the analysis result.

    Args:
        ticker: The ticker symbol.
        signal: "BUY", "SELL", or "HOLD".
        rsi: RSI value.
        macd_data: Dict from compute_macd().
        boll_data: Dict from compute_bollinger().
        sma20: 20-day SMA value or None.
        sma50: 50-day SMA value or None.
        price: Current close price.

    Returns:
        Single summary string.
    """
    parts = [f"{ticker} is currently trading at ${price:.2f}."]

    if rsi < 35:
        parts.append(f"RSI at {rsi:.1f} suggests the asset may be oversold.")
    elif rsi > 65:
        parts.append(f"RSI at {rsi:.1f} suggests the asset may be overbought.")
    else:
        parts.append(f"RSI at {rsi:.1f} is in neutral territory.")

    if sma20 is not None and sma50 is not None:
        if sma20 > sma50:
            parts.append(
                f"SMA20 (${sma20:.2f}) is above SMA50 (${sma50:.2f}), indicating a bullish trend."
            )
        else:
            parts.append(
                f"SMA20 (${sma20:.2f}) is below SMA50 (${sma50:.2f}), indicating a bearish trend."
            )

    hist_sign = "+" if macd_data["histogram"] >= 0 else ""
    parts.append(
        f"MACD histogram is {macd_data['trend']} ({hist_sign}{macd_data['histogram']:.3f})."
    )

    pos_map = {
        "upper_extreme": "near the upper Bollinger Band extreme",
        "upper_third":   "in the upper third of the Bollinger Band",
        "lower_extreme": "near the lower Bollinger Band extreme",
        "lower_third":   "near the lower Bollinger Band",
        "middle":        "in the middle of the Bollinger Band",
    }
    parts.append(f"Price is {pos_map.get(boll_data['position'], 'within Bollinger Bands')}.")

    verdict_map = {
        "BUY":  "Overall technical indicators lean bullish.",
        "SELL": "Overall technical indicators lean bearish.",
        "HOLD": "Mixed signals suggest caution — no clear directional edge.",
    }
    parts.append(verdict_map[signal])

    return " ".join(parts)


def generate_analysis(ticker: str, period: str = "3mo") -> dict:
    """
    Generate a full technical analysis for a ticker using data from the database.

    Computes RSI, SMA crossovers, MACD, Bollinger Bands, ATR, support/resistance,
    and produces a buy/sell/hold signal with confidence and price targets.

    Args:
        ticker: The stock ticker symbol (e.g. "AAPL").
        period: yfinance period string used to determine fetch window.
                One of: 5d, 1mo, 3mo, 6mo, 1y. Defaults to "3mo".

    Returns:
        Dict with full analysis result, or None if insufficient data.
    """
    # Always fetch at least 90 days for reliable indicator computation
    days = max(PERIOD_TO_DAYS.get(period, 90), 90)
    rows = database.get_stock_history(ticker, days)

    if len(rows) < MIN_DATA_POINTS:
        logger.warning(
            "Insufficient data for %s: got %d rows, need %d",
            ticker, len(rows), MIN_DATA_POINTS,
        )
        return None

    closes  = [r["close"]  for r in rows if r["close"]  is not None]
    highs   = [r["high"]   for r in rows if r["high"]   is not None]
    lows    = [r["low"]    for r in rows if r["low"]    is not None]
    volumes = [r["volume"] for r in rows if r["volume"] is not None]

    if len(closes) < MIN_DATA_POINTS:
        return None

    price = closes[-1]

    # ── Compute indicators ────────────────────────────
    rsi       = compute_rsi(closes)
    sma20     = compute_sma(closes, 20)
    sma50     = compute_sma(closes, 50)
    macd_data = compute_macd(closes)
    boll_data = compute_bollinger(closes)
    atr       = compute_atr(highs, lows, closes)
    levels    = find_levels(highs, lows)
    vol_vote, vol_trend = _volume_vote(volumes, closes)

    # ── Score each indicator (-1, 0, +1) ─────────────
    rsi_vote = 1 if rsi < 40 else (-1 if rsi > 60 else 0)

    sma_vote  = 0
    sma_cross = "neutral"
    if sma20 is not None and sma50 is not None:
        if sma20 > sma50:
            sma_vote, sma_cross = 1, "bullish"
        elif sma20 < sma50:
            sma_vote, sma_cross = -1, "bearish"

    price_vs_sma20_vote = 0
    if sma20 is not None:
        price_vs_sma20_vote = 1 if price > sma20 else -1

    macd_vote = 1 if macd_data["histogram"] > 0 else (-1 if macd_data["histogram"] < 0 else 0)
    boll_vote = 1 if boll_data["pct_b"] < 0.3 else (-1 if boll_data["pct_b"] > 0.7 else 0)

    score     = rsi_vote + sma_vote + price_vs_sma20_vote + macd_vote + boll_vote + vol_vote
    max_score = 6

    # ── Determine signal ──────────────────────────────
    if score >= 3:
        signal = "BUY"
    elif score <= -3:
        signal = "SELL"
    else:
        signal = "HOLD"

    confidence = min(95, max(40, round(abs(score) / max_score * 100)))

    # ── Price targets ─────────────────────────────────
    resistance   = levels["resistance"]
    support      = levels["support"]
    atr_cushion  = 2 * atr if atr > 0 else price * 0.05

    if signal in ("BUY", "HOLD"):
        target_price = resistance
        stop_loss    = round(price - atr_cushion, 2)
    else:
        target_price = support
        stop_loss    = round(price + atr_cushion, 2)

    risk_reward = None
    denominator = abs(price - stop_loss)
    if denominator > 0:
        risk_reward = round(abs(target_price - price) / denominator, 2)

    summary = _build_summary(ticker, signal, rsi, macd_data, boll_data, sma20, sma50, price)

    return {
        "ticker":       ticker,
        "signal":       signal,
        "confidence":   confidence,
        "price":        round(price, 2),
        "target_price": round(target_price, 2),
        "stop_loss":    round(stop_loss, 2),
        "risk_reward":  risk_reward,
        "indicators": {
            "rsi": {
                "value": rsi,
                "zone":  "oversold" if rsi < 30 else ("overbought" if rsi > 70 else "neutral"),
                "vote":  rsi_vote,
            },
            "sma": {
                "sma20":  sma20,
                "sma50":  sma50,
                "cross":  sma_cross,
                "vote":   sma_vote,
            },
            "macd": {
                "value":       macd_data["macd"],
                "signal_line": macd_data["signal_line"],
                "histogram":   macd_data["histogram"],
                "trend":       macd_data["trend"],
                "vote":        macd_vote,
            },
            "bollinger": {
                "upper":    boll_data["upper"],
                "middle":   boll_data["middle"],
                "lower":    boll_data["lower"],
                "pct_b":    boll_data["pct_b"],
                "position": boll_data["position"],
                "vote":     boll_vote,
            },
            "volume": {
                "trend": vol_trend,
                "vote":  vol_vote,
            },
        },
        "summary":      summary,
        "period_used":  period,
        "data_points":  len(closes),
        "last_updated": date.today().isoformat(),
    }


if __name__ == "__main__":
    import json
    logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)
    database.init_db()
    result = generate_analysis("AAPL", "3mo")
    if result:
        logger.info("Analysis result:\n%s", json.dumps(result, indent=2))
    else:
        logger.warning("No analysis result — not enough data in DB for AAPL")
