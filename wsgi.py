"""
wsgi.py
-------
Production entry point for EconoWatch using Waitress (Windows-compatible WSGI server).

Usage:
    python wsgi.py

Waitress serves on 0.0.0.0 so the dashboard is reachable from any device
on the local network at http://<your-ip>:5000
"""
import atexit
import logging
import os

from dotenv import load_dotenv
from waitress import serve

import database
import scheduler
from app import app

load_dotenv()

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "5000"))

if __name__ == "__main__":
    logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)
    logger = logging.getLogger(__name__)

    database.init_db()
    scheduler.start_scheduler()
    atexit.register(scheduler.stop_scheduler)

    logger.info("EconoWatch starting — http://%s:%d", HOST, PORT)
    logger.info("Local network access: http://<your-ip>:%d", PORT)
    serve(app, host=HOST, port=PORT, threads=4)
