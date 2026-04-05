"""
cache.py
--------
Shared Flask-Caching instance for the EconoWatch application.

Initialised without an app here so that both app.py and scraper.py can
import this module without creating a circular dependency.  app.py calls
cache.init_app(app) after the Flask app is configured.

Usage:
    # In app.py
    from cache import cache
    cache.init_app(app, config={"CACHE_TYPE": "SimpleCache"})

    # In scraper.py
    from cache import cache

    @cache.memoize(timeout=300)
    def _yfinance_history(ticker, period): ...
"""
from flask_caching import Cache

cache = Cache()
