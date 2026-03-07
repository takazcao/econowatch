"""
wsgi.py
-------
Production entry point for EconoWatch.

Usage:
    Windows (local):  python wsgi.py          — Waitress on 0.0.0.0:5000
    Linux (Oracle):   gunicorn -w 1 -b 0.0.0.0:5000 --timeout 120 wsgi:app

Module-level init (database + scheduler) runs regardless of how this file
is imported, so both Gunicorn and python wsgi.py work correctly.
"""
import atexit
import logging
import os
import sys

from dotenv import load_dotenv

import database
import scheduler
from app import app

load_dotenv()

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "5000"))

# ── Module-level init (runs under both Gunicorn and python wsgi.py) ──────────
logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)
logger = logging.getLogger(__name__)

database.init_db()
scheduler.start_scheduler()
atexit.register(scheduler.stop_scheduler)

# ── Windows local server (Waitress) ─────────────────────────────────────────
if __name__ == "__main__":
    try:
        from waitress import serve
    except ImportError:
        logger.error("waitress not installed. Run: pip install waitress")
        sys.exit(1)

    logger.info("EconoWatch starting (Waitress) — http://%s:%d", HOST, PORT)
    serve(app, host=HOST, port=PORT, threads=4)
