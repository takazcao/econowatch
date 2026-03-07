# EconoWatch — Financial Intelligence Dashboard

> A self-hosted, real-time financial and economic analysis platform built for investors, traders, financial advisors, and fintech businesses.

---

## What Is EconoWatch?

EconoWatch is a professional-grade financial dashboard that aggregates stock market data, macroeconomic indicators, technical analysis signals, and crypto market intelligence — all in a single web application that runs on your own server with zero per-user data costs.

Think of it as Bloomberg Terminal Lite — without the $24,000/year price tag.

In under 5 minutes, EconoWatch gives you:

- **Live candlestick charts** for any stock, ETF, index, or crypto pair
- **Technical analysis signals** (RSI, MACD, SMA cross, Bollinger Bands) with BUY / HOLD / SELL
- **Macro regime detection** — is the economy Risk-On, Risk-Off, Stagflationary, or Recessionary?
- **Smart Money Rotation model** — which asset class (Stocks, Gold, or Crypto) the macro environment favors
- **19 economic indicators** pulled from the Federal Reserve (FRED)
- **Company fundamentals** — P/E, EPS, ROE, margins, earnings dates, dividends
- **Price alerts** — triggered when RSI crosses 30, SMA crosses, or macro regime shifts
- **Multi-ticker comparison** — overlay 2-3 tickers normalized to % return
- **CSV export** for offline analysis
- **Latest news** per ticker

---

## The Problem EconoWatch Solves

| Problem                                                        | How EconoWatch Solves It                                                |
| -------------------------------------------------------------- | ----------------------------------------------------------------------- |
| Bloomberg / Refinitiv terminals cost $20,000–$30,000/year      | EconoWatch costs $0 in data fees — built on free public APIs            |
| Investors switch between 5+ apps to get a full picture         | One dashboard — charts, macro, TA signals, fundamentals, news           |
| Macro analysis requires economics expertise                    | Automated regime scoring explains what the data means in plain language |
| Retail investors make emotional decisions                      | Quantified signals (1–10 bullish score) remove guesswork                |
| Financial advisors have no affordable client-facing dashboards | White-label ready, self-hosted, no per-seat data fees                   |

---

## Who Uses This

### 1. Retail Investors / Self-Directed Traders

People managing their own portfolios who want professional tools without a Bloomberg subscription.

### 2. Financial Advisors & Wealth Managers (RIAs)

Need to monitor client portfolios, explain macro conditions, and demonstrate analysis rigor to clients. EconoWatch gives them a branded dashboard they can show in client meetings.

### 3. Family Offices & Boutique Hedge Funds

Small funds that cannot justify Bloomberg costs but need macro regime intelligence and technical signals across multiple assets.

### 4. Finance Educators & Universities

Teaching investment analysis, financial modeling, or macro economics. EconoWatch gives students a live, hands-on tool.

### 5. Fintech Startups

Startups that need financial intelligence capabilities embedded in their products — use EconoWatch as the analytics engine.

---

## How to Make Money — Revenue Model

### Model 1: SaaS Subscription (Primary)

Deploy EconoWatch as a hosted web service. Charge users monthly.

| Tier       | Price / month | Features                                              |
| ---------- | ------------- | ----------------------------------------------------- |
| Free       | $0            | 5 tickers, 1-month history, basic indicators          |
| Pro        | $29           | Unlimited tickers, all indicators, TA signals, alerts |
| Advisor    | $99           | Multi-client watchlists, branded reports, API access  |
| Enterprise | Custom        | On-premise deployment, SSO, custom indicators         |

**Target market size:** 15+ million self-directed retail investors in the US alone. Capturing 0.1% at $29/month = **$522,000 ARR** from a tiny slice of the market.

---

### Model 2: White-Label for Financial Advisors

Sell EconoWatch as a branded client portal to Registered Investment Advisors (RIAs) and wealth management firms.

- Setup fee: $2,000–$5,000 per firm
- Monthly license: $200–$500/firm
- Target: 10,000+ RIA firms in the US alone

**Revenue potential:** 100 firms × $300/month = **$360,000 ARR**

---

### Model 3: API Access for Algorithmic Traders

Expose the TA signal engine and macro regime scores as a REST API.

- Traders pay per 1,000 API calls or monthly flat fee
- TA signals (RSI, MACD, SMA cross) are pre-computed and cached — marginal cost near zero
- Macro regime score refreshes hourly — high value, low compute cost

**Revenue potential:** $49–$199/month per API subscriber

---

### Model 4: B2B Data Licensing

License the aggregated macro regime + capital flow model to:

- Hedge funds
- Financial media (newsletter platforms, Substack writers)
- Robo-advisors that need a macro overlay

**Revenue potential:** $1,000–$10,000/month per enterprise client

---

### Model 5: Financial Education Platforms

License as a teaching tool:

- University finance departments
- CFA / CFP training programs
- Investment clubs

**Pricing:** $500–$2,000/year per institution

---

## Why This Idea Is Good

### 1. Near-Zero Data Cost

EconoWatch is built on **free public APIs**:

- **yfinance** — Yahoo Finance data (stocks, ETFs, crypto, futures, forex) — free
- **FRED API** — Federal Reserve economic data — free
- **No Bloomberg, no Refinitiv, no Quandl subscription required**

This means gross margins are extremely high. Every dollar of revenue above server costs is profit.

### 2. Defensible Moat — The Macro Intelligence Layer

The Macro Regime Analysis is not just a data display — it is an **automated economic interpretation engine**:

- Scores 19 indicators (CPI, unemployment, treasury yields, M2 money supply, VIX, credit spreads, GDP, oil, etc.)
- Detects regime: Risk-On / Risk-Off / Inflationary / Stagflationary / Recessionary
- Outputs capital flow allocation: which asset class (Stocks / Gold / Crypto) the data favors
- Generates a "Smart Money Rotation" narrative automatically

This kind of macro synthesis normally requires a team of economists. EconoWatch does it in seconds.

### 3. Self-Hosted = Data Privacy Selling Point

Regulated financial firms (RIAs, family offices) cannot send client data to third-party SaaS tools. EconoWatch runs on **their own server** — no client data ever leaves their infrastructure. This is a major compliance advantage.

### 4. No Per-Seat Licensing Trap

Unlike Bloomberg where each user pays $2,000/month, EconoWatch's cost is flat — one server, unlimited users. Financial advisory firms with 10 advisors pay the same as a firm with 1.

### 5. Network Effect via Watchlists

As users build their custom watchlists and alert configurations, switching cost increases. The longer they use it, the more embedded it becomes in their workflow.

---

## Dashboard — 5 Tabs Explained

### Tab 1: Overview

The main working screen for active traders.

- **TradingView-quality candlestick chart** — OHLCV with SMA20, SMA50, Bollinger Band overlays
- **Period selector:** 1D / 5D / 1W / 1M / 3M / 6M / 1Y
- **Price summary card** — latest close, % change over period, data point count
- **Download CSV button** — export raw OHLCV data for any ticker and period
- **Compare chart** — enter 2-3 tickers and overlay them normalized to % return from start date
- **Latest News** — live news headlines per ticker with publisher and timestamp
- **Watchlist quick-pick** — one-click switching between tracked tickers (grouped: Stocks / ETFs / Crypto)

### Tab 2: Technical Analysis

Quantitative signal panel for a selected ticker.

- **Signal badge**: BUY / HOLD / SELL with confidence % and color-coded progress bar
- **Target price** (60-day resistance level)
- **Stop loss** (2× ATR from current price)
- **Risk / Reward ratio**
- **5 indicator cards:**
  - RSI (14) — value + Oversold / Neutral / Overbought zone
  - SMA Cross (20/50) — bullish / bearish cross with both MA values
  - MACD — line value, histogram, trend direction
  - Bollinger Bands — %B position, upper/lower band values
  - Volume — 5-day vs 10-day average trend

### Tab 3: Macro

Economic intelligence and regime detection.

- **19 Economic Indicator cards** — each shows latest value, unit, trend arrow, and date
  - CPI Inflation, Unemployment Rate, Fed Funds Rate, 10Y Treasury, 2Y Treasury, GDP, M2 Money Supply, VIX, WTI Oil, DXY Dollar Index, Non-Farm Payrolls, PPI, Retail Sales, Mortgage Rate, Breakeven Inflation, HY Credit Spreads, BTC Dominance, Stablecoin Market Cap, Fed Balance Sheet
- **Macro Regime Badge** — detected regime (color-coded)
- **Bullish Score 1–10 gauge** for Stocks, Gold, and Crypto — pip bar visualization with count explanation
- **Capital Flow Allocation donut chart** — % allocation to each asset class based on macro score
- **Smart Money Rotation verdict** — plain-language explanation of where capital should rotate
- **Analysis Summary** — narrative describing key drivers
- **Yield Curve Inversion warning** — when 2Y yield > 10Y yield (recession indicator)
- **Indicator Breakdown table** — every indicator's vote (+1 / 0 / -1) for Stocks, Gold, Crypto with trend and impact description

### Tab 4: Market

Breadth and momentum view.

- **Bitcoin Dominance chart** — BTC market share trend with interpretation
- **Stablecoin Market Cap chart** — crypto liquidity proxy
- **Top 5 Gainers table** — biggest movers from tracked universe today
- **Top 5 Losers table** — with clickable rows to load chart

### Tab 5: Fundamentals

Company deep-dive for selected ticker.

- **Company**: Sector, Industry, Employees, Market Cap, Enterprise Value, 52W High/Low
- **Valuation**: Trailing P/E, Forward P/E, Price/Book, Trailing EPS, Forward EPS, Next Earnings Date
- **Financials**: Profit Margin, Operating Margin, ROE, ROA, Revenue Growth, Earnings Growth, Debt/Equity, Free Cash Flow, Dividend Yield, Annual Dividend

---

## Price Alert System

EconoWatch automatically monitors all tracked tickers and sends alerts when:

| Trigger                                | Alert                                                                                 |
| -------------------------------------- | ------------------------------------------------------------------------------------- |
| RSI < 30                               | "{TICKER} RSI is {value} (Oversold). Potential exhaustion of selling pressure."       |
| Bullish SMA cross                      | "{TICKER} formed a Bullish SMA Cross (SMA20 > SMA50). Positive momentum."             |
| Bearish SMA cross                      | "{TICKER} formed a Bearish SMA Cross (SMA20 < SMA50). Negative momentum."             |
| Macro = Stagflationary or Recessionary | "Macro Warning: Environment has shifted to {regime}. Defensive positioning advised."  |
| Macro = Risk-On                        | "Macro Update: Environment is Risk-On. Favorable conditions for Equities and Crypto." |

Alerts appear as a badge on the bell icon (top right). Click to view all unread alerts in a modal. Alerts de-duplicate per day — no spam.

---

## Technical Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     BROWSER (Frontend)                       │
│  Bootstrap 5.3 dark theme + TradingView Lightweight Charts  │
│  Vanilla JS (no framework — fast, no build step required)   │
│  Tabs: Overview | Technical | Macro | Market | Fundamentals │
│  Auto-polls every 5 minutes (no page reload)               │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP JSON (fetch API)
┌──────────────────────────▼──────────────────────────────────┐
│                   FLASK API (Backend)                        │
│  Python 3.11 · Flask 3.x · Waitress WSGI (production)      │
│  14 REST endpoints — JSON responses, no templates           │
│  Input validation on every route                            │
│  Global error handlers — no raw exceptions to client        │
└──────────┬───────────────────────────────┬──────────────────┘
           │ function calls                │ function calls
┌──────────▼────────────┐     ┌───────────▼──────────────────┐
│   ANALYSIS ENGINE     │     │      DATA LAYER               │
│   analysis.py         │     │  scraper.py   database.py     │
│   pandas-ta 0.4.71b0  │     │  yfinance     SQLite          │
│   RSI/MACD/BB/SMA/ATR │     │  FRED API     CRUD functions  │
│   Macro regime scorer │     │  Retry logic  Parameterized   │
│   Alert generator     │     │  (tenacity)   SQL only        │
└──────────────────────┘     └───────────┬──────────────────┘
                                          │
┌─────────────────────────────────────────▼──────────────────┐
│                    BACKGROUND SCHEDULER                      │
│  APScheduler 3.10.4 · BackgroundScheduler                   │
│  Every 15 min: fetch all watchlist prices + run alerts      │
│  Every 60 min: fetch all 19 FRED indicators                 │
│  On startup: immediate fetch so first load has fresh data   │
└────────────────────────────────────────────────────────────┘
```

### Data Sources

| Source                     | What It Provides                                   | Cost      |
| -------------------------- | -------------------------------------------------- | --------- |
| Yahoo Finance (yfinance)   | OHLCV price history for 100,000+ symbols worldwide | Free      |
| FRED API (Federal Reserve) | 800,000+ US macroeconomic time series              | Free      |
| CoinMarketCap              | BTC dominance, stablecoin market cap               | Free tier |
| yfinance `.info`           | Company fundamentals, earnings calendar            | Free      |
| yfinance `.news`           | Latest news headlines per ticker                   | Free      |

**Total data cost: $0/month**

### API Endpoints

| Method | Route                                   | Description                                      |
| ------ | --------------------------------------- | ------------------------------------------------ |
| GET    | `/api/stock/<ticker>?period=1mo`        | OHLCV + change % for any ticker                  |
| GET    | `/api/analysis/<ticker>?period=3mo`     | Full TA panel (RSI, MACD, BB, SMA, ATR, signal)  |
| GET    | `/api/indicators`                       | Latest value for all 19 FRED indicators          |
| GET    | `/api/macro`                            | Macro regime, scores, flow allocation, breakdown |
| GET    | `/api/fundamentals/<ticker>`            | P/E, EPS, margins, dividends, earnings date      |
| GET    | `/api/movers`                           | Top 5 gainers and losers from watchlist          |
| GET    | `/api/compare?tickers=A,B,C&period=1mo` | Normalized % return for 2-3 tickers              |
| GET    | `/api/news/<ticker>`                    | Latest 5 news articles                           |
| GET    | `/api/export/<ticker>?period=1y`        | Download CSV of price history                    |
| GET    | `/api/alerts`                           | Unread price and macro alerts                    |
| POST   | `/api/alerts/read`                      | Mark all alerts read                             |
| GET    | `/api/search?q=<query>`                 | Validate ticker, return company name             |
| GET    | `/api/watchlist`                        | All tracked tickers                              |
| GET    | `/api/status`                           | Server uptime and last data update               |

### Database Schema

```sql
-- Price history for all tracked tickers
stocks (ticker, date, open, high, low, close, volume) UNIQUE(ticker, date)

-- Economic indicator time series
economic_indicators (series_id, name, date, value, unit) UNIQUE(series_id, date)

-- Tracked tickers (default 25 + user additions)
watchlist (ticker, name)

-- Price and macro alerts
alerts (ticker, alert_type, message, is_read, alert_date) UNIQUE(ticker, alert_type, alert_date)
```

### Technical Analysis Engine

Built on **pandas-ta 0.4.71b0** (908 indicators library):

| Indicator       | Parameters          | Signal Logic                              |
| --------------- | ------------------- | ----------------------------------------- |
| RSI             | 14-period           | < 40 bullish · > 60 bearish               |
| SMA Cross       | 20 / 50 period      | SMA20 > SMA50 = bullish · below = bearish |
| Price vs SMA20  | —                   | Above = bullish · below = bearish         |
| MACD            | 12/26/9             | Histogram > 0 = bullish · < 0 = bearish   |
| Bollinger Bands | 20 period, 2σ       | %B position scoring                       |
| Volume          | 5-day vs 10-day avg | Rising on up-days = bullish               |
| ATR             | 14-period           | Used for stop loss calculation (2× ATR)   |

**Bullish Score:** `round((bullish_count / total_active) × 9 + 1)` → maps to 1–10

**Signal generation:**

- Count +1 / -1 votes across all indicators
- BUY if net score ≥ +3
- SELL if net score ≤ -3
- HOLD otherwise
- Confidence % = `abs(net_score) / total_indicators × 100`

### Macro Regime Engine

Scores 19 macroeconomic indicators against their trend direction. Each indicator has a predefined vote matrix:

| Indicator          | Trend   | Stocks Vote | Gold Vote | Crypto Vote |
| ------------------ | ------- | ----------- | --------- | ----------- |
| CPI (Inflation)    | Rising  | -1          | +1        | 0           |
| 10Y Treasury       | Rising  | -1          | -1        | -1          |
| DXY (Dollar Index) | Falling | +1          | +1        | +1          |
| M2 Money Supply    | Rising  | 0           | +1        | +1          |
| VIX (Volatility)   | Rising  | -1          | +1        | -1          |
| GDP Growth         | Rising  | +1          | -1        | +1          |
| Non-Farm Payrolls  | Falling | +1          | +1        | +1          |
| Fed Balance Sheet  | Rising  | +1          | +1        | +1          |
| HY Credit Spreads  | Rising  | -1          | +1        | -1          |
| ... 10 more        | ...     | ...         | ...       | ...         |

**Regime classification** — based on net scores for Stocks vs Gold vs Crypto:

- Risk-On · Risk-Off · Inflationary · Stagflationary · Recessionary · Mixed

**Capital Flow Allocation** — proportional % from raw positive scores:

```
flow_pct[asset] = max(0, score[asset]) / sum(positive_scores) × 100
```

---

## Setup & Running

### Requirements

- Python 3.11+
- FRED API key (free at https://fred.stlouisfed.org/docs/api/api_key.html)

### Installation

```bash
git clone https://github.com/takazcao/econowatch.git
cd econowatch
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
cp .env.example .env           # then add your FRED_API_KEY
```

### Run (Development)

```bash
python app.py
# Dashboard at http://localhost:5000
```

### Run (Production — Local Network)

```bash
python wsgi.py
# Dashboard at http://0.0.0.0:5000
# Accessible from any device on your LAN
```

### Default Tracked Tickers (25)

**Stocks:** AAPL · MSFT · GOOGL · TSLA · AMZN · NVDA · META · JPM · BRK-B · V

**Indices & ETFs:** ^GSPC (S&P 500) · ^DJI (Dow) · ^IXIC (Nasdaq) · QQQ · SPY · GC=F (Gold Spot) · SI=F (Silver Spot) · CL=F (Crude Oil)

**Crypto:** BTC-USD · ETH-USD · BNB-USD · SOL-USD · XRP-USD · ADA-USD · DOGE-USD

---

## Tech Stack

| Layer           | Technology                     | Version     |
| --------------- | ------------------------------ | ----------- |
| Backend         | Python / Flask                 | 3.11+ / 3.x |
| WSGI Server     | Waitress                       | latest      |
| Database        | SQLite                         | built-in    |
| Scheduler       | APScheduler                    | 3.10.4      |
| TA Engine       | pandas-ta                      | 0.4.71b0    |
| Data Fetching   | yfinance + requests            | latest      |
| Retry Logic     | tenacity                       | latest      |
| Frontend Charts | TradingView Lightweight Charts | 4.1.3       |
| Frontend UI     | Bootstrap                      | 5.3.3       |
| Environment     | python-dotenv                  | latest      |

---

## Competitive Comparison

| Feature                    | EconoWatch | Bloomberg Terminal | TradingView Pro | Yahoo Finance |
| -------------------------- | ---------- | ------------------ | --------------- | ------------- |
| Stock charts               | ✅         | ✅                 | ✅              | ✅            |
| Technical analysis signals | ✅         | ✅                 | ✅              | ❌            |
| Macro regime detection     | ✅         | Manual             | ❌              | ❌            |
| Smart Money rotation model | ✅         | ❌                 | ❌              | ❌            |
| Capital flow allocation    | ✅         | ❌                 | ❌              | ❌            |
| Price alerts               | ✅         | ✅                 | ✅              | ✅            |
| Company fundamentals       | ✅         | ✅                 | ✅              | ✅            |
| CSV export                 | ✅         | ✅                 | ✅              | Limited       |
| Self-hosted / data privacy | ✅         | ❌                 | ❌              | ❌            |
| Monthly cost (data)        | **$0**     | **$2,000**         | **$60**         | **$0**        |
| Open / customizable        | ✅         | ❌                 | ❌              | ❌            |

---

## Roadmap — Next Features

- [ ] User authentication (Flask-Login) — multi-user support
- [ ] Email / Telegram alert delivery
- [ ] Portfolio tracker — P&L across multiple positions
- [ ] Backtesting engine — test TA strategies against historical data
- [ ] AI market commentary — LLM-generated analysis narrative
- [ ] Sector rotation heatmap
- [ ] Options flow data integration
- [ ] Mobile app wrapper (PWA)
- [ ] Multi-language support

---

## License

MIT License — free to use, modify, and deploy commercially.

---

_EconoWatch — Built with Python, Flask, and free public financial data._
