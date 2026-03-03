"""
database.py
-----------
SQLite schema definition and all CRUD functions for EconoWatch.

Functions:
    init_db() -> None: Create all tables if they don't exist
    get_db_connection() -> sqlite3.Connection: Open and return a configured connection
    insert_stock_prices(ticker, df) -> bool: Save price DataFrame to stocks table
    get_stock_history(ticker, days) -> list[dict]: Fetch price rows for a ticker
    insert_indicator(series_id, name, date, value, unit) -> bool: Save one indicator row
    get_indicators() -> list[dict]: Get latest value for each indicator
    get_top_movers(limit) -> dict: Return top gainers and losers from watchlist
    get_watchlist() -> list[dict]: Return all tickers in watchlist
    add_to_watchlist(ticker, name) -> bool: Insert a ticker into watchlist
"""
import logging
import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

# ── Constants ────────────────────────────────────────
load_dotenv()
DB_PATH = Path(os.getenv("DB_PATH", "data/econowatch.db"))
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

logger = logging.getLogger(__name__)


def get_db_connection() -> sqlite3.Connection:
    """
    Open and return a configured SQLite connection.

    Returns:
        A sqlite3.Connection with row_factory set to sqlite3.Row.
    """
    os.makedirs(DB_PATH.parent, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """
    Create all database tables if they do not already exist.

    Creates: stocks, economic_indicators, watchlist tables.
    """
    os.makedirs(DB_PATH.parent, exist_ok=True)
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stocks (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker     TEXT NOT NULL,
                date       TEXT NOT NULL,
                open       REAL,
                high       REAL,
                low        REAL,
                close      REAL,
                volume     INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(ticker, date)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS economic_indicators (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                series_id  TEXT NOT NULL,
                name       TEXT NOT NULL,
                date       TEXT NOT NULL,
                value      REAL,
                unit       TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(series_id, date)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker   TEXT NOT NULL UNIQUE,
                name     TEXT,
                added_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
    logger.info("Database initialized at %s", DB_PATH)


def insert_stock_prices(ticker: str, df) -> bool:
    """
    Save a DataFrame of OHLCV prices to the stocks table.

    Args:
        ticker: The stock ticker symbol (e.g. "AAPL").
        df: A pandas DataFrame with columns: date, open, high, low, close, volume.

    Returns:
        True if successful, False on failure.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            rows_inserted = 0
            for _, row in df.iterrows():
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO stocks (ticker, date, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ticker,
                        str(row["date"]),
                        round(float(row["open"]), 4) if row["open"] else None,
                        round(float(row["high"]), 4) if row["high"] else None,
                        round(float(row["low"]), 4) if row["low"] else None,
                        round(float(row["close"]), 4) if row["close"] else None,
                        int(row["volume"]) if row["volume"] else None,
                    ),
                )
                rows_inserted += cursor.rowcount
            conn.commit()
        logger.info("Inserted %d rows for %s", rows_inserted, ticker)
        return True
    except Exception as e:
        logger.error("Failed to insert stock prices for %s: %s", ticker, e)
        return False


def get_stock_history(ticker: str, days: int = 30) -> list:
    """
    Fetch price rows for a ticker ordered by date ascending.

    Args:
        ticker: The stock ticker symbol.
        days: Number of most recent days to return. Defaults to 30.

    Returns:
        List of dicts with keys: date, open, high, low, close, volume.
        Returns empty list if no data found.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT date, open, high, low, close, volume
                FROM stocks
                WHERE ticker = ?
                ORDER BY date DESC
                LIMIT ?
                """,
                (ticker, days),
            )
            rows = cursor.fetchall()
        result = [dict(row) for row in reversed(rows)]
        return result
    except Exception as e:
        logger.error("Failed to get stock history for %s: %s", ticker, e)
        return []


def insert_indicator(series_id: str, name: str, date: str, value: float, unit: str) -> bool:
    """
    Save one economic indicator data point to the database.

    Args:
        series_id: FRED series ID (e.g. "CPIAUCSL").
        name: Human-readable name (e.g. "CPI Inflation").
        date: Date string in "YYYY-MM-DD" format.
        value: Numeric value of the indicator.
        unit: Unit label (e.g. "%" or "Billions USD").

    Returns:
        True if successful, False on failure.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR IGNORE INTO economic_indicators (series_id, name, date, value, unit)
                VALUES (?, ?, ?, ?, ?)
                """,
                (series_id, name, date, value, unit),
            )
            conn.commit()
        return True
    except Exception as e:
        logger.error("Failed to insert indicator %s: %s", series_id, e)
        return False


def get_indicators() -> list:
    """
    Get the latest value for each economic indicator.

    Returns:
        List of dicts with keys: series_id, name, date, value, unit, prev_value.
        Returns empty list if no data found.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT e1.series_id, e1.name, e1.date, e1.value, e1.unit,
                       e2.value AS prev_value
                FROM economic_indicators e1
                LEFT JOIN economic_indicators e2
                    ON e1.series_id = e2.series_id
                    AND e2.date = (
                        SELECT date FROM economic_indicators
                        WHERE series_id = e1.series_id
                        AND date < e1.date
                        ORDER BY date DESC
                        LIMIT 1
                    )
                WHERE e1.date = (
                    SELECT MAX(date) FROM economic_indicators
                    WHERE series_id = e1.series_id
                )
                ORDER BY e1.series_id
                """
            )
            rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error("Failed to get indicators: %s", e)
        return []


def get_top_movers(limit: int = 5) -> dict:
    """
    Calculate daily % change for all watchlist tickers and return top movers.

    Args:
        limit: Number of top gainers and losers to return. Defaults to 5.

    Returns:
        Dict with keys "gainers" and "losers", each a list of dicts:
        {ticker, name, change_pct, close}
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT w.ticker, w.name,
                       s1.close AS latest_close,
                       s2.close AS prev_close
                FROM watchlist w
                JOIN stocks s1 ON s1.ticker = w.ticker
                    AND s1.date = (
                        SELECT MAX(date) FROM stocks WHERE ticker = w.ticker
                    )
                JOIN stocks s2 ON s2.ticker = w.ticker
                    AND s2.date = (
                        SELECT MAX(date) FROM stocks
                        WHERE ticker = w.ticker
                        AND date < s1.date
                    )
                """
            )
            rows = cursor.fetchall()

        movers = []
        for row in rows:
            if row["prev_close"] and row["prev_close"] != 0:
                change_pct = round(
                    (row["latest_close"] - row["prev_close"]) / row["prev_close"] * 100, 2
                )
                movers.append({
                    "ticker": row["ticker"],
                    "name": row["name"],
                    "change_pct": change_pct,
                    "close": round(row["latest_close"], 2),
                })

        movers.sort(key=lambda x: x["change_pct"], reverse=True)
        return {
            "gainers": movers[:limit],
            "losers": movers[-limit:][::-1],
        }
    except Exception as e:
        logger.error("Failed to get top movers: %s", e)
        return {"gainers": [], "losers": []}


def get_watchlist() -> list:
    """
    Return all tickers currently in the watchlist.

    Returns:
        List of dicts with keys: id, ticker, name, added_at.
        Returns empty list if watchlist is empty.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, ticker, name, added_at FROM watchlist ORDER BY added_at")
            rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error("Failed to get watchlist: %s", e)
        return []


def add_to_watchlist(ticker: str, name: str) -> bool:
    """
    Add a new ticker to the watchlist.

    Args:
        ticker: The stock ticker symbol.
        name: Human-readable company or index name.

    Returns:
        True if inserted, False if already exists or on error.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO watchlist (ticker, name) VALUES (?, ?)",
                (ticker, name),
            )
            conn.commit()
        logger.info("Added %s (%s) to watchlist", ticker, name)
        return True
    except Exception as e:
        logger.error("Failed to add %s to watchlist: %s", ticker, e)
        return False


if __name__ == "__main__":
    logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)
    init_db()
    logger.info("database.py standalone run complete — tables created.")
