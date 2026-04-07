"""
scheduler.py
------------
Background job scheduler for EconoWatch. Runs scraper jobs automatically
on a fixed interval so data stays fresh without manual intervention.

Functions:
    start_scheduler() -> None: Start APScheduler with all background jobs
    stop_scheduler()  -> None: Shutdown scheduler gracefully on process exit
    run_screener()    -> None: Fetch S&P 100 prices, run TA, save screener scores
    send_daily_newsletter() -> None: Build and email daily digest to configured recipients
"""
import email.mime.multipart
import email.mime.text
import logging
import os
import smtplib
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
from dotenv import load_dotenv

import analysis
import database
import scraper

# ── Constants ────────────────────────────────────────
load_dotenv()
SCRAPE_INTERVAL_MINUTES    = int(os.getenv("SCRAPE_INTERVAL_MINUTES", "15"))
INDICATOR_INTERVAL_MINUTES = 60
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

SP100_TICKERS = [
    "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "TSLA", "BRK-B", "JPM", "UNH",
    "XOM",  "JNJ",  "V",    "PG",   "MA",    "HD",   "CVX",  "MRK",   "ABBV","PEP",
    "COST", "KO",   "AVGO", "WMT",  "MCD",   "CSCO", "ACN",  "LIN",   "TMO", "ABT",
    "CRM",  "BAC",  "NKE",  "DHR",  "ORCL",  "NEE",  "TXN",  "PM",    "QCOM","RTX",
    "HON",  "AMGN", "UPS",  "SBUX", "IBM",   "GS",   "CAT",  "LOW",   "SPGI","INTU",
    "ELV",  "AXP",  "BLK",  "DE",   "GILD",  "ADI",  "MDLZ", "ISRG",  "VRTX","REGN",
    "SYK",  "MO",   "ZTS",  "PLD",  "MMC",   "CI",   "TJX",  "EOG",   "LRCX","NOC",
    "SO",   "D",    "DUK",  "AEP",  "SRE",   "PCG",  "WEC",  "ED",    "ES",  "XEL",
    "GE",   "BA",   "MMM",  "LMT",  "GD",    "HUM",  "MCK",  "CAH",   "CNC", "CVS",
    "SCHW", "BDX",  "AFL",  "MET",  "PRU",   "AIG",  "TRV",  "CB",    "AON", "ALL",
]  # 100 tickers  (WBA delisted → SCHW; ANTM renamed to ELV already in list → BDX)

SP100_NAMES = {
    "AAPL": "Apple",          "MSFT": "Microsoft",        "AMZN": "Amazon",
    "NVDA": "NVIDIA",         "GOOGL": "Alphabet",         "META": "Meta",
    "TSLA": "Tesla",          "BRK-B": "Berkshire Hathaway","JPM": "JPMorgan Chase",
    "UNH":  "UnitedHealth",   "XOM":  "ExxonMobil",        "JNJ": "Johnson & Johnson",
    "V":    "Visa",           "PG":   "Procter & Gamble",   "MA":  "Mastercard",
    "HD":   "Home Depot",     "CVX":  "Chevron",            "MRK": "Merck",
    "ABBV": "AbbVie",         "PEP":  "PepsiCo",            "COST":"Costco",
    "KO":   "Coca-Cola",      "AVGO": "Broadcom",           "WMT": "Walmart",
    "MCD":  "McDonald's",     "CSCO": "Cisco",              "ACN": "Accenture",
    "LIN":  "Linde",          "TMO":  "Thermo Fisher",      "ABT": "Abbott",
    "CRM":  "Salesforce",     "BAC":  "Bank of America",    "NKE": "Nike",
    "DHR":  "Danaher",        "ORCL": "Oracle",             "NEE": "NextEra Energy",
    "TXN":  "Texas Instruments","PM": "Philip Morris",      "QCOM":"Qualcomm",
    "RTX":  "RTX Corp",       "HON":  "Honeywell",          "AMGN":"Amgen",
    "UPS":  "UPS",            "SBUX": "Starbucks",          "IBM": "IBM",
    "GS":   "Goldman Sachs",  "CAT":  "Caterpillar",        "LOW": "Lowe's",
    "SPGI": "S&P Global",     "INTU": "Intuit",             "ELV": "Elevance Health",
    "AXP":  "American Express","BLK": "BlackRock",          "DE":  "John Deere",
    "GILD": "Gilead Sciences","ADI":  "Analog Devices",     "MDLZ":"Mondelez",
    "ISRG": "Intuitive Surgical","VRTX":"Vertex Pharma",    "REGN":"Regeneron",
    "SYK":  "Stryker",        "MO":   "Altria",             "ZTS": "Zoetis",
    "PLD":  "Prologis",       "MMC":  "Marsh McLennan",     "CI":  "Cigna",
    "TJX":  "TJX Companies",  "EOG":  "EOG Resources",      "LRCX":"Lam Research",
    "NOC":  "Northrop Grumman","SO":  "Southern Company",   "D":   "Dominion Energy",
    "DUK":  "Duke Energy",    "AEP":  "American Elec Power","SRE": "Sempra",
    "PCG":  "PG&E",           "WEC":  "WEC Energy",         "ED":  "Con Edison",
    "ES":   "Eversource",     "XEL":  "Xcel Energy",        "GE":  "GE Aerospace",
    "BA":   "Boeing",         "MMM":  "3M",                 "LMT": "Lockheed Martin",
    "GD":   "General Dynamics","HUM": "Humana",             "MCK": "McKesson",
    "CAH":  "Cardinal Health","CNC":  "Centene",            "CVS": "CVS Health",
    "SCHW": "Charles Schwab",  "BDX":  "Becton Dickinson",   "AFL": "Aflac",
    "MET":  "MetLife",        "PRU":  "Prudential",         "AIG": "AIG",
    "TRV":  "Travelers",      "CB":   "Chubb",              "AON": "Aon",
    "ALL":  "Allstate",
}

_SIGNAL_TO_SCORE = {
    "STRONG BUY":  9,
    "BUY":         7,
    "HOLD":        5,
    "SELL":        3,
    "STRONG SELL": 1,
}

logger = logging.getLogger(__name__)

# Module-level scheduler instance — one per process
_scheduler = BackgroundScheduler()


# ── Job functions ─────────────────────────────────────

def _job_fetch_prices() -> None:
    """Scheduled job: fetch latest prices for all watchlist tickers."""
    logger.info("Scheduler: running fetch_watchlist_prices()")
    scraper.fetch_watchlist_prices()
    
    logger.info("Scheduler: triggering alert generation")
    analysis.check_and_generate_alerts()


def _job_fetch_indicators() -> None:
    """Scheduled job: fetch all FRED economic indicators."""
    logger.info("Scheduler: running fetch_all_indicators()")
    scraper.fetch_all_indicators()


def run_screener() -> None:
    """
    Fetch prices for all S&P 100 tickers, run TA analysis, and save scores to the screener table.

    Uses a single yf.download() batch call for all 100 tickers instead of 100 individual
    fetches, then runs TA analysis for each. Called daily at 16:15 ET and on-demand.
    """
    logger.info("Screener: starting S&P 100 scan (%d tickers)", len(SP100_TICKERS))

    # One batch download for all 100 tickers — much faster than per-ticker calls
    scraper.fetch_screener_batch(SP100_TICKERS, "3mo")

    processed = 0
    for ticker in SP100_TICKERS:
        try:
            result = analysis.generate_analysis(ticker, "3mo")
            if result is None:
                logger.debug("Screener: skipping %s — insufficient data", ticker)
                continue

            bullish_score = _SIGNAL_TO_SCORE.get(result["signal"], 5)
            rsi = result["indicators"]["rsi"]["value"]
            macd_trend = result["indicators"]["macd"]["trend"]
            sma_cross = result["indicators"]["sma"]["cross"]
            macd_signal = "buy" if macd_trend == "bullish" else ("sell" if macd_trend == "bearish" else "neutral")
            sma_signal  = "golden_cross" if sma_cross == "bullish" else ("death_cross" if sma_cross == "bearish" else "neutral")
            name = SP100_NAMES.get(ticker, ticker)

            database.upsert_screener_row(
                ticker, name, bullish_score, rsi, macd_signal, sma_signal, result["price"]
            )
            processed += 1
        except Exception as e:
            logger.error("Screener: error processing %s: %s", ticker, e)

    logger.info("Screener complete: %d/%d tickers processed", processed, len(SP100_TICKERS))


# ── Event listener ────────────────────────────────────

def _on_job_event(event) -> None:
    """Log job success or failure."""
    if event.exception:
        logger.error("Scheduler job %s failed: %s", event.job_id, event.exception)
    else:
        logger.debug("Scheduler job %s completed successfully", event.job_id)


# ── Public API ────────────────────────────────────────

def start_scheduler() -> None:
    """
    Start the background scheduler with all scraping jobs.

    Jobs:
        fetch_prices:     runs every SCRAPE_INTERVAL_MINUTES (default 15)
        fetch_indicators: runs every INDICATOR_INTERVAL_MINUTES (default 60)

    Safe to call multiple times — skips if already running.
    """
    if _scheduler.running:
        logger.warning("Scheduler already running — skipping start")
        return

    _scheduler.add_listener(_on_job_event, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

    _scheduler.add_job(
        _job_fetch_prices,
        trigger="interval",
        minutes=SCRAPE_INTERVAL_MINUTES,
        id="fetch_prices",
        name="Fetch watchlist prices",
        max_instances=1,
        misfire_grace_time=60,
    )

    _scheduler.add_job(
        _job_fetch_indicators,
        trigger="interval",
        minutes=INDICATOR_INTERVAL_MINUTES,
        id="fetch_indicators",
        name="Fetch FRED indicators",
        max_instances=1,
        misfire_grace_time=120,
    )

    _scheduler.add_job(
        run_screener,
        trigger="cron",
        hour=16,
        minute=15,
        id="screener",
        name="S&P 100 daily screener",
        max_instances=1,
        misfire_grace_time=300,
        replace_existing=True,
    )

    _scheduler.add_job(
        send_daily_newsletter,
        trigger="cron",
        hour=7,
        minute=0,
        id="daily_newsletter",
        name="Daily newsletter digest",
        max_instances=1,
        misfire_grace_time=600,
        replace_existing=True,
    )

    _scheduler.start()
    logger.info(
        "Scheduler started — prices every %d min, indicators every %d min",
        SCRAPE_INTERVAL_MINUTES,
        INDICATOR_INTERVAL_MINUTES,
    )

    # Fire immediate startup fetches so the dashboard has data on fresh installs
    _scheduler.add_job(
        _job_fetch_prices,
        trigger="date",
        run_date=datetime.now(),
        id="fetch_prices_startup",
        name="Initial price fetch on startup",
    )

    _scheduler.add_job(
        _job_fetch_indicators,
        trigger="date",
        run_date=datetime.now(),
        id="fetch_indicators_startup",
        name="Initial indicators fetch on startup",
    )


def send_daily_newsletter() -> None:
    """
    Build and email the daily EconoWatch digest to all configured recipients.

    Reads SMTP settings and newsletter_to from the settings table.
    Renders email_report.html via jinja2 directly (not Flask render_template)
    to avoid needing an active Flask app context inside the scheduler.
    Silently returns if SMTP is not configured.
    """
    smtp_host     = database.get_setting("smtp_host", "")
    smtp_port_str = database.get_setting("smtp_port", "587")
    smtp_user     = database.get_setting("smtp_user", "")
    smtp_pass     = database.get_setting("smtp_pass", "")
    newsletter_to = database.get_setting("newsletter_to", "")

    if not all([smtp_host, smtp_user, smtp_pass, newsletter_to]):
        logger.debug("Newsletter: SMTP not configured — skipping")
        return

    try:
        smtp_port = int(smtp_port_str)
    except ValueError:
        smtp_port = 587

    recipients = [r.strip() for r in newsletter_to.split(",") if r.strip()]
    if not recipients:
        return

    # Build template context
    indicators = database.get_indicators()
    movers     = database.get_top_movers(limit=5)
    today      = datetime.now().strftime("%B %d, %Y")

    # Render with jinja2 directly — no Flask app context needed
    try:
        from jinja2 import Environment, FileSystemLoader
        template_dir = Path(__file__).parent / "templates"
        env = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=True)
        template = env.get_template("email_report.html")
        html_body = template.render(
            date=today,
            indicators=indicators,
            gainers=movers.get("gainers", []),
            losers=movers.get("losers", []),
        )
    except Exception as e:
        logger.error("Newsletter: template render failed: %s", e)
        return

    # Build MIME message
    msg = email.mime.multipart.MIMEMultipart("alternative")
    msg["Subject"] = f"EconoWatch Daily Digest — {today}"
    msg["From"]    = smtp_user
    msg["To"]      = ", ".join(recipients)
    msg.attach(email.mime.text.MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, recipients, msg.as_string())
        logger.info("Newsletter sent to %d recipient(s)", len(recipients))
    except Exception as e:
        logger.error("Newsletter: SMTP send failed: %s", e)


def stop_scheduler() -> None:
    """
    Shutdown the scheduler gracefully.

    Called via atexit.register() in app.py — fires once on process exit.
    Never call this from teardown_appcontext (fires on every request).
    """
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


if __name__ == "__main__":
    import time
    import database
    logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)

    logger.info("=== Scheduler standalone test ===")
    database.init_db()
    start_scheduler()
    logger.info("Scheduler running — press Ctrl+C to stop")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_scheduler()
        logger.info("Stopped.")
