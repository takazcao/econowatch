"""
scheduler.py
------------
Background job scheduler for EconoWatch. Runs scraper jobs automatically
on a fixed interval so data stays fresh without manual intervention.

Functions:
    start_scheduler() -> None: Start APScheduler with all background jobs
    stop_scheduler()  -> None: Shutdown scheduler gracefully on process exit
"""
import logging
import os
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
from dotenv import load_dotenv

import analysis
import scraper

# ── Constants ────────────────────────────────────────
load_dotenv()
SCRAPE_INTERVAL_MINUTES    = int(os.getenv("SCRAPE_INTERVAL_MINUTES", "15"))
INDICATOR_INTERVAL_MINUTES = 60
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

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
