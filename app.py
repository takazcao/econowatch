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
    get_range(ticker) -> Response: Return 52-week high, low, current price and range position as JSON
    get_ai_summary() -> Response: Return AI-generated 2-3 sentence macro regime summary as JSON
    get_radar(ticker) -> Response: Return 6-dimension radar scores for a ticker as JSON
    ai_chat() -> Response: AI assistant response for the current ticker context (Pro only)
    settings_page() -> Response: Render settings page (GET) or save settings (POST)
"""
import atexit
import functools
import json
import logging
import os
import secrets
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
import csv
import io
from flask import Flask, Response, flash, jsonify, redirect, render_template, request, session, stream_with_context, url_for

import analysis
import cache as _cache_module
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
DASHBOARD_PIN = os.getenv("DASHBOARD_PIN")  # optional — if unset, app is open
STALE_THRESHOLD_MINUTES = 15

VALID_PERIODS = {"1d", "5d", "1w", "1mo", "3mo", "6mo", "1y"}

# ── AI Summary Cache ─────────────────────────────────
_ai_summary_cache: dict = {"summary": None, "generated_at": None, "expires_at": None}

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

LICENSE_VALIDATION_URL = os.getenv("LICENSE_VALIDATION_URL", "")

SETTINGS_KEYS = [
    "license_key", "logo_url", "brand_color",
    "polygon_api_key", "finnhub_api_key",
    "discord_webhook_url", "telegram_bot_token", "telegram_chat_id",
    "smtp_host", "smtp_port", "smtp_user", "smtp_pass", "newsletter_to",
]

# Sensitive keys — only write to DB when the submitted value is non-empty
SETTINGS_SENSITIVE = {"polygon_api_key", "finnhub_api_key", "telegram_bot_token", "smtp_pass"}

logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["SECRET_KEY"] = FLASK_SECRET_KEY
_cache_module.cache.init_app(app, config={"CACHE_TYPE": "SimpleCache", "CACHE_DEFAULT_TIMEOUT": 300})


# ── PIN Auth ─────────────────────────────────────────

@app.before_request
def _check_pin():
    """Block all routes (except /login, /logout, static) when DASHBOARD_PIN is set and user is not authenticated."""
    if not DASHBOARD_PIN:
        return  # PIN not configured — open access
    if request.endpoint in ("login", "do_login", "logout", "static"):
        return  # always allow auth endpoints and static assets
    if not session.get("authenticated"):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Unauthorized"}), 401
        return redirect(url_for("login"))


@app.route("/login", methods=["GET"])
def login():
    """Route: GET /login — Render PIN entry form."""
    if not DASHBOARD_PIN:
        return redirect(url_for("index"))
    if session.get("authenticated"):
        return redirect(url_for("index"))
    return render_template("login.html", error=None)


@app.route("/login", methods=["POST"])
def do_login():
    """Route: POST /login — Validate PIN and start session."""
    pin = request.form.get("pin", "")
    if pin == DASHBOARD_PIN:
        session["authenticated"] = True
        return redirect(url_for("index"))
    return render_template("login.html", error="Incorrect PIN. Try again."), 401


@app.route("/logout")
def logout():
    """Route: GET /logout — Clear session and redirect to /login."""
    session.clear()
    return redirect(url_for("login"))


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
    return render_template("index.html", pro_unlocked=_is_pro_unlocked())


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


@app.route("/api/range/<string:ticker>")
def get_range(ticker: str):
    """Route: GET /api/range/<ticker> — Return 52-week high, low, current price, and range position."""
    ticker = ticker.upper()

    if not _is_valid_ticker_format(ticker):
        return jsonify({"error": "Invalid ticker format"}), 400

    data = scraper.get_ticker_range(ticker)
    if not data:
        return jsonify({"error": f"52-week range data unavailable for {ticker}"}), 404

    return jsonify(data), 200


def _ind_trend(ind: dict) -> str:
    """Compute trend string from an indicator row's value vs prev_value."""
    v = ind.get("value")
    p = ind.get("prev_value")
    if v is None or p is None:
        return "flat"
    if v > p:
        return "up"
    if v < p:
        return "down"
    return "flat"


def _rule_based_summary(indicators: list) -> str:
    """
    Generate a plain-English macro summary from indicator data without an AI API.

    Args:
        indicators: List of indicator dicts from database.get_indicators().

    Returns:
        A 2-3 sentence summary string.
    """
    by_id = {ind["series_id"]: ind for ind in indicators}

    sentences = []

    # Sentence 1 — Rates (Fed Funds + 10Y Treasury)
    fed   = by_id.get("FEDFUNDS")
    dgs10 = by_id.get("DGS10")
    dgs2  = by_id.get("DGS2")
    if fed:
        s = f"The Fed Funds rate stands at {round(fed['value'], 2)}%"
        if dgs10:
            s += f", with the 10-year Treasury at {round(dgs10['value'], 2)}%"
        if dgs2 and dgs10:
            spread = round(dgs10["value"] - dgs2["value"], 2)
            curve  = "inverted" if spread < 0 else "normal"
            s += f" (yield curve {curve}, spread {spread:+.2f}%)"
        sentences.append(s + ".")

    # Sentence 2 — Labour market
    unrate = by_id.get("UNRATE")
    if unrate:
        ur_dir = {"up": "rising", "down": "falling", "flat": "steady"}.get(_ind_trend(unrate), "steady")
        sentences.append(
            f"The labor market remains {ur_dir} with unemployment at {round(unrate['value'], 1)}%."
        )

    # Sentence 3 — Volatility / risk sentiment
    vix = by_id.get("VIXCLS")
    if vix:
        v = round(vix["value"], 1)
        if v > 30:
            mood = f"elevated market stress (VIX {v}) warrants caution"
        elif v > 20:
            mood = f"moderate volatility (VIX {v}) reflects cautious sentiment"
        else:
            mood = f"calm market conditions (VIX {v}) suggest risk-on positioning"
        sentences.append(mood[0].upper() + mood[1:] + ".")

    if not sentences:
        return "Insufficient indicator data to generate a macro summary."

    return " ".join(sentences)


@app.route("/api/ai-summary")
def get_ai_summary():
    """Route: GET /api/ai-summary — Return macro regime summary as JSON (Claude AI or rule-based)."""
    now = datetime.now()

    # Serve cached result if still fresh
    if _ai_summary_cache["expires_at"] and now < _ai_summary_cache["expires_at"]:
        return jsonify({
            "available":    True,
            "summary":      _ai_summary_cache["summary"],
            "generated_at": _ai_summary_cache["generated_at"],
            "source":       _ai_summary_cache.get("source", "auto"),
        }), 200

    indicators = database.get_indicators()
    if not indicators:
        return jsonify({"error": "No indicator data for AI summary"}), 404

    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")

    # ── Path A: Claude API ────────────────────────────
    if anthropic_key:
        lines = [
            f"- {ind['name']}: {round(ind['value'], 2)} {ind['unit']} (trend: {_ind_trend(ind)})"
            for ind in indicators
        ]
        prompt = (
            "You are a macro economist. Based on these latest economic indicators, "
            "write a 2-3 sentence plain-English summary of the current macro regime. "
            "Focus on the most important signals: inflation, rates, and growth momentum. "
            "Be direct and concise. No bullet points or headers.\n\n"
            f"Economic Indicators:\n" + "\n".join(lines)
        )
        try:
            import anthropic as _anthropic
            client = _anthropic.Anthropic(api_key=anthropic_key)
            message = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
            )
            summary = message.content[0].text.strip()
            source  = "claude"
            logger.info("AI summary generated via Claude API")
        except Exception as e:
            logger.error("Claude API call failed, falling back to rule-based: %s", e)
            summary = _rule_based_summary(indicators)
            source  = "auto"

    # ── Path B: Rule-based fallback (no API key) ──────
    else:
        summary = _rule_based_summary(indicators)
        source  = "auto"

    generated_at = now.strftime("%Y-%m-%d %H:%M:%S")
    _ai_summary_cache["summary"]      = summary
    _ai_summary_cache["generated_at"] = generated_at
    _ai_summary_cache["expires_at"]   = now + timedelta(hours=24)
    _ai_summary_cache["source"]       = source

    return jsonify({
        "available":    True,
        "summary":      summary,
        "generated_at": generated_at,
        "source":       source,
    }), 200


@app.route("/api/overlay/<string:series_id>")
def get_overlay(series_id: str):
    """Route: GET /api/overlay/<series_id> — Return FRED time series for chart overlay."""
    series_id = series_id.upper()
    allowed = {s[0] for s in scraper.FRED_SERIES}
    if series_id not in allowed:
        return jsonify({"error": "Unknown series_id"}), 400

    rows = database.get_indicator_history(series_id, days=500)
    if not rows:
        return jsonify({"error": "No data available for this series"}), 404

    meta = next((s for s in scraper.FRED_SERIES if s[0] == series_id), None)
    return jsonify({
        "series_id": series_id,
        "name":      meta[1] if meta else series_id,
        "unit":      meta[2] if meta else "",
        "data":      [{"time": r["date"], "value": r["value"]} for r in rows],
    }), 200


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


# ── License + Pro Helpers ────────────────────────────

def _validate_license_key(key: str) -> bool:
    """
    Validate a license key against the payment provider API.

    POSTs to LICENSE_VALIDATION_URL with {"key": key, "product": "econowatch"}.
    On success, caches result in settings table for 24 hours.
    Falls back to the cached license_valid DB value if the network call fails.

    Args:
        key: The license key string to validate.

    Returns:
        True if the license is valid, False otherwise.
    """
    import requests as _requests

    # Check 24-hour cache first
    cached_valid = database.get_setting("license_valid", "")
    cached_at_str = database.get_setting("license_checked_at", "")
    if cached_valid and cached_at_str:
        try:
            checked_at = datetime.strptime(cached_at_str, "%Y-%m-%d %H:%M:%S")
            if datetime.now() - checked_at < timedelta(hours=24):
                return cached_valid == "1"
        except ValueError:
            pass

    if not LICENSE_VALIDATION_URL or not key:
        return False

    try:
        resp = _requests.post(
            LICENSE_VALIDATION_URL,
            json={"key": key, "product": "econowatch"},
            timeout=5,
        )
        valid = resp.status_code == 200 and resp.json().get("valid", False)
    except Exception as e:
        logger.warning("License validation network error — using cached value: %s", e)
        return cached_valid == "1"

    database.set_setting("license_valid", "1" if valid else "0")
    database.set_setting("license_checked_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    return valid


def _is_pro_unlocked() -> bool:
    """Return True if a valid Pro license is active (always True in dev mode)."""
    if FLASK_DEBUG:
        return True
    return database.get_setting("license_valid", "0") == "1"


def requires_pro_license(f):
    """
    Flask route decorator that returns 403 if no valid Pro license is active.

    In dev mode (FLASK_DEBUG=True) this is a no-op — all routes pass through.
    """
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if FLASK_DEBUG:
            return f(*args, **kwargs)
        if not _is_pro_unlocked():
            return jsonify({"error": "Pro license required"}), 403
        return f(*args, **kwargs)
    return decorated


# ── CSRF Helpers ─────────────────────────────────────

def _generate_csrf_token() -> str:
    """Generate and store a CSRF token in the session, returning the token."""
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(32)
    return session["_csrf_token"]


def _validate_csrf() -> bool:
    """Return True if the submitted _csrf_token matches the session token."""
    return request.form.get("_csrf_token") == session.get("_csrf_token")


# ── Radar Route ──────────────────────────────────────

@app.route("/api/radar/<string:ticker>")
def get_radar(ticker: str):
    """Route: GET /api/radar/<ticker> — Return 6-dimension radar scores for a ticker."""
    ticker = ticker.upper()

    if not _is_valid_ticker_format(ticker):
        return jsonify({"error": "Invalid ticker format"}), 400

    if _is_stale(ticker):
        scraper.fetch_stock_prices(ticker, "1y")

    result = analysis.get_radar_data(ticker)
    if not result:
        return jsonify({"error": "Not enough data for radar analysis"}), 404

    return jsonify(result), 200


# ── AI Chat Route ────────────────────────────────────

@app.route("/api/chat", methods=["POST"])
@requires_pro_license
def ai_chat():
    """
    Route: POST /api/chat — AI assistant response in context of the current ticker (Pro only).

    Body JSON:
        message: str — the user's question
        ticker:  str — current ticker symbol (context)
        history: list[{role, content}] — prior conversation turns (max 10)
    """
    body    = request.get_json(silent=True) or {}
    message = str(body.get("message", "")).strip()
    ticker  = str(body.get("ticker", "")).strip().upper()
    history = body.get("history", [])

    if not message:
        return jsonify({"error": "message is required"}), 400

    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not anthropic_key:
        return jsonify({"error": "AI Chat is not configured (ANTHROPIC_API_KEY missing)"}), 503

    # Build system context
    system_parts = [
        "You are EconoWatch AI, a concise financial assistant. "
        "Answer questions about stocks, economic indicators, and macro trends. "
        "Be brief and direct. No unsolicited disclaimers."
    ]
    if ticker and _is_valid_ticker_format(ticker):
        rows = database.get_stock_history(ticker, 5)
        if rows:
            latest = rows[-1]
            system_parts.append(
                f"Current context: {ticker} last close ${latest['close']:.2f} on {latest['date']}."
            )

    system_prompt = " ".join(system_parts)

    # Sanitize history — keep last 10 turns, valid roles only
    safe_history = [
        {"role": turn["role"], "content": str(turn["content"])[:2000]}
        for turn in history[-10:]
        if turn.get("role") in ("user", "assistant") and turn.get("content")
    ]
    safe_history.append({"role": "user", "content": message})

    try:
        import anthropic as _anthropic
        client = _anthropic.Anthropic(api_key=anthropic_key)
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=system_prompt,
            messages=safe_history,
        )
        reply = resp.content[0].text.strip()
        return jsonify({"reply": reply}), 200
    except Exception as e:
        err_str = str(e)
        if "rate_limit" in err_str.lower() or "RateLimitError" in type(e).__name__:
            return jsonify({"error": "Rate limit. Try again in a moment."}), 429
        logger.error("AI chat error: %s", e)
        return jsonify({"error": "AI response unavailable"}), 503


# ── Settings Route ────────────────────────────────────

@app.route("/settings", methods=["GET", "POST"])
def settings_page():
    """Route: GET /settings — Render settings page. POST /settings — Save settings."""
    if request.method == "POST":
        if not _validate_csrf():
            return jsonify({"error": "Invalid CSRF token"}), 403

        for key in SETTINGS_KEYS:
            value = request.form.get(key, "").strip()
            # Sensitive fields: only overwrite when a new value is submitted
            if key in SETTINGS_SENSITIVE and not value:
                continue
            database.set_setting(key, value)

        # Validate license key immediately after save if one was submitted
        license_key = request.form.get("license_key", "").strip()
        if license_key:
            valid = _validate_license_key(license_key)
            if valid:
                flash("Settings saved. License key validated — Pro features unlocked!", "success")
            else:
                flash("Settings saved. License key could not be validated.", "warning")
        else:
            flash("Settings saved.", "success")

        return redirect(url_for("settings_page"))

    # GET — load current settings
    settings = {key: database.get_setting(key) for key in SETTINGS_KEYS}
    csrf_token = _generate_csrf_token()
    pro_unlocked = _is_pro_unlocked()
    return render_template("settings.html", settings=settings, csrf_token=csrf_token,
                           pro_unlocked=pro_unlocked)


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
