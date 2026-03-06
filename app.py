"""
app.py
------
Flask application entry point. Defines all API routes and serves the dashboard.

Functions:
    index() -> Response: Serve the dashboard HTML page
    get_stock(ticker) -> Response: Return stock price history as JSON
    get_indicators() -> Response: Return latest economic indicators as JSON
    get_movers() -> Response: Return top daily gainers and losers as JSON
    search_ticker() -> Response: Validate a ticker symbol and return its name
    get_status() -> Response: Return server status and last data update time
    get_analysis(ticker) -> Response: Return technical analysis as JSON
    get_macro() -> Response: Return macro regime analysis as JSON
    get_indicator_history(series_id) -> Response: Return historical values for one indicator as JSON
"""
import atexit
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

import analysis
import database
import scheduler
import scraper

# ── Constants ────────────────────────────────────────
load_dotenv()
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev_secret")
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "False").lower() == "true"
STALE_THRESHOLD_MINUTES = 15

VALID_PERIODS = {"1d", "5d", "1w", "1mo", "3mo", "6mo", "1y"}

PERIOD_TO_DAYS = {
    "1d":  2,    # yesterday + today
    "5d":  5,
    "1w":  7,    # ~5 trading days
    "1mo": 30,
    "3mo": 90,
    "6mo": 180,
    "1y":  365,
}

# yfinance only accepts specific period strings — map custom periods to nearest valid one
PERIOD_TO_YFINANCE = {
    "1d":  "5d",   # need at least 2 daily candles; fetch 5d then slice to 2
    "5d":  "5d",
    "1w":  "5d",   # 1 trading week ≈ 5 trading days
    "1mo": "1mo",
    "3mo": "3mo",
    "6mo": "6mo",
    "1y":  "1y",
}

logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["SECRET_KEY"] = FLASK_SECRET_KEY


# ── Helpers ──────────────────────────────────────────

def _is_stale(ticker: str) -> bool:
    """
    Check if stock data for a ticker is stale (older than STALE_THRESHOLD_MINUTES).

    Args:
        ticker: The stock ticker symbol.

    Returns:
        True if data is missing or stale, False if fresh.
    """
    try:
        with database.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT MAX(created_at) FROM stocks WHERE ticker = ?",
                (ticker,),
            )
            row = cursor.fetchone()
            if not row or not row[0]:
                return True
            last_updated = datetime.strptime(row[0][:19], "%Y-%m-%d %H:%M:%S")
            return datetime.now() - last_updated > timedelta(minutes=STALE_THRESHOLD_MINUTES)
    except Exception as e:
        logger.error("Error checking staleness for %s: %s", ticker, e)
        return True


def _is_valid_ticker_format(ticker: str) -> bool:
    """
    Validate that a ticker string contains only safe characters.

    Args:
        ticker: The ticker string to validate.

    Returns:
        True if format is valid, False otherwise.
    """
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-^.=")
    return bool(ticker) and all(c in allowed for c in ticker.upper())


# ── Routes ───────────────────────────────────────────

@app.route("/")
def index():
    """Route: GET / — Serve the dashboard HTML page."""
    return render_template("index.html")


@app.route("/api/stock/<string:ticker>")
def get_stock(ticker: str):
    """
    Route: GET /api/stock/<ticker>?period=1mo — Return stock price history as JSON.

    Query params:
        period: One of 5d, 1mo, 3mo, 6mo, 1y. Defaults to 1mo.
    """
    ticker = ticker.upper()

    if not _is_valid_ticker_format(ticker):
        return jsonify({"error": "Invalid ticker format"}), 400

    period = request.args.get("period", "1mo").lower()
    if period not in VALID_PERIODS:
        return jsonify({"error": f"Invalid period. Use one of: {', '.join(VALID_PERIODS)}"}), 400

    days        = PERIOD_TO_DAYS[period]
    yf_period   = PERIOD_TO_YFINANCE[period]

    # Fetch fresh data if stale or missing (use yfinance-compatible period)
    if _is_stale(ticker):
        logger.info("Data stale for %s — fetching from yfinance", ticker)
        scraper.fetch_stock_prices(ticker, yf_period)

    rows = database.get_stock_history(ticker, days)

    if not rows:
        return jsonify({"error": f"No data found for {ticker}"}), 404

    labels  = [r["date"] for r in rows]
    prices  = [round(r["close"], 2) if r["close"] else None for r in rows]
    volumes = [int(r["volume"]) if r["volume"] else 0 for r in rows]

    latest_close = prices[-1] if prices else None

    # change_pct = full period change: first price in window vs latest
    change_pct = None
    if len(prices) >= 2 and prices[0]:
        change_pct = round((prices[-1] - prices[0]) / prices[0] * 100, 2)

    return jsonify({
        "ticker":       ticker,
        "labels":       labels,
        "prices":       prices,
        "volumes":      volumes,
        "latest_close": latest_close,
        "change_pct":   change_pct,
        "error":        None,
    }), 200


@app.route("/api/indicators")
def get_indicators():
    """Route: GET /api/indicators — Return latest economic indicator values as JSON."""
    rows = database.get_indicators()

    if not rows:
        return jsonify({"error": "No indicator data available"}), 404

    indicators = []
    for row in rows:
        value      = row["value"]
        prev_value = row.get("prev_value")

        if prev_value is not None:
            if value > prev_value:
                trend = "up"
            elif value < prev_value:
                trend = "down"
            else:
                trend = "flat"
        else:
            trend = "flat"

        indicators.append({
            "series_id": row["series_id"],
            "name":      row["name"],
            "value":     round(value, 3),
            "unit":      row["unit"],
            "date":      row["date"],
            "trend":     trend,
        })

    return jsonify({"indicators": indicators}), 200


@app.route("/api/movers")
def get_movers():
    """Route: GET /api/movers — Return top daily gainers and losers from the watchlist."""
    movers = database.get_top_movers(limit=5)

    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with database.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(created_at) FROM stocks")
            row = cursor.fetchone()
            if row and row[0]:
                updated_at = row[0][:19]
    except Exception as e:
        logger.warning("Could not get updated_at timestamp: %s", e)

    return jsonify({
        "gainers":    movers.get("gainers", []),
        "losers":     movers.get("losers", []),
        "updated_at": updated_at,
    }), 200


@app.route("/api/search")
def search_ticker():
    """Route: GET /api/search?q=<ticker> — Validate a ticker and return its name."""
    query = request.args.get("q", "").strip().upper()

    if not query:
        return jsonify({"error": "Missing query parameter: q"}), 400

    if not _is_valid_ticker_format(query):
        return jsonify({"valid": False, "ticker": query, "name": None,
                        "error": "Invalid ticker format"}), 400

    is_valid = scraper.validate_ticker(query)
    if not is_valid:
        return jsonify({"valid": False, "ticker": query, "name": None,
                        "error": "Ticker not found"}), 200

    # Try to get the company name from yfinance
    name = query
    try:
        import yfinance as yf
        info = yf.Ticker(query).info
        name = info.get("shortName") or info.get("longName") or query
    except Exception:
        pass

    return jsonify({"valid": True, "ticker": query, "name": name, "error": None}), 200


@app.route("/api/watchlist")
def get_watchlist():
    """Route: GET /api/watchlist — Return all tickers in the watchlist."""
    rows = database.get_watchlist()
    return jsonify([{"ticker": r["ticker"], "name": r["name"]} for r in rows]), 200


@app.route("/api/analysis/<string:ticker>")
def get_analysis(ticker: str):
    """Route: GET /api/analysis/<ticker>?period=3mo — Return TA analysis as JSON."""
    ticker = ticker.upper()

    if not _is_valid_ticker_format(ticker):
        return jsonify({"error": "Invalid ticker format"}), 400

    period = request.args.get("period", "3mo").lower()
    if period not in VALID_PERIODS:
        period = "3mo"

    if _is_stale(ticker):
        logger.info("Data stale for %s — fetching before analysis", ticker)
        scraper.fetch_stock_prices(ticker, PERIOD_TO_YFINANCE.get(period, period))

    result = analysis.generate_analysis(ticker, period)
    if not result:
        return jsonify({"error": "Not enough data for analysis"}), 404

    return jsonify(result), 200


@app.route("/api/indicator/<string:series_id>")
def get_indicator_history(series_id: str):
    """Route: GET /api/indicator/<series_id>?days=30 — Return historical values for one indicator."""
    series_id = series_id.upper()
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")
    if not series_id or not all(c in allowed for c in series_id):
        return jsonify({"error": "Invalid series_id format"}), 400

    days = request.args.get("days", 30)
    try:
        days = int(days)
    except ValueError:
        days = 30

    rows = database.get_indicator_history(series_id, days)
    if not rows:
        return jsonify({"error": f"No data found for {series_id}"}), 404

    return jsonify({
        "series_id": series_id,
        "labels":    [r["date"] for r in rows],
        "values":    [round(r["value"], 4) for r in rows],
        "unit":      rows[-1]["unit"],
    }), 200


@app.route("/api/macro")
def get_macro():
    """Route: GET /api/macro — Return macro regime analysis and asset class recommendation."""
    result = analysis.generate_macro_analysis()
    if not result:
        return jsonify({"error": "No indicator data available for macro analysis"}), 404
    return jsonify(result), 200


@app.route("/api/status")
def get_status():
    """Route: GET /api/status — Return server status and last data update timestamp."""
    last_updated = "unknown"
    try:
        with database.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(created_at) FROM stocks")
            row = cursor.fetchone()
            if row and row[0]:
                last_updated = row[0][:19]
    except Exception as e:
        logger.error("Error fetching status: %s", e)

    return jsonify({"status": "ok", "last_updated": last_updated}), 200


# ── Error Handlers ───────────────────────────────────

@app.errorhandler(404)
def not_found(error):
    """Return JSON 404 — never expose stack traces."""
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def server_error(error):
    """Return JSON 500 — never expose stack traces."""
    logger.error("Internal server error: %s", error)
    return jsonify({"error": "Internal server error"}), 500


# ── Entry Point ──────────────────────────────────────

if __name__ == "__main__":
    database.init_db()
    scheduler.start_scheduler()
    atexit.register(scheduler.stop_scheduler)
    app.run(debug=FLASK_DEBUG, port=5000)
