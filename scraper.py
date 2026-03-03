"""
scraper.py
----------
Fetches stock prices from yfinance and economic indicators from FRED API,
then saves them to the SQLite database via database.py.

Functions:
    validate_ticker(ticker) -> bool: Check if a ticker exists on yfinance
    fetch_stock_prices(ticker, period) -> bool: Fetch OHLCV data and save to DB
    fetch_watchlist_prices() -> None: Fetch prices for all watchlist tickers
    fetch_fred_series(series_id, name, unit) -> bool: Fetch one FRED series and save to DB
    fetch_all_indicators() -> None: Fetch all configured FRED indicators
"""
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests
import yfinance as yf
from dotenv import load_dotenv

import database

# ── Constants ────────────────────────────────────────
load_dotenv()
DB_PATH = Path(os.getenv("DB_PATH", "data/econowatch.db"))
FRED_API_KEY = os.getenv("FRED_API_KEY", "")
FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

DEFAULT_TICKERS = [
    ("AAPL",    "Apple"),
    ("MSFT",    "Microsoft"),
    ("GOOGL",   "Alphabet"),
    ("TSLA",    "Tesla"),
    ("AMZN",    "Amazon"),
    ("^GSPC",   "S&P 500"),
    ("^DJI",    "Dow Jones"),
    ("GLD",     "Gold ETF"),
    ("BTC-USD", "Bitcoin"),
]

FRED_SERIES = [
    ("CPIAUCSL", "CPI Inflation",      "% YoY"),
    ("UNRATE",   "Unemployment Rate",  "%"),
    ("FEDFUNDS", "Fed Funds Rate",     "%"),
    ("DGS10",    "10-Year Treasury",   "%"),
    ("GDPC1",    "Real GDP Growth",    "Billions USD"),
]

# Simple in-memory cache: ticker -> (is_valid, timestamp)
_ticker_cache: dict = {}
CACHE_TTL_SECONDS = 3600  # 1 hour

logger = logging.getLogger(__name__)


def validate_ticker(ticker: str) -> bool:
    """
    Check whether a ticker symbol exists on yfinance.

    Uses a 1-hour in-memory cache to avoid repeated API calls for the same ticker.

    Args:
        ticker: The stock ticker symbol to validate (e.g. "AAPL").

    Returns:
        True if ticker is valid, False otherwise.
    """
    now = datetime.now()
    if ticker in _ticker_cache:
        is_valid, cached_at = _ticker_cache[ticker]
        if (now - cached_at).seconds < CACHE_TTL_SECONDS:
            return is_valid

    try:
        t = yf.Ticker(ticker)
        df = t.history(period="5d")
        is_valid = not df.empty
        _ticker_cache[ticker] = (is_valid, now)
        return is_valid
    except Exception as e:
        logger.error("Error validating ticker %s: %s", ticker, e)
        _ticker_cache[ticker] = (False, now)
        return False


def fetch_stock_prices(ticker: str, period: str = "1mo") -> bool:
    """
    Fetch OHLCV stock price history from yfinance and save to the database.

    Args:
        ticker: The stock ticker symbol (e.g. "AAPL").
        period: yfinance period string. One of: 5d, 1mo, 3mo, 6mo, 1y.
                Defaults to "1mo".

    Returns:
        True if data was fetched and saved successfully, False on failure.
    """
    try:
        t = yf.Ticker(ticker)
        df = t.history(period=period)

        if df.empty:
            logger.warning("No data returned from yfinance for %s (period=%s)", ticker, period)
            return False

        df = df.reset_index()
        df.columns = [c.lower() for c in df.columns]
        df = df.rename(columns={"date": "date"})
        df["date"] = df["date"].astype(str).str[:10]
        df = df[["date", "open", "high", "low", "close", "volume"]].dropna(subset=["close"])

        success = database.insert_stock_prices(ticker, df)
        if success:
            logger.info("Fetched %d rows for %s (%s)", len(df), ticker, period)
        return success

    except Exception as e:
        logger.error("Unexpected error fetching %s: %s", ticker, e)
        return False


def fetch_watchlist_prices() -> None:
    """
    Fetch latest stock prices for every ticker in the watchlist and save to DB.

    Logs a summary of how many tickers succeeded and failed.
    """
    watchlist = database.get_watchlist()
    if not watchlist:
        logger.warning("Watchlist is empty — nothing to fetch")
        return

    success_count = 0
    fail_count = 0

    for item in watchlist:
        ticker = item["ticker"]
        ok = fetch_stock_prices(ticker, period="1mo")
        if ok:
            success_count += 1
        else:
            fail_count += 1
        time.sleep(0.5)  # rate limiting

    logger.info(
        "fetch_watchlist_prices complete — %d succeeded, %d failed",
        success_count,
        fail_count,
    )


def fetch_fred_series(series_id: str, name: str, unit: str) -> bool:
    """
    Fetch observations for one FRED data series and save to the database.

    Filters out missing values (FRED uses "." for missing data).
    Saves up to the latest 12 observations.

    Args:
        series_id: FRED series ID (e.g. "CPIAUCSL").
        name: Human-readable indicator name (e.g. "CPI Inflation").
        unit: Unit label (e.g. "%" or "Billions USD").

    Returns:
        True if data was saved successfully, False on failure.
    """
    if not FRED_API_KEY:
        logger.warning("FRED_API_KEY not set — skipping %s", series_id)
        return False

    try:
        params = {
            "series_id":  series_id,
            "api_key":    FRED_API_KEY,
            "file_type":  "json",
            "sort_order": "desc",
            "limit":      12,
        }
        response = requests.get(FRED_BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        observations = data.get("observations", [])
        valid_obs = [o for o in observations if o.get("value") != "."]

        if not valid_obs:
            logger.warning("No valid observations for FRED series %s", series_id)
            return False

        saved = 0
        for obs in valid_obs:
            ok = database.insert_indicator(
                series_id=series_id,
                name=name,
                date=obs["date"],
                value=float(obs["value"]),
                unit=unit,
            )
            if ok:
                saved += 1

        logger.info("Saved %d observations for %s (%s)", saved, name, series_id)
        return True

    except requests.HTTPError as e:
        logger.error("HTTP error fetching FRED series %s: %s", series_id, e)
        return False
    except Exception as e:
        logger.error("Unexpected error fetching FRED series %s: %s", series_id, e)
        return False


def fetch_all_indicators() -> None:
    """
    Fetch all configured FRED economic indicator series and save to the database.

    Loops through FRED_SERIES constant and calls fetch_fred_series() for each.
    Logs a summary of results.
    """
    success_count = 0
    fail_count = 0

    for series_id, name, unit in FRED_SERIES:
        ok = fetch_fred_series(series_id, name, unit)
        if ok:
            success_count += 1
        else:
            fail_count += 1
        time.sleep(0.3)  # avoid rate limiting

    logger.info(
        "fetch_all_indicators complete — %d succeeded, %d failed",
        success_count,
        fail_count,
    )


def _seed_watchlist() -> None:
    """Seed the watchlist with default tickers if it is empty."""
    existing = database.get_watchlist()
    if existing:
        logger.info("Watchlist already has %d tickers — skipping seed", len(existing))
        return

    for ticker, name in DEFAULT_TICKERS:
        database.add_to_watchlist(ticker, name)
    logger.info("Seeded watchlist with %d default tickers", len(DEFAULT_TICKERS))


if __name__ == "__main__":
    logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)

    logger.info("=== EconoWatch Scraper — Standalone Run ===")

    # 1. Ensure DB tables exist
    database.init_db()

    # 2. Seed watchlist with defaults
    _seed_watchlist()

    # 3. Fetch stock prices for all watchlist tickers
    logger.info("--- Fetching stock prices ---")
    fetch_watchlist_prices()

    # 4. Fetch economic indicators from FRED
    logger.info("--- Fetching economic indicators ---")
    fetch_all_indicators()

    logger.info("=== Scraper run complete ===")
