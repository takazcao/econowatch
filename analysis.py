"""
analysis.py
-----------
Technical analysis engine for EconoWatch. Uses pandas-ta for indicator math
and generates buy/sell/hold signals with price targets and macro regime scoring.

Functions:
    find_levels(highs, lows, window) -> dict: Find support and resistance levels
    generate_analysis(ticker, period) -> dict | None: Full TA analysis for a ticker
    generate_macro_analysis() -> dict: Macro regime + asset class recommendation
"""
import logging
from datetime import date
from typing import Optional

import pandas as pd
import pandas_ta as ta
from dotenv import load_dotenv

import database

# ── Constants ────────────────────────────────────────
load_dotenv()
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
MIN_DATA_POINTS = 52  # need at least 52 rows for SMA50 + buffer

PERIOD_TO_DAYS = {
    "5d":  5,
    "1mo": 30,
    "3mo": 90,
    "6mo": 180,
    "1y":  365,
}

logger = logging.getLogger(__name__)


def find_levels(highs: list, lows: list, window: int = 60) -> dict:
    """
    Find support (rolling low) and resistance (rolling high) levels.

    Args:
        highs: List of daily high prices, oldest first.
        lows: List of daily low prices, oldest first.
        window: Number of recent days to consider. Defaults to 60.

    Returns:
        Dict with keys: support, resistance.
    """
    recent_highs = highs[-window:] if len(highs) >= window else highs
    recent_lows  = lows[-window:]  if len(lows)  >= window else lows

    return {
        "support":    round(min(recent_lows),  2),
        "resistance": round(max(recent_highs), 2),
    }


def _volume_vote(volumes: list, closes: list) -> tuple:
    """
    Compute a vote for volume trend by comparing 5-day vs 10-day average volume.

    Args:
        volumes: List of volume values, oldest first.
        closes: List of closing prices, oldest first.

    Returns:
        Tuple of (vote: int, trend_label: str).
    """
    if len(volumes) < 10 or len(closes) < 2:
        return 0, "neutral"

    avg5  = sum(volumes[-5:])  / 5
    avg10 = sum(volumes[-10:]) / 10
    rising = avg5 > avg10

    price_up = closes[-1] > closes[-5] if len(closes) >= 5 else closes[-1] > closes[-2]

    if rising and price_up:
        return 1, "rising"
    if rising and not price_up:
        return -1, "rising"
    return 0, "flat"


def _build_summary(
    ticker: str,
    signal: str,
    rsi: float,
    macd_data: dict,
    boll_data: dict,
    sma20,
    sma50,
    price: float,
    vol_trend: str = "neutral",
) -> str:
    """
    Generate a professional financial analyst summary paragraph.

    Follows standard TA interpretation: RSI zones, SMA cross trend,
    MACD momentum, Bollinger position, and volume trend.

    Args:
        ticker: The ticker symbol.
        signal: One of STRONG BUY, BUY, HOLD, SELL, STRONG SELL.
        rsi: RSI(14) value.
        macd_data: Dict from compute_macd().
        boll_data: Dict from compute_bollinger().
        sma20: 20-day SMA value or None.
        sma50: 50-day SMA value or None.
        price: Current close price.
        vol_trend: Volume trend label from _volume_vote().

    Returns:
        Professional 3-4 sentence summary string.
    """
    # Sentence 1 — asset + price + RSI
    if rsi < 30:
        rsi_desc = f"RSI(14) at {rsi:.1f} places the asset firmly in oversold territory, suggesting potential exhaustion of selling pressure."
    elif rsi > 70:
        rsi_desc = f"RSI(14) at {rsi:.1f} places the asset in overbought territory, indicating elevated risk of a near-term pullback."
    else:
        rsi_desc = f"RSI(14) at {rsi:.1f} sits in neutral territory, reflecting a balanced market without extreme momentum."

    sentence1 = f"{ticker} is currently trading at ${price:,.2f}. {rsi_desc}"

    # Sentence 2 — SMA cross trend
    if sma20 is not None and sma50 is not None:
        if sma20 > sma50:
            sentence2 = (
                f"The short-term SMA20 (${sma20:,.2f}) is trading above the long-term SMA50 (${sma50:,.2f}), "
                f"confirming a bullish trend structure with positive momentum continuation."
            )
        else:
            sentence2 = (
                f"The short-term SMA20 (${sma20:,.2f}) remains below the long-term SMA50 (${sma50:,.2f}), "
                f"signaling a bearish trend structure and continued downside pressure."
            )
    else:
        sentence2 = "Insufficient data to compute a reliable SMA crossover signal."

    # Sentence 3 — MACD + Bollinger
    hist = macd_data["histogram"]
    hist_sign = "+" if hist >= 0 else ""
    if hist > 0:
        macd_desc = f"positive ({hist_sign}{hist:.3f}), reinforcing bullish momentum"
    elif hist < 0:
        macd_desc = f"negative ({hist:.3f}), indicating bearish momentum"
    else:
        macd_desc = "flat (0.000), showing no directional momentum"

    pos_map = {
        "upper_extreme": "pressing the upper Bollinger Band extreme, a sign of strong but potentially overextended buying",
        "upper_third":   "in the upper third of the Bollinger Band, reflecting positive price momentum",
        "lower_extreme": "pressing the lower Bollinger Band extreme, suggesting aggressive selling and possible oversold conditions",
        "lower_third":   "in the lower third of the Bollinger Band, reflecting continued downside pressure",
        "middle":        "near the midpoint of the Bollinger Band, indicating a consolidation phase",
    }
    boll_desc = pos_map.get(boll_data["position"], "within normal Bollinger Band range")

    sentence3 = f"The MACD histogram is {macd_desc}, while price is {boll_desc}."

    # Sentence 4 — conclusion based on signal
    verdict_map = {
        "STRONG BUY":  "Strong alignment across all indicators points to robust upward momentum — conditions favor an aggressive long position.",
        "BUY":         "The majority of indicators lean bullish, suggesting a favorable risk/reward setup for initiating or adding to long positions.",
        "HOLD":        "Mixed signals across indicators suggest caution — no clear directional edge exists at current levels, and patience is advised.",
        "SELL":        "The majority of indicators lean bearish, suggesting that reducing exposure or initiating short positions may be warranted.",
        "STRONG SELL": "Strong bearish alignment across all indicators signals significant downside risk — defensive positioning is strongly advised.",
    }
    sentence4 = verdict_map.get(signal, "No clear directional bias at this time.")

    return f"{sentence1} {sentence2} {sentence3} {sentence4}"


def generate_analysis(ticker: str, period: str = "3mo") -> Optional[dict]:
    """
    Generate a full technical analysis for a ticker using data from the database.

    Computes RSI, SMA crossovers, MACD, Bollinger Bands, ATR, support/resistance,
    and produces a buy/sell/hold signal with confidence and price targets.

    Args:
        ticker: The stock ticker symbol (e.g. "AAPL").
        period: yfinance period string used to determine fetch window.
                One of: 5d, 1mo, 3mo, 6mo, 1y. Defaults to "3mo".

    Returns:
        Dict with full analysis result, or None if insufficient data.
    """
    # Always fetch at least 90 days for reliable indicator computation
    days = max(PERIOD_TO_DAYS.get(period, 90), 90)
    rows = database.get_stock_history(ticker, days)

    if len(rows) < MIN_DATA_POINTS:
        logger.warning(
            "Insufficient data for %s: got %d rows, need %d",
            ticker, len(rows), MIN_DATA_POINTS,
        )
        return None

    df_rows = [r for r in rows if r["close"] is not None]
    if len(df_rows) < MIN_DATA_POINTS:
        return None

    df = pd.DataFrame(df_rows)[["close", "high", "low", "volume"]].astype(float)
    closes  = df["close"].tolist()
    highs   = df["high"].tolist()
    lows    = df["low"].tolist()
    volumes = df["volume"].tolist()
    price   = closes[-1]

    # ── Compute indicators via pandas-ta ──────────────
    rsi_s   = ta.rsi(df["close"], length=14)
    sma20_s = ta.sma(df["close"], length=20)
    sma50_s = ta.sma(df["close"], length=50)
    macd_df = ta.macd(df["close"], fast=12, slow=26, signal=9)
    bb_df   = ta.bbands(df["close"], length=20, std=2)
    atr_s   = ta.atr(df["high"], df["low"], df["close"], length=14)

    def _safe(series, default, decimals=2):
        """Return the last non-NaN value from a Series, or default."""
        try:
            v = series.iloc[-1]
            return round(float(v), decimals) if pd.notna(v) else default
        except Exception:
            return default

    rsi   = _safe(rsi_s,   50.0, 2)
    sma20 = _safe(sma20_s, None, 2)
    sma50 = _safe(sma50_s, None, 2)
    atr   = _safe(atr_s,   0.0,  4)

    if macd_df is not None and not macd_df.empty:
        macd_val   = _safe(macd_df["MACD_12_26_9"],  0.0, 4)
        signal_val = _safe(macd_df["MACDs_12_26_9"], 0.0, 4)
        histogram  = _safe(macd_df["MACDh_12_26_9"], 0.0, 4)
        macd_trend = "bullish" if histogram > 0 else ("bearish" if histogram < 0 else "neutral")
    else:
        macd_val = signal_val = histogram = 0.0
        macd_trend = "neutral"
    macd_data = {"macd": macd_val, "signal_line": signal_val, "histogram": histogram, "trend": macd_trend}

    if bb_df is not None and not bb_df.empty:
        _bbu = next((c for c in bb_df.columns if c.startswith("BBU_")), None)
        _bbm = next((c for c in bb_df.columns if c.startswith("BBM_")), None)
        _bbl = next((c for c in bb_df.columns if c.startswith("BBL_")), None)
        _bbp = next((c for c in bb_df.columns if c.startswith("BBP_")), None)
        bb_upper  = _safe(bb_df[_bbu], 0.0, 2) if _bbu else 0.0
        bb_middle = _safe(bb_df[_bbm], 0.0, 2) if _bbm else 0.0
        bb_lower  = _safe(bb_df[_bbl], 0.0, 2) if _bbl else 0.0
        pct_b     = _safe(bb_df[_bbp], 0.5, 4) if _bbp else 0.5
    else:
        bb_upper = bb_middle = bb_lower = 0.0
        pct_b = 0.5

    if pct_b > 0.8:        bb_pos = "upper_extreme"
    elif pct_b > 0.6:      bb_pos = "upper_third"
    elif pct_b < 0.2:      bb_pos = "lower_extreme"
    elif pct_b < 0.4:      bb_pos = "lower_third"
    else:                  bb_pos = "middle"

    boll_data = {"upper": bb_upper, "middle": bb_middle, "lower": bb_lower,
                 "pct_b": pct_b, "position": bb_pos}

    levels = find_levels(highs, lows)
    vol_vote, vol_trend = _volume_vote(volumes, closes)

    # ── Score each indicator (-1, 0, +1) ─────────────
    rsi_vote = 1 if rsi < 40 else (-1 if rsi > 60 else 0)

    sma_vote  = 0
    sma_cross = "neutral"
    if sma20 is not None and sma50 is not None:
        if sma20 > sma50:
            sma_vote, sma_cross = 1, "bullish"
        elif sma20 < sma50:
            sma_vote, sma_cross = -1, "bearish"

    price_vs_sma20_vote = 0
    if sma20 is not None:
        price_vs_sma20_vote = 1 if price > sma20 else -1

    macd_vote = 1 if float(macd_data["histogram"]) > 0 else (-1 if float(macd_data["histogram"]) < 0 else 0)
    boll_vote = 1 if float(boll_data["pct_b"]) < 0.3 else (-1 if float(boll_data["pct_b"]) > 0.7 else 0)

    score     = rsi_vote + sma_vote + price_vs_sma20_vote + macd_vote + boll_vote + vol_vote
    max_score = 6

    # ── Determine signal ──────────────────────────────
    if score >= 5:
        signal = "STRONG BUY"
    elif score >= 2:
        signal = "BUY"
    elif score <= -5:
        signal = "STRONG SELL"
    elif score <= -2:
        signal = "SELL"
    else:
        signal = "HOLD"

    # Confidence: higher when more indicators agree on the same direction
    all_votes = [rsi_vote, sma_vote, macd_vote, boll_vote, vol_vote]
    nonzero = [v for v in all_votes if v != 0]
    all_agree = len(set(nonzero)) == 1 if nonzero else False
    base_confidence = round(abs(score) / max_score * 100)
    confidence = min(95, max(35, base_confidence + (10 if all_agree else 0)))

    # ── Price targets ─────────────────────────────────
    resistance   = levels["resistance"]
    support      = levels["support"]
    atr_cushion  = 2 * atr if atr > 0 else price * 0.05

    if signal in ("STRONG BUY", "BUY", "HOLD"):
        target_price = resistance
        stop_loss    = round(price - atr_cushion, 2)
    else:
        target_price = support
        stop_loss    = round(price + atr_cushion, 2)

    risk_reward = None
    denominator = abs(price - stop_loss)
    if denominator > 0:
        risk_reward = round(abs(target_price - price) / denominator, 2)

    summary = _build_summary(ticker, signal, rsi, macd_data, boll_data, sma20, sma50, price, vol_trend)

    return {
        "ticker":       ticker,
        "signal":       signal,
        "confidence":   confidence,
        "price":        round(price, 2),
        "target_price": round(target_price, 2),
        "stop_loss":    round(stop_loss, 2),
        "risk_reward":  risk_reward,
        "indicators": {
            "rsi": {
                "value": rsi,
                "zone":  "oversold" if rsi < 30 else ("overbought" if rsi > 70 else "neutral"),
                "vote":  rsi_vote,
            },
            "sma": {
                "sma20":  sma20,
                "sma50":  sma50,
                "cross":  sma_cross,
                "vote":   sma_vote,
            },
            "macd": {
                "value":       macd_data["macd"],
                "signal_line": macd_data["signal_line"],
                "histogram":   macd_data["histogram"],
                "trend":       macd_data["trend"],
                "vote":        macd_vote,
            },
            "bollinger": {
                "upper":    boll_data["upper"],
                "middle":   boll_data["middle"],
                "lower":    boll_data["lower"],
                "pct_b":    boll_data["pct_b"],
                "position": boll_data["position"],
                "vote":     boll_vote,
            },
            "volume": {
                "trend": vol_trend,
                "vote":  vol_vote,
            },
        },
        "summary":      summary,
        "period_used":  period,
        "data_points":  len(closes),
        "last_updated": date.today().isoformat(),
    }


# ── Macro Regime Analysis ─────────────────────────────────────────────────────

# Scoring rules: for each FRED series, what vote does a rising/falling trend cast
# for each asset class? (+1 = bullish, -1 = bearish, 0 = neutral)
_MACRO_RULES = {
    #  series_id        rising_votes                   falling_votes
    #                   stocks  gold  crypto            stocks  gold  crypto
    "CPIAUCSL":  {"up": (-1,    +1,    0),  "down": (+1,   -1,    0)},
    "PPIACO":    {"up": (-1,    +1,    0),  "down": (+1,   -1,    0)},
    "T10YIE":    {"up": (-1,    +1,   +1),  "down": (+1,   -1,   -1)},
    "FEDFUNDS":  {"up": (-1,    -1,   -1),  "down": (+1,   +1,   +1)},
    "DGS10":     {"up": (-1,    -1,   -1),  "down": (+1,   +1,   +1)},
    "DGS2":      {"up": (-1,    -1,   -1),  "down": (+1,   +1,   +1)},
    "UNRATE":    {"up": (-1,    +1,   -1),  "down": (+1,    0,   +1)},
    "GDPC1":     {"up": (+1,    -1,   +1),  "down": (-1,   +1,   -1)},
    "VIXCLS":    {"up": (-1,    +1,   -1),  "down": (+1,    0,   +1)},
    "M2SL":      {"up": (0,     +1,   +1),  "down": (0,    -1,   -1)},
    "MORTGAGE30US": {"up": (-1,  0,    0),  "down": (+1,    0,    0)},
    "DCOILWTICO":{"up": (-1,    +1,    0),  "down": (+1,   -1,    0)},
    # ── Dollar & Liquidity ────────────────────────────────────────────────────
    "DTWEXBGS":  {"up": (-1,    -1,   -1),  "down": (+1,   +1,   +1)},
    "WALCL":     {"up": (+1,    +1,   +1),  "down": (-1,   -1,   -1)},
    # ── Employment & Spending ─────────────────────────────────────────────────
    "PAYEMS":    {"up": (-1,    -1,   -1),  "down": (+1,   +1,   +1)},
    "RSXFS":     {"up": (+1,    -1,   +1),  "down": (-1,   +1,   -1)},
    # ── Credit Risk ───────────────────────────────────────────────────────────
    "BAMLH0A0HYM2": {"up": (-1, +1,  -1),  "down": (+1,   -1,   +1)},
    # ── Crypto Specific (CoinMarketCap) ───────────────────────────────────────
    "STABLECOIN_MCAP": {"up": (0,  0,   +1),  "down": (0,    0,   -1)},
    "BTC_DOMINANCE":   {"up": (0,  0,    0),  "down": (0,    0,    0)},
}

_IMPACT_LABELS = {
    #  series_id       trend   human reason + exact votes per asset
    "CPIAUCSL": {
        "up":   "Rising inflation → hedge demand lifts Gold (+1), erodes equity margins Stocks (-1), Crypto neutral (0)",
        "down": "Falling inflation → eases cost pressure, Stocks (+1) benefit, Gold (-1) loses appeal, Crypto neutral (0)",
    },
    "PPIACO": {
        "up":   "Rising producer prices → inflationary signal, Gold (+1), margin squeeze on Stocks (-1), Crypto neutral (0)",
        "down": "Falling producer prices → disinflationary, Stocks (+1) relief, Gold (-1) weakens, Crypto neutral (0)",
    },
    "T10YIE": {
        "up":   "Higher inflation expectations → Gold (+1) & Crypto (+1) as debasement hedges, Stocks (-1) pressured",
        "down": "Lower inflation expectations → Stocks (+1) favored, Gold (-1) & Crypto (-1) lose hedge premium",
    },
    "FEDFUNDS": {
        "up":   "Rising Fed rate → tightening liquidity, all assets pressured: Stocks (-1), Gold (-1), Crypto (-1)",
        "down": "Falling Fed rate → liquidity boost across all assets: Stocks (+1), Gold (+1), Crypto (+1)",
    },
    "DGS10": {
        "up":   "Higher 10Y yield → raises discount rate, Stocks (-1) & Gold (-1) less attractive, Crypto (-1) risk-off",
        "down": "Lower 10Y yield → Stocks (+1), Gold (+1) & Crypto (+1) all benefit from easing",
    },
    "DGS2": {
        "up":   "Higher 2Y yield → near-term rate pressure, Stocks (-1), Gold (-1), Crypto (-1) all impacted",
        "down": "Lower 2Y yield → easing signal, Stocks (+1), Gold (+1), Crypto (+1) all benefit",
    },
    "UNRATE": {
        "up":   "Rising unemployment → recession risk, Gold (+1) safe haven, Stocks (-1) & Crypto (-1) risk-off",
        "down": "Falling unemployment → growth signal, Stocks (+1) & Crypto (+1) benefit, Gold (0) neutral",
    },
    "GDPC1": {
        "up":   "GDP expanding → risk-on environment, Stocks (+1) & Crypto (+1) favored, Gold (-1) loses safe-haven bid",
        "down": "GDP contracting → recession risk, Gold (+1) safe haven, Stocks (-1) & Crypto (-1) under pressure",
    },
    "VIXCLS": {
        "up":   "Elevated volatility → risk-off, Gold (+1) safe haven, Stocks (-1) & Crypto (-1) sold off",
        "down": "Low volatility → risk-on appetite, Stocks (+1) & Crypto (+1) benefit, Gold (0) neutral",
    },
    "M2SL": {
        "up":   "Money supply expanding → monetary debasement, Gold (+1) & Crypto (+1) as hedges, Stocks (0) neutral",
        "down": "Money supply contracting → liquidity tightening, Gold (-1) & Crypto (-1) pressured, Stocks (0) neutral",
    },
    "MORTGAGE30US": {
        "up":   "Higher mortgage rates → economic drag, Stocks (-1) impacted, Gold (0) & Crypto (0) unaffected",
        "down": "Lower mortgage rates → economic stimulus, Stocks (+1) benefit, Gold (0) & Crypto (0) unaffected",
    },
    "DCOILWTICO": {
        "up":   "Rising oil → inflationary pressure, Gold (+1) hedge, Stocks (-1) cost squeeze, Crypto (0) neutral",
        "down": "Falling oil → deflationary relief, Stocks (+1) benefit, Gold (-1) loses inflation premium, Crypto (0) neutral",
    },
    "DTWEXBGS": {
        "up":   "Rising USD (DXY) → strong dollar pressures all risk assets & commodities: Stocks (-1), Gold (-1), Crypto (-1)",
        "down": "Falling USD (DXY) → weak dollar lifts risk assets & commodities: Stocks (+1), Gold (+1), Crypto (+1)",
    },
    "WALCL": {
        "up":   "Fed balance sheet expanding (QE) → liquidity injection favors all assets: Stocks (+1), Gold (+1), Crypto (+1)",
        "down": "Fed balance sheet shrinking (QT) → liquidity drain pressures all assets: Stocks (-1), Gold (-1), Crypto (-1)",
    },
    "PAYEMS": {
        "up":   "Hot NFP → strong labor market raises hawkish Fed fears: Stocks (-1), Gold (-1), Crypto (-1)",
        "down": "Weak NFP → labor softening may prompt Fed easing: Stocks (+1), Gold (+1), Crypto (+1)",
    },
    "RSXFS": {
        "up":   "Rising retail sales → strong consumer spending, risk-on: Stocks (+1) & Crypto (+1) favored, Gold (-1) loses safe-haven bid",
        "down": "Falling retail sales → consumer weakness, risk-off: Stocks (-1) & Crypto (-1) pressured, Gold (+1) safe haven",
    },
    "BAMLH0A0HYM2": {
        "up":   "Widening HY spreads → rising default risk, market stress: Stocks (-1), Gold (+1) safe haven, Crypto (-1)",
        "down": "Tightening HY spreads → credit confidence returning, risk-on: Stocks (+1), Gold (-1) loses safe-haven bid, Crypto (+1)",
    },
    "STABLECOIN_MCAP": {
        "up":   "Stablecoin market cap expanding → new liquidity entering crypto ecosystem: Crypto (+1), Stocks (0), Gold (0)",
        "down": "Stablecoin market cap shrinking → capital leaving crypto ecosystem: Crypto (-1), Stocks (0), Gold (0)",
    },
    "BTC_DOMINANCE": {
        "up":   "Rising BTC dominance → internal crypto flight to safety: capital rotating from Altcoins into Bitcoin (macro neutral: Stocks 0, Gold 0, Crypto 0)",
        "down": "Falling BTC dominance → altcoin season signal: capital rotating from Bitcoin into Altcoins (macro neutral: Stocks 0, Gold 0, Crypto 0)",
    },
}


def generate_macro_analysis() -> dict:
    """
    Analyze all economic indicators and produce a macro regime recommendation.

    Scores each FRED indicator as bullish/bearish for Stocks, Gold, and Crypto
    based on whether it is rising or falling. Detects the macro regime
    (Risk-On, Risk-Off, Inflationary, Recessionary, Mixed) and recommends
    the best asset class.

    Returns:
        Dict with scores, recommendation, regime, per-indicator breakdown,
        and a professional summary. Returns empty dict if no indicators in DB.
    """
    rows = database.get_indicators()
    if not rows:
        logger.warning("No economic indicators in DB for macro analysis")
        return {}

    scores = {"stocks": 0, "gold": 0, "crypto": 0}
    breakdown = []
    dgs10_val = None
    dgs2_val  = None

    for row in rows:
        sid   = row["series_id"]
        value = row["value"]
        prev  = row.get("prev_value")

        # Determine trend
        if prev is None or prev == 0:
            trend = "flat"
        elif value > prev:
            trend = "up"
        elif value < prev:
            trend = "down"
        else:
            trend = "flat"

        # Collect yield curve values for inversion check
        if sid == "DGS10":
            dgs10_val = value
        if sid == "DGS2":
            dgs2_val  = value

        # Apply scoring rules
        votes = (0, 0, 0)
        if sid in _MACRO_RULES and trend in ("up", "down"):
            votes = _MACRO_RULES[sid][trend]

        s_vote, g_vote, c_vote = votes
        scores["stocks"] += s_vote
        scores["gold"]   += g_vote
        scores["crypto"] += c_vote

        impact = _IMPACT_LABELS.get(sid, {}).get(trend, "Neutral — no clear directional signal")

        breakdown.append({
            "series_id":    sid,
            "name":         row["name"],
            "value":        round(value, 3),
            "unit":         row["unit"],
            "date":         row["date"],
            "trend":        trend,
            "impact":       impact,
            "stocks_vote":  s_vote,
            "gold_vote":    g_vote,
            "crypto_vote":  c_vote,
        })

    # Yield curve inversion check — strong recession signal
    yield_curve_inverted = False
    if dgs10_val is not None and dgs2_val is not None:
        if dgs2_val > dgs10_val:
            yield_curve_inverted = True
            scores["stocks"] -= 2
            scores["gold"]   += 2
            scores["crypto"] -= 2

    # ── Convert to 1–10 points based on actual indicator counts ─────────────
    # Formula: point = round((bullish_count / total_active) × 9 + 1)
    # bullish_count = indicators that gave +1 for this asset
    # total_active  = indicators that gave +1 or -1 (excludes flat/neutral 0s)
    # This makes the score directly readable: "6 of 9 active indicators bullish"

    vote_keys = {"stocks": "stocks_vote", "gold": "gold_vote", "crypto": "crypto_vote"}
    points = {}
    points_detail = {}

    for asset, vk in vote_keys.items():
        bullish = sum(1 for b in breakdown if b.get(vk, 0) == +1)
        bearish = sum(1 for b in breakdown if b.get(vk, 0) == -1)
        total_active = bullish + bearish

        if total_active == 0:
            pt = 5  # no data → neutral
        else:
            pt = max(1, min(10, round((bullish / total_active) * 9 + 1)))

        points[asset] = pt
        points_detail[asset] = {
            "bullish":      bullish,
            "bearish":      bearish,
            "neutral":      len(breakdown) - total_active,
            "total_active": total_active,
        }

    # Determine winner
    max_score = max(scores.values())
    min_score = min(scores.values())
    leaders   = [k for k, v in scores.items() if v == max_score]

    if len(leaders) == 1:
        recommendation = leaders[0].upper()
    else:
        recommendation = "MIXED"

    # Confidence: spread between top and bottom score
    spread     = max_score - min_score
    max_spread = len(_MACRO_RULES) * 2 + (4 if yield_curve_inverted else 0)
    confidence = min(95, max(30, round(spread / max(max_spread, 1) * 100)))

    # Detect macro regime
    inflation_trending_up = any(
        r["trend"] == "up" and r["series_id"] in ("CPIAUCSL", "PPIACO", "T10YIE")
        for r in breakdown
    )
    rates_rising = any(
        r["trend"] == "up" and r["series_id"] in ("FEDFUNDS", "DGS10")
        for r in breakdown
    )
    vix_row   = next((r for r in breakdown if r["series_id"] == "VIXCLS"), None)
    vix_high  = vix_row and vix_row["value"] > 25
    gdp_row   = next((r for r in breakdown if r["series_id"] == "GDPC1"), None)
    gdp_up    = gdp_row and gdp_row["trend"] == "up"

    if yield_curve_inverted or (vix_high and not gdp_up):
        regime = "Recessionary"
    elif inflation_trending_up and rates_rising:
        regime = "Stagflationary"
    elif inflation_trending_up:
        regime = "Inflationary"
    elif scores["stocks"] >= 3 and gdp_up:
        regime = "Risk-On"
    elif scores["gold"] >= 3 or vix_high:
        regime = "Risk-Off"
    else:
        regime = "Mixed / Transitional"

    # Build summary — use 1-10 points scale, reference key indicator drivers
    rec_name = {
        "STOCKS": "Equities (Stocks)",
        "GOLD":   "Gold (XAU/USD)",
        "CRYPTO": "Crypto",
        "MIXED":  "a diversified mix of assets",
    }.get(recommendation, recommendation)

    regime_desc = {
        "Recessionary":         "The macro environment shows recessionary signals",
        "Stagflationary":       "The macro environment is stagflationary",
        "Inflationary":         "The macro environment is inflationary",
        "Risk-On":              "The macro environment is risk-on with strong growth signals",
        "Risk-Off":             "The macro environment is defensive and risk-off",
        "Mixed / Transitional": "The macro environment is mixed with conflicting signals",
    }.get(regime, "The macro environment is unclear")

    # Find bullish drivers for the recommended asset (indicators that gave it +1)
    rec_key = recommendation.lower() if recommendation != "MIXED" else None
    vote_key_map = {"stocks": "stocks_vote", "gold": "gold_vote", "crypto": "crypto_vote"}
    bullish_drivers = []
    bearish_drivers = []
    if rec_key and rec_key in vote_key_map:
        vk = vote_key_map[rec_key]
        bullish_drivers = [b["name"] for b in breakdown if b.get(vk, 0) == +1]
        bearish_drivers = [b["name"] for b in breakdown if b.get(vk, 0) == -1]

    # Points line — consistent with the 1-10 visual, explains the count
    def _pt_line(asset: str) -> str:
        d = points_detail[asset]
        return f"{asset.capitalize()} {points[asset]}/10 ({d['bullish']}/{d['total_active']} indicators bullish)"

    points_line = f"Scores: {_pt_line('stocks')}, {_pt_line('gold')}, {_pt_line('crypto')}."

    # Driver sentence
    if rec_key and bullish_drivers:
        drivers_str = ", ".join(bullish_drivers[:3])
        driver_sentence = f"Key drivers for {rec_name}: {drivers_str} all scored bullish."
        if bearish_drivers:
            drag_str = ", ".join(bearish_drivers[:2])
            driver_sentence += f" Headwinds from {drag_str}."
    else:
        driver_sentence = ""

    inversion_note = (
        " The yield curve is inverted (2Y > 10Y), a historically reliable recession warning."
        if yield_curve_inverted else ""
    )

    if recommendation == "MIXED":
        advice = "No single asset class has a clear edge — diversification is advised."
    else:
        advice = f"{rec_name} scores highest ({points[rec_key]}/10) and presents the strongest macro setup."

    summary = " ".join(filter(None, [
        f"{regime_desc}.{inversion_note}",
        points_line,
        driver_sentence,
        advice,
    ]))

    # ── Capital Flow Allocation ──────────────────────────
    # Use raw net scores. Zero out negatives. Distribute 100% among positives.
    flow_raw   = {k: max(0, v) for k, v in scores.items()}
    flow_total = sum(flow_raw.values())

    if flow_total == 0:
        # All assets unfavorable — defensive environment
        flow_pct     = {"stocks": 33, "gold": 34, "crypto": 33}
        flow_verdict = (
            "All asset classes face macro headwinds. No clear rotation target — "
            "a defensive, cash-heavy posture is advised."
        )
    else:
        flow_pct = {k: round(v / flow_total * 100) for k, v in flow_raw.items()}
        # Fix rounding drift so percentages always sum to exactly 100
        diff = 100 - sum(flow_pct.values())
        if diff != 0:
            top_asset = max(flow_pct, key=flow_pct.get)
            flow_pct[top_asset] += diff

        _asset_names = {"stocks": "Equities", "gold": "Gold (XAU/USD)", "crypto": "Crypto"}
        dominant_key, dominant_pct = max(flow_pct.items(), key=lambda x: x[1])
        avoided = [k for k, v in flow_pct.items() if v == 0]
        strength = "strongly" if dominant_pct >= 70 else ("moderately" if dominant_pct >= 50 else "slightly")

        flow_verdict = (
            f"Smart Money is {strength} rotating into "
            f"{_asset_names[dominant_key]} ({dominant_pct}%) based on current macro conditions."
        )
        if avoided:
            avoid_str = " and ".join(_asset_names[a] for a in avoided)
            flow_verdict += f" Avoid {avoid_str} — macro environment is unfavorable."

    return {
        "regime":               regime,
        "recommendation":       recommendation,
        "confidence":           confidence,
        "scores":               scores,
        "points":               points,
        "points_detail":        points_detail,
        "yield_curve_inverted": yield_curve_inverted,
        "breakdown":            breakdown,
        "summary":              summary,
        "flow_pct":             flow_pct,
        "flow_verdict":         flow_verdict,
        "last_updated":         rows[0]["date"] if rows else None,
    }


def check_and_generate_alerts() -> None:
    """
    Evaluate all tracked tickers and macro indicators for alert conditions.
    Generates alerts for:
      - RSI < 30 (Oversold)
      - Bullish/Bearish SMA cross
      - Macro regime shifts

    Alerts are pushed to the database; uniqueness per day prevents spam.
    """
    logger.info("Starting alert condition evaluation...")

    # 1. Macro Regime Alert
    macro_data = generate_macro_analysis()
    if macro_data:
        regime = macro_data.get("regime", "")
        # Very simple daily alert if we detect a recessionary or stagflationary regime
        if regime in ("Recessionary", "Stagflationary"):
            msg = f"Macro Warning: Environment has shifted to {regime}. Defensive positioning advised."
            database.insert_alert("", "macro", msg)
        elif regime == "Risk-On":
            msg = "Macro Update: Environment is Risk-On. Favorable conditions for Equities and Crypto."
            database.insert_alert("", "macro", msg)

    # 2. Ticker Technical Alerts (RSI & SMA)
    watch_rows = database.get_watchlist()
    for w in watch_rows:
        ticker = w["ticker"]
        ta_result = generate_analysis(ticker, "3mo")
        if not ta_result:
            continue

        rsi = ta_result["indicators"]["rsi"]["value"]
        if rsi < 30:
            msg = f"{ticker} RSI is {rsi:.1f} (Oversold). Potential exhaustion of selling pressure."
            database.insert_alert(ticker, "rsi", msg)

        sma_cross = ta_result["indicators"]["sma"]["cross"]
        if sma_cross == "bullish":
            msg = f"{ticker} formed a Bullish SMA Cross (SMA20 > SMA50). Positive momentum."
            database.insert_alert(ticker, "sma", msg)
        elif sma_cross == "bearish":
            msg = f"{ticker} formed a Bearish SMA Cross (SMA20 < SMA50). Negative momentum."
            database.insert_alert(ticker, "sma", msg)

    logger.info("Finished alert evaluation.")


if __name__ == "__main__":
    import json
    logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)
    database.init_db()
    result = generate_analysis("AAPL", "3mo")
    if result:
        logger.info("Analysis result:\n%s", json.dumps(result, indent=2))
    else:
        logger.warning("No analysis result — not enough data in DB for AAPL")
