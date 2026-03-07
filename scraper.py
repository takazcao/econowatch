"""
scraper.py
----------
Fetches stock prices from yfinance and economic indicators from FRED API
and CoinMarketCap API, then saves them to the SQLite database via database.py.

Functions:
    validate_ticker(ticker) -> bool: Check if a ticker exists on yfinance
    get_ticker_name(ticker) -> str: Return human-readable name for a ticker from yfinance
    get_ticker_news(ticker, limit) -> list[dict]: Fetch latest news headlines for a ticker
    fetch_stock_prices(ticker, period) -> bool: Fetch OHLCV data and save to DB
    fetch_watchlist_prices() -> None: Fetch prices for all watchlist tickers
    fetch_fred_series(series_id, name, unit) -> bool: Fetch one FRED series and save to DB
    fetch_all_indicators() -> None: Fetch all FRED + CMC indicators
    fetch_cmc_metrics() -> bool: Fetch BTC dominance + stablecoin market cap from CMC

Private helpers (internal retry wrappers):
    _yfinance_history(ticker, period) -> pd.DataFrame: yfinance call with exponential backoff
    _fred_get(params) -> dict: FRED API call with exponential backoff
"""
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests
import yfinance as yf
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, RetryError

import database

# ── Constants ────────────────────────────────────────
load_dotenv()
DB_PATH = Path(os.getenv("DB_PATH", "data/econowatch.db"))
FRED_API_KEY  = os.getenv("FRED_API_KEY", "")
FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"
CMC_API_KEY   = os.getenv("CMC_API_KEY", "")
CMC_BASE_URL  = "https://pro-api.coinmarketcap.com/v1/global-metrics/quotes/latest"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

DEFAULT_TICKERS = [
    # ── US Mega-Cap Stocks ────────────────────────────
    ("AAPL",    "Apple"),
    ("MSFT",    "Microsoft"),
    ("NVDA",    "NVIDIA"),
    ("GOOGL",   "Alphabet"),
    ("AMZN",    "Amazon"),
    ("META",    "Meta"),
    ("TSLA",    "Tesla"),
    ("NFLX",    "Netflix"),
    ("JPM",     "JPMorgan Chase"),
    ("V",       "Visa"),
    ("WMT",     "Walmart"),
    # ── Market Indices ────────────────────────────────
    ("^GSPC",   "S&P 500"),
    ("^DJI",    "Dow Jones"),
    ("^IXIC",   "NASDAQ Composite"),
    ("^RUT",    "Russell 2000"),
    # ── ETFs ─────────────────────────────────────────
    ("SPY",     "S&P 500 ETF"),
    ("QQQ",     "NASDAQ ETF"),
    ("GC=F",    "Gold XAU/USD"),
    ("SI=F",    "Silver XAG/USD"),
    ("USO",     "Oil ETF"),
    ("TLT",     "Long-Term Treasury ETF"),
    # ── Crypto ───────────────────────────────────────
    ("BTC-USD", "Bitcoin"),
    ("ETH-USD", "Ethereum"),
    ("SOL-USD", "Solana"),
    ("BNB-USD", "BNB"),
]

FRED_SERIES = [
    # ── Inflation & Prices ────────────────────────────
    ("CPIAUCSL",    "CPI Inflation",            "% YoY"),
    ("PPIACO",      "Producer Price Index",     "Index"),
    ("T10YIE",      "Breakeven Inflation 10Y",  "%"),
    ("DCOILWTICO",  "Crude Oil WTI",            "$ / Barrel"),
    # ── Employment & Growth ───────────────────────────
    ("UNRATE",      "Unemployment Rate",        "%"),
    ("GDPC1",       "Real GDP Growth",          "Billions USD"),
    # ── Interest Rates ────────────────────────────────
    ("FEDFUNDS",    "Fed Funds Rate",           "%"),
    ("DGS10",       "10-Year Treasury",         "%"),
    ("DGS2",        "2-Year Treasury",          "%"),
    ("MORTGAGE30US","30-Year Mortgage Rate",    "%"),
    # ── Money & Credit ────────────────────────────────
    ("M2SL",        "M2 Money Supply",          "Billions USD"),
    ("VIXCLS",      "VIX Volatility Index",     "Index"),
    # ── Dollar & Liquidity ────────────────────────────
    ("DTWEXBGS",    "US Dollar Index (DXY)",    "Index"),
    ("WALCL",       "Fed Balance Sheet",        "Billions USD"),
    # ── Employment & Spending ─────────────────────────
    ("PAYEMS",      "Non-Farm Payrolls",        "Thousands"),
    ("RSXFS",       "Retail Sales",             "Millions USD"),
    # ── Credit Risk ───────────────────────────────────
    ("BAMLH0A0HYM2","HY Credit Spreads",       "%"),
]

# Simple in-memory cache: ticker -> (is_valid, timestamp)
_ticker_cache: dict = {}
CACHE_TTL_SECONDS = 3600  # 1 hour

logger = logging.getLogger(__name__)


# ── Retry Helpers ─────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _yfinance_history(ticker: str, period: str):
    """Fetch yfinance price history with automatic exponential-backoff retry (max 3 attempts)."""
    return yf.Ticker(ticker).history(period=period)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _fred_get(params: dict) -> dict:
    """Call FRED API with automatic exponential-backoff retry (max 3 attempts)."""
    response = requests.get(FRED_BASE_URL, params=params, timeout=10)
    response.raise_for_status()
    return response.json()


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
        if (now - cached_at).total_seconds() < CACHE_TTL_SECONDS:
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


def get_ticker_name(ticker: str) -> str:
    """
    Return the human-readable name for a ticker from yfinance.

    Uses the shortName field from yfinance .info, falling back to longName,
    then the raw ticker symbol if neither is available.

    Args:
        ticker: The stock ticker symbol (e.g. "AAPL").

    Returns:
        Human-readable company or index name, or the ticker symbol on failure.
    """
    try:
        info = yf.Ticker(ticker).info
        return info.get("shortName") or info.get("longName") or ticker
    except Exception as e:
        logger.warning("Could not retrieve name for %s: %s", ticker, e)
        return ticker


def get_ticker_news(ticker: str, limit: int = 5) -> list:
    """
    Fetch the latest news headlines for a ticker from yfinance.

    Args:
        ticker: The stock ticker symbol (e.g. "AAPL").
        limit: Maximum number of articles to return. Defaults to 5.

    Returns:
        List of dicts with keys: title, publisher, link, published_at (unix timestamp).
        Returns empty list on failure or when no news is available.
    """
    try:
        news = yf.Ticker(ticker).news or []
        results = []
        for item in news[:limit]:
            # yfinance ≥0.2.50 wraps everything under item["content"]
            content = item.get("content") or item
            title     = content.get("title", "")
            publisher = (content.get("provider") or {}).get("displayName", "") or content.get("publisher", "")
            link      = (content.get("canonicalUrl") or {}).get("url", "") or content.get("link", "")
            pub_date  = content.get("pubDate", "") or ""
            # Convert ISO date string to unix timestamp if needed
            published_at = content.get("providerPublishTime", 0)
            if not published_at and pub_date:
                try:
                    from datetime import datetime, timezone
                    published_at = int(datetime.fromisoformat(pub_date.replace("Z", "+00:00")).timestamp())
                except Exception:
                    published_at = 0
            if title:
                results.append({
                    "title":        title,
                    "publisher":    publisher,
                    "link":         link,
                    "published_at": published_at,
                })
        return results
    except Exception as e:
        logger.warning("Could not fetch news for %s: %s", ticker, e)
        return []


def get_ticker_fundamentals(ticker: str) -> dict | None:
    """
    Fetch fundamental data for a ticker from yfinance.

    Args:
        ticker: The stock ticker symbol (e.g. "AAPL").

    Returns:
        Dict with valuation, earnings, dividend, and company info fields.
        Returns None on failure.
    """
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}

        def _pct(val):
            return round(val * 100, 2) if val is not None else None

        def _fmt(val, decimals=2):
            return round(float(val), decimals) if val is not None else None

        # Earnings date from calendar
        earnings_date = None
        try:
            cal = t.calendar or {}
            ed = cal.get("Earnings Date")
            if ed:
                earnings_date = str(ed[0]) if isinstance(ed, list) else str(ed)
        except Exception:
            pass

        return {
            "ticker":              ticker,
            "sector":              info.get("sector"),
            "industry":            info.get("industry"),
            "employees":           info.get("fullTimeEmployees"),
            "market_cap":          info.get("marketCap"),
            "enterprise_value":    info.get("enterpriseValue"),
            "trailing_pe":         _fmt(info.get("trailingPE")),
            "forward_pe":          _fmt(info.get("forwardPE")),
            "price_to_book":       _fmt(info.get("priceToBook")),
            "trailing_eps":        _fmt(info.get("trailingEps")),
            "forward_eps":         _fmt(info.get("forwardEps")),
            "earnings_growth":     _pct(info.get("earningsGrowth")),
            "revenue_growth":      _pct(info.get("revenueGrowth")),
            "profit_margin":       _pct(info.get("profitMargins")),
            "operating_margin":    _pct(info.get("operatingMargins")),
            "roe":                 _pct(info.get("returnOnEquity")),
            "roa":                 _pct(info.get("returnOnAssets")),
            "debt_to_equity":      _fmt(info.get("debtToEquity")),
            "free_cashflow":       info.get("freeCashflow"),
            "dividend_yield":      _pct(info.get("dividendYield") / 100 if info.get("dividendYield") else None),
            "dividend_rate":       _fmt(info.get("dividendRate")),
            "week_52_high":        _fmt(info.get("fiftyTwoWeekHigh")),
            "week_52_low":         _fmt(info.get("fiftyTwoWeekLow")),
            "next_earnings_date":  earnings_date,
        }
    except Exception as e:
        logger.warning("Could not fetch fundamentals for %s: %s", ticker, e)
        return None


def fetch_stock_prices(ticker: str, period: str = "1y") -> bool:
    """
    Fetch OHLCV stock price history from yfinance and save to the database.

    Args:
        ticker: The stock ticker symbol (e.g. "AAPL").
        period: yfinance period string. One of: 5d, 1mo, 3mo, 6mo, 1y.
                Defaults to "1y".

    Returns:
        True if data was fetched and saved successfully, False on failure.
    """
    try:
        df = _yfinance_history(ticker, period)

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

    except RetryError:
        logger.error("Max retries reached for %s — yfinance unavailable", ticker)
        return False
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
        ok = fetch_stock_prices(ticker, period="1y")
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
        data = _fred_get(params)

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

    except RetryError:
        logger.error("Max retries reached for FRED series %s — API unavailable", series_id)
        return False
    except requests.HTTPError as e:
        logger.error("HTTP error fetching FRED series %s: %s", series_id, e)
        return False
    except Exception as e:
        logger.error("Unexpected error fetching FRED series %s: %s", series_id, e)
        return False


def fetch_cmc_metrics() -> bool:
    """
    Fetch Bitcoin dominance and stablecoin market cap from CoinMarketCap API.

    Calls /v1/global-metrics/quotes/latest and saves two indicators:
        - BTC_DOMINANCE: Bitcoin's % share of total crypto market cap
        - STABLECOIN_MCAP: Total stablecoin market cap (Billions USD)

    Returns:
        True if both metrics were saved successfully, False on failure.
    """
    if not CMC_API_KEY:
        logger.warning("CMC_API_KEY not set — skipping CoinMarketCap fetch")
        return False

    try:
        headers  = {"X-CMC_PRO_API_KEY": CMC_API_KEY, "Accept": "application/json"}
        response = requests.get(CMC_BASE_URL, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json().get("data", {})

        today = datetime.now().strftime("%Y-%m-%d")

        btc_dominance = data.get("btc_dominance")
        stablecoin_mcap = data.get("stablecoin_market_cap")

        if btc_dominance is None or stablecoin_mcap is None:
            logger.error("CMC response missing expected fields: %s", list(data.keys()))
            return False

        database.insert_indicator("BTC_DOMINANCE",   "Bitcoin Dominance",       today, float(btc_dominance),           "%")
        database.insert_indicator("STABLECOIN_MCAP", "Stablecoin Market Cap",   today, round(stablecoin_mcap / 1e9, 2), "Billions USD")

        logger.info(
            "CMC metrics saved — BTC dominance: %.2f%%, Stablecoin market cap: $%.1fB",
            btc_dominance,
            stablecoin_mcap / 1e9,
        )
        return True

    except requests.HTTPError as e:
        logger.error("HTTP error fetching CMC metrics: %s", e)
        return False
    except Exception as e:
        logger.error("Unexpected error fetching CMC metrics: %s", e)
        return False


def fetch_all_indicators() -> None:
    """
    Fetch all configured FRED and CMC economic indicators and save to the database.

    Loops through FRED_SERIES constant and calls fetch_fred_series() for each,
    then calls fetch_cmc_metrics() for CoinMarketCap data.
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

    cmc_ok = fetch_cmc_metrics()
    if cmc_ok:
        success_count += 1
    else:
        fail_count += 1

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
