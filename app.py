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
    get_news(ticker) -> Response: Return latest news headlines for a ticker as JSON
    get_alerts() -> Response: Return unread alerts as JSON
    mark_alerts_read() -> Response: Mark all unread alerts as read
    export_csv(ticker) -> Response: Export price history as CSV file download
    get_fundamentals(ticker) -> Response: Return fundamental data for a ticker as JSON
    get_screener() -> Response: Return S&P 100 screener results as JSON
    portfolio_prices() -> Response: Return latest close price for a list of tickers as JSON
"""
import atexit
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
import csv
import io
from flask import Flask, Response, jsonify, render_template, request, stream_with_context

import analysis
import database
import scheduler
import scraper

# ── Constants ────────────────────────────────────────
load_dotenv()
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "False").lower() == "true"
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY")
if not FLASK_SECRET_KEY:
    if FLASK_DEBUG:
        FLASK_SECRET_KEY = "dev_secret_do_not_use_in_production"
        logging.warning("FLASK_SECRET_KEY not set — using insecure dev default")
    else:
        raise RuntimeError("FLASK_SECRET_KEY must be set when FLASK_DEBUG=False")
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
    opens   = [round(r["open"],  2) if r["open"]  else None for r in rows]
    highs   = [round(r["high"],  2) if r["high"]  else None for r in rows]
    lows    = [round(r["low"],   2) if r["low"]   else None for r in rows]
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
        "opens":        opens,
        "highs":        highs,
        "lows":         lows,
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

    name = scraper.get_ticker_name(query)

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


@app.route("/api/news/<string:ticker>")
def get_news(ticker: str):
    """Route: GET /api/news/<ticker> — Return latest news headlines for a ticker."""
    ticker = ticker.upper()

    if not _is_valid_ticker_format(ticker):
        return jsonify({"error": "Invalid ticker format"}), 400

    articles = scraper.get_ticker_news(ticker)
    return jsonify({"ticker": ticker, "articles": articles}), 200


@app.route("/api/fundamentals/<string:ticker>")
def get_fundamentals(ticker: str):
    """Route: GET /api/fundamentals/<ticker> — Return fundamental data for a ticker."""
    ticker = ticker.upper()

    if not _is_valid_ticker_format(ticker):
        return jsonify({"error": "Invalid ticker format"}), 400

    data = scraper.get_ticker_fundamentals(ticker)
    if not data:
        return jsonify({"error": f"Could not fetch fundamentals for {ticker}"}), 404

    return jsonify(data), 200


@app.route("/api/macro")
def get_macro():
    """Route: GET /api/macro — Return macro regime analysis and asset class recommendation."""
    result = analysis.generate_macro_analysis()
    if not result:
        return jsonify({"error": "No indicator data available for macro analysis"}), 404
    return jsonify(result), 200


@app.route("/api/alerts", methods=["GET"])
def get_alerts():
    """Route: GET /api/alerts — Return unread alerts."""
    alerts = database.get_unread_alerts()
    return jsonify({"alerts": alerts}), 200


@app.route("/api/alerts/read", methods=["POST"])
def mark_alerts_read():
    """Route: POST /api/alerts/read — Mark all alerts as read."""
    success = database.mark_alerts_read()
    if success:
        return jsonify({"success": True}), 200
    return jsonify({"error": "Failed to mark alerts as read"}), 500


@app.route("/api/export/<string:ticker>")
def export_csv(ticker: str):
    """Route: GET /api/export/<ticker>?period=1y — Download price history as CSV."""
    ticker = ticker.upper()

    if not _is_valid_ticker_format(ticker):
        return jsonify({"error": "Invalid ticker format"}), 400

    period = request.args.get("period", "1y").lower()
    days = PERIOD_TO_DAYS.get(period, 365)
    rows = database.get_stock_history(ticker, days)

    if not rows:
        return jsonify({"error": f"No data found for {ticker}"}), 404

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["date", "open", "high", "low", "close", "volume"])
    writer.writeheader()
    for r in rows:
        writer.writerow({
            "date":   r["date"],
            "open":   r["open"],
            "high":   r["high"],
            "low":    r["low"],
            "close":  r["close"],
            "volume": r["volume"],
        })

    filename = f"{ticker}_{period}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.route("/api/compare")
def get_compare():
    """Route: GET /api/compare?tickers=AAPL,MSFT&period=1mo — Normalized % change for multiple tickers."""
    raw = request.args.get("tickers", "")
    period = request.args.get("period", "1mo").lower()
    if period not in VALID_PERIODS:
        period = "1mo"

    tickers = [t.strip().upper() for t in raw.split(",") if t.strip()][:3]
    if len(tickers) < 2:
        return jsonify({"error": "Provide at least 2 tickers (e.g. ?tickers=AAPL,MSFT)"}), 400

    for t in tickers:
        if not _is_valid_ticker_format(t):
            return jsonify({"error": f"Invalid ticker format: {t}"}), 400

    days = PERIOD_TO_DAYS[period]
    series = {}
    all_dates = None

    for ticker in tickers:
        if _is_stale(ticker):
            scraper.fetch_stock_prices(ticker, PERIOD_TO_YFINANCE.get(period, period))
        rows = database.get_stock_history(ticker, days)
        if rows:
            date_price = {r["date"]: r["close"] for r in rows if r["close"]}
            series[ticker] = date_price
            dates = set(date_price.keys())
            all_dates = dates if all_dates is None else all_dates & dates

    if not all_dates or len(series) < 2:
        return jsonify({"error": "Not enough overlapping data"}), 404

    labels = sorted(all_dates)
    result = {"labels": labels, "series": {}}

    for ticker, date_price in series.items():
        prices = [date_price[d] for d in labels]
        base = prices[0]
        pct_changes = [round((p - base) / base * 100, 2) if base else 0 for p in prices]
        result["series"][ticker] = pct_changes

    return jsonify(result), 200


@app.route("/api/screener")
def get_screener():
    """Route: GET /api/screener — Return cached screener results (no scan triggered)."""
    rows = database.get_screener_results()
    scanned_at = rows[0].get("scanned_at", "") if rows else None
    return jsonify({
        "results":    rows,
        "count":      len(rows),
        "scanned_at": scanned_at,
    }), 200


@app.route("/api/screener/stream")
def screener_stream():
    """
    Route: GET /api/screener/stream — SSE stream of S&P 100 screener results.

    Emits events:
        {status: "downloading"}           — batch price fetch started
        {status: "analyzing", saved: N}   — prices saved, analysis starting
        {status: "row", ticker, ...}       — one ticker result ready
        {status: "done", count: N}         — all tickers processed
    """
    def generate():
        yield f"data: {json.dumps({'status': 'downloading', 'msg': 'Downloading 100 tickers...'})}\n\n"

        saved = scraper.fetch_screener_batch(scheduler.SP100_TICKERS, "3mo")

        yield f"data: {json.dumps({'status': 'analyzing', 'saved': saved, 'msg': f'Prices ready ({saved} tickers). Running analysis...'})}\n\n"

        processed = 0
        for ticker in scheduler.SP100_TICKERS:
            try:
                result = analysis.generate_analysis(ticker, "3mo")
                if result is None:
                    continue

                bullish_score = scheduler._SIGNAL_TO_SCORE.get(result["signal"], 5)
                rsi = result["indicators"]["rsi"]["value"]
                macd_trend = result["indicators"]["macd"]["trend"]
                sma_cross  = result["indicators"]["sma"]["cross"]
                macd_signal = "buy"  if macd_trend == "bullish" else ("sell" if macd_trend == "bearish" else "neutral")
                sma_signal  = "golden_cross" if sma_cross == "bullish" else ("death_cross" if sma_cross == "bearish" else "neutral")
                name = scheduler.SP100_NAMES.get(ticker, ticker)

                database.upsert_screener_row(ticker, name, bullish_score, rsi, macd_signal, sma_signal, result["price"])
                processed += 1

                yield f"data: {json.dumps({'status': 'row', 'ticker': ticker, 'name': name, 'bullish_score': bullish_score, 'rsi': round(rsi, 1), 'macd_signal': macd_signal, 'sma_signal': sma_signal, 'close': result['price'], 'processed': processed})}\n\n"

            except Exception as e:
                logger.error("Screener stream error for %s: %s", ticker, e)

        yield f"data: {json.dumps({'status': 'done', 'count': processed})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/portfolio/prices")
def portfolio_prices():
    """Route: GET /api/portfolio/prices?tickers=AAPL,MSFT — Return latest close price for each ticker."""
    raw = request.args.get("tickers", "").strip()
    if not raw:
        return jsonify({"error": "Missing tickers parameter"}), 400

    tickers = [t.strip().upper() for t in raw.split(",") if t.strip()][:20]
    if not tickers:
        return jsonify({"error": "No valid tickers provided"}), 400

    for t in tickers:
        if not _is_valid_ticker_format(t):
            return jsonify({"error": f"Invalid ticker format: {t}"}), 400

    prices = {}
    for ticker in tickers:
        rows = database.get_stock_history(ticker, days=2)
        if rows and rows[-1]["close"]:
            prices[ticker] = round(rows[-1]["close"], 2)

    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return jsonify({"prices": prices, "updated_at": updated_at}), 200


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
    app.run(debug=FLASK_DEBUG, host="0.0.0.0", port=5000)
