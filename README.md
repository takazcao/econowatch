# EconoWatch — Financial Intelligence Dashboard

> A self-hosted, real-time financial and economic analysis platform built for investors, traders, financial advisors, and fintech businesses.

---

## Demo

[![EconoWatch Demo](https://img.youtube.com/vi/3EMv7s4qFuo/0.jpg)](https://youtu.be/3EMv7s4qFuo)

---

## What Is EconoWatch?

EconoWatch is a professional-grade financial dashboard that aggregates stock market data, macroeconomic indicators, technical analysis signals, and crypto market intelligence — all in a single web application that runs on your own server with zero per-user data costs.

Think of it as Bloomberg Terminal Lite — without the $24,000/year price tag.

In under 5 minutes, EconoWatch gives you:

- **Live candlestick charts** for any stock, ETF, index, or crypto pair
- **Technical analysis signals** (RSI, MACD, SMA cross, Bollinger Bands) with BUY / HOLD / SELL
- **Radar chart** — 6-axis visual overview of RSI, Trend, Momentum, Volume, Bollinger, and 52W Range
- **Macro regime detection** — is the economy Risk-On, Risk-Off, Stagflationary, or Recessionary?
- **Smart Money Rotation model** — which asset class (Stocks, Gold, or Crypto) the macro environment favors
- **19 economic indicators** pulled from the Federal Reserve (FRED)
- **Company fundamentals** — P/E, EPS, ROE, margins, earnings dates, dividends
- **Price alerts** — triggered when RSI crosses 30, SMA crosses, or macro regime shifts
- **Multi-ticker comparison** — overlay 2–3 tickers normalized to % return
- **S&P 100 Screener** — scan the top 100 stocks by signal strength
- **Portfolio Tracker** — track P&L across multiple positions
- **AI Chat** — ask Claude about any ticker or macro condition
- **AI Macro Summary** — auto-generated narrative for the current regime
- **Daily newsletter** — email report sent at 07:00 each morning
- **Print / PDF report** — one-click formatted export
- **CSV export** for offline analysis
- **Latest news** per ticker
- **Draggable dashboard layout** — GridStack.js powered, saved per browser
- **Dashboard PIN authentication** — lock the dashboard behind a PIN
- **FRED indicator overlay** on price charts
- **52-Week Range bar** on every ticker card

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

## Revenue Model

### Model 1: SaaS Subscription (Primary)

| Tier       | Price / month | Features                                                       |
| ---------- | ------------- | -------------------------------------------------------------- |
| Free       | $0            | 5 tickers, 1-month history, basic indicators                   |
| Pro        | $29           | Unlimited tickers, all indicators, TA signals, AI Chat, alerts |
| Advisor    | $99           | Multi-client watchlists, branded reports, API access           |
| Enterprise | Custom        | On-premise deployment, SSO, custom indicators                  |

**Target market size:** 15+ million self-directed retail investors in the US alone. Capturing 0.1% at $29/month = **$522,000 ARR** from a tiny slice of the market.

### Model 2: White-Label for Financial Advisors

- Setup fee: $2,000–$5,000 per firm
- Monthly license: $200–$500/firm
- Target: 10,000+ RIA firms in the US alone

### Model 3: API Access for Algorithmic Traders

- TA signals (RSI, MACD, SMA) are pre-computed and cached — marginal cost near zero
- Macro regime score refreshes hourly — high value, low compute cost
- **Revenue potential:** $49–$199/month per API subscriber

### Model 4: B2B Data Licensing

License the aggregated macro regime + capital flow model to hedge funds, financial media, and robo-advisors.

### Model 5: Financial Education

License as a teaching tool to universities and CFA/CFP training programs.

---

## Dashboard — 6 Tabs Explained

### Tab 1: Overview

The main working screen for active traders.

- **TradingView-quality candlestick chart** — OHLCV with SMA20, SMA50, Bollinger Band overlays
- **FRED indicator overlay** — toggle any of the 19 economic indicators directly on the price chart
- **52-Week Range bar** — shows where the current price sits between its 52W low and high
- **Period selector:** 5D / 1M / 3M / 6M / 1Y
- **Price summary card** — latest close, % change over period, data point count
- **Download CSV button** — export raw OHLCV data for any ticker and period
- **Compare chart** — enter 2–3 tickers and overlay them normalized to % return from start date
- **Latest News** — live news headlines per ticker with publisher and timestamp
- **Watchlist quick-pick** — one-click switching between tracked tickers (grouped: Stocks / ETFs / Crypto)
- **Draggable layout** — widgets are resizable and reorderable; layout saved in your browser

### Tab 2: Technical Analysis

Quantitative signal panel for a selected ticker.

- **Signal badge**: BUY / HOLD / SELL with confidence % and color-coded progress bar
- **Target price** (60-day resistance level)
- **Stop loss** (2× ATR from current price)
- **Risk / Reward ratio**
- **Radar chart** — 6-axis spider chart: RSI, Trend, Momentum, Volume, Bollinger Bands, 52W Range (all 0–100)
- **5 indicator cards:**
  - RSI (14) — value + Oversold / Neutral / Overbought zone
  - SMA Cross (20/50) — bullish / bearish cross with both MA values
  - MACD — line value, histogram, trend direction
  - Bollinger Bands — %B position, upper/lower band values
  - Volume — 5-day vs 10-day average trend

### Tab 3: Macro

Economic intelligence and regime detection.

- **19 Economic Indicator cards** — each shows latest value, unit, trend arrow, and date (CPI, Unemployment, Fed Funds Rate, 10Y Treasury, GDP, M2, VIX, WTI Oil, DXY, Non-Farm Payrolls, PPI, Retail Sales, Mortgage Rate, Breakeven Inflation, HY Credit Spreads, BTC Dominance, Stablecoin Market Cap, Fed Balance Sheet, and more)
- **Macro Regime Badge** — detected regime (color-coded)
- **AI Macro Summary** — LLM-generated plain-language analysis of the current macro environment
- **Bullish Score 1–10 gauge** for Stocks, Gold, and Crypto
- **Capital Flow Allocation donut chart** — % allocation to each asset class based on macro score
- **Smart Money Rotation verdict** — plain-language explanation of where capital should rotate
- **Yield Curve Inversion warning** — when 2Y yield > 10Y yield (recession indicator)
- **Indicator Breakdown table** — every indicator's vote (+1 / 0 / -1) for Stocks, Gold, Crypto

### Tab 4: Market

Breadth and momentum view.

- **Bitcoin Dominance chart** — BTC market share trend with interpretation
- **Stablecoin Market Cap chart** — crypto liquidity proxy
- **Top 5 Gainers table** — biggest movers from tracked universe today
- **Top 5 Losers table** — with clickable rows to load chart
- **Draggable layout** — all 4 widgets are resizable and reorderable

### Tab 5: Fundamentals

Company deep-dive for selected ticker.

- **Company**: Sector, Industry, Employees, Market Cap, Enterprise Value, 52W High/Low
- **Valuation**: Trailing P/E, Forward P/E, Price/Book, Trailing EPS, Forward EPS, Next Earnings Date
- **Financials**: Profit Margin, Operating Margin, ROE, ROA, Revenue Growth, Earnings Growth, Debt/Equity, Free Cash Flow, Dividend Yield, Annual Dividend

### Tab 6: Screener

Scan the S&P 100 by signal strength.

- Filter by signal: BUY / HOLD / SELL
- Sort by confidence %, bullish score, or change %
- Click any row to load that ticker in the main chart

---

## Portfolio Tracker

Track your actual positions and see live P&L.

- Add positions: ticker, shares, average cost
- Live P&L calculated from latest price data
- Total portfolio value and total gain/loss summary
- Positions persist in the database (no account required)

---

## AI Chat

Ask Claude (Anthropic) about any ticker or macro condition directly from the dashboard.

- Powered by Claude Haiku (fast, low-cost)
- Context-aware: automatically includes the current ticker being viewed
- Responds to questions like: "Is AAPL oversold?", "What does a Risk-Off regime mean for gold?", "Explain the yield curve inversion"
- Requires an Anthropic API key (set in Settings or `.env`)

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

## Daily Newsletter

EconoWatch sends a formatted HTML email report every morning at 07:00.

- Macro regime summary
- Top movers from the watchlist
- Any active alerts

Configure SMTP settings (host, port, sender, recipient) in the Settings page.

---

## Settings Page

Access via the gear icon (top right of the navbar).

- **FRED API Key** — your Federal Reserve data API key
- **Anthropic API Key** — for AI Chat and AI Macro Summary
- **SMTP settings** — for daily newsletter email delivery
- **Dashboard PIN** — lock the dashboard behind a PIN code
- Sensitive fields (API keys) are never echoed back to the page

---

## Print / PDF Report

Click the **Print Report** button in the navbar to generate a formatted, print-optimized view of the current dashboard state. Use your browser's Print → Save as PDF.

---

## Technical Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     BROWSER (Frontend)                       │
│  Bootstrap 5.3 dark theme + TradingView Lightweight Charts  │
│  Vanilla JS (no framework — fast, no build step required)   │
│  GridStack.js draggable layout, Chart.js radar chart        │
│  Tabs: Overview | Technical | Macro | Market | Fundamentals │
│  Auto-polls every 5 minutes (no page reload)                │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP JSON (fetch API)
┌──────────────────────────▼──────────────────────────────────┐
│                   FLASK API (Backend)                        │
│  Python 3.11 · Flask 3.x · Waitress WSGI (production)      │
│  REST endpoints — JSON responses                            │
│  Input validation on every route                            │
│  Global error handlers — no raw exceptions to client        │
│  Flask-Caching — reduces redundant API calls                │
└──────────┬───────────────────────────────┬──────────────────┘
           │ function calls                │ function calls
┌──────────▼────────────┐     ┌───────────▼──────────────────┐
│   ANALYSIS ENGINE     │     │      DATA LAYER               │
│   analysis.py         │     │  scraper.py   database.py     │
│   pandas-ta 0.4.71b0  │     │  yfinance     SQLite (WAL)    │
│   RSI/MACD/BB/SMA/ATR │     │  FRED API     CRUD functions  │
│   Macro regime scorer │     │  Retry logic  Parameterized   │
│   Alert generator     │     │  (tenacity)   SQL only        │
│   Radar chart data    │     │               Settings table  │
└──────────────────────┘     └───────────┬──────────────────┘
                                          │
┌─────────────────────────────────────────▼──────────────────┐
│                    BACKGROUND SCHEDULER                      │
│  APScheduler 3.10.4 · BackgroundScheduler                   │
│  Every 15 min: fetch all watchlist prices + run alerts      │
│  Every 60 min: fetch all 19 FRED indicators                 │
│  Daily 07:00: send newsletter email                         │
│  On startup: immediate fetch so first load has fresh data   │
└────────────────────────────────────────────────────────────┘
```

### Data Sources

| Source                     | What It Provides                                   | Cost |
| -------------------------- | -------------------------------------------------- | ---- |
| Yahoo Finance (yfinance)   | OHLCV price history for 100,000+ symbols worldwide | Free |
| FRED API (Federal Reserve) | 800,000+ US macroeconomic time series              | Free |
| yfinance `.info`           | Company fundamentals, earnings calendar            | Free |
| yfinance `.news`           | Latest news headlines per ticker                   | Free |

**Total data cost: $0/month**

### API Endpoints

| Method | Route                                   | Description                                      |
| ------ | --------------------------------------- | ------------------------------------------------ |
| GET    | `/api/stock/<ticker>?period=1mo`        | OHLCV + change % for any ticker                  |
| GET    | `/api/analysis/<ticker>?period=3mo`     | Full TA panel (RSI, MACD, BB, SMA, ATR, signal)  |
| GET    | `/api/radar/<ticker>`                   | 6-axis radar chart data                          |
| GET    | `/api/indicators`                       | Latest value for all 19 FRED indicators          |
| GET    | `/api/macro`                            | Macro regime, scores, flow allocation, breakdown |
| GET    | `/api/fundamentals/<ticker>`            | P/E, EPS, margins, dividends, earnings date      |
| GET    | `/api/movers`                           | Top 5 gainers and losers from watchlist          |
| GET    | `/api/compare?tickers=A,B,C&period=1mo` | Normalized % return for 2–3 tickers              |
| GET    | `/api/news/<ticker>`                    | Latest 5 news articles                           |
| GET    | `/api/export/<ticker>?period=1y`        | Download CSV of price history                    |
| GET    | `/api/alerts`                           | Unread price and macro alerts                    |
| POST   | `/api/alerts/read`                      | Mark all alerts read                             |
| GET    | `/api/search?q=<query>`                 | Validate ticker, return company name             |
| GET    | `/api/watchlist`                        | All tracked tickers                              |
| GET    | `/api/status`                           | Server uptime and last data update               |
| POST   | `/api/chat`                             | AI Chat (requires Anthropic API key)             |
| GET    | `/settings`                             | Settings page                                    |
| POST   | `/settings`                             | Save settings                                    |

### Database Schema

```sql
-- Price history for all tracked tickers
stocks (ticker, date, open, high, low, close, volume)

-- Economic indicator time series
economic_indicators (series_id, name, date, value, unit)

-- Tracked tickers
watchlist (ticker, name)

-- Price and macro alerts
alerts (ticker, alert_type, message, is_read, alert_date)

-- Portfolio positions
portfolio (ticker, shares, avg_cost)

-- Application settings (API keys stored here, not in plain text files)
settings (key, value)
```

### Technical Analysis Engine

Built on **pandas-ta 0.4.71b0** (908 indicators library):

| Indicator       | Parameters          | Signal Logic                      |
| --------------- | ------------------- | --------------------------------- |
| RSI             | 14-period           | < 40 bullish · > 60 bearish       |
| SMA Cross       | 20 / 50 period      | SMA20 > SMA50 = bullish           |
| Price vs SMA20  | —                   | Above = bullish · below = bearish |
| MACD            | 12/26/9             | Histogram > 0 = bullish           |
| Bollinger Bands | 20 period, 2σ       | %B position scoring               |
| Volume          | 5-day vs 10-day avg | Rising on up-days = bullish       |
| ATR             | 14-period           | Used for stop loss (2× ATR)       |

**Signal generation:** BUY if net score ≥ +3 · SELL if ≤ -3 · HOLD otherwise

### Macro Regime Engine

Scores 19 macroeconomic indicators against their trend direction. Each indicator votes +1 / 0 / -1 for Stocks, Gold, and Crypto. Regimes: **Risk-On · Risk-Off · Inflationary · Stagflationary · Recessionary · Mixed**

---

## Setup & Running

### Requirements

- Python 3.11+
- FRED API key — free at [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/api_key.html)
- Anthropic API key — free tier available at [console.anthropic.com](https://console.anthropic.com) (only needed for AI Chat)

### Installation

```bash
git clone https://github.com/takazcao/econowatch.git
cd econowatch
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
cp .env.example .env           # fill in your API keys
```

### Environment Variables

Copy `.env.example` to `.env` and fill in your values. The file lists every variable with a description. **Never commit your `.env` file — it is in `.gitignore`.**

Key variables:

| Variable            | Required | Description                                     |
| ------------------- | -------- | ----------------------------------------------- |
| `FRED_API_KEY`      | Yes      | Federal Reserve API key                         |
| `ANTHROPIC_API_KEY` | No       | Enables AI Chat and AI Macro Summary            |
| `SECRET_KEY`        | Yes      | Flask session secret (set a long random string) |
| `FLASK_DEBUG`       | No       | Set to `0` in production                        |

### Run (Development)

```bash
python app.py
# Dashboard at http://localhost:5000
```

### Run (Production — Local Network)

```bash
python wsgi.py
# Dashboard accessible from any device on your LAN
```

### Run (Docker)

```bash
cp .env.example .env   # fill in your API keys
docker compose up -d   # build image and start in background
# Dashboard at http://localhost:5000
```

The SQLite database is stored in `./data/` on your host machine and mounted into the container — it survives restarts and image rebuilds.

```bash
docker compose logs -f        # tail logs
docker compose down           # stop container
docker compose up -d --build  # rebuild after code changes
```

### Default Tracked Tickers (25)

**Stocks:** AAPL · MSFT · GOOGL · TSLA · AMZN · NVDA · META · JPM · BRK-B · V

**Indices & ETFs:** ^GSPC (S&P 500) · ^DJI (Dow) · ^IXIC (Nasdaq) · QQQ · SPY · GC=F (Gold) · SI=F (Silver) · CL=F (Crude Oil)

**Crypto:** BTC-USD · ETH-USD · BNB-USD · SOL-USD · XRP-USD · ADA-USD · DOGE-USD

You can add any ticker supported by Yahoo Finance directly from the dashboard search bar.

---

## Tech Stack

| Layer            | Technology                     | Version          |
| ---------------- | ------------------------------ | ---------------- |
| Backend          | Python / Flask                 | 3.11+ / 3.x      |
| WSGI Server      | Waitress                       | latest           |
| Database         | SQLite (WAL mode)              | built-in         |
| Scheduler        | APScheduler                    | 3.10.4           |
| Caching          | Flask-Caching                  | latest           |
| TA Engine        | pandas-ta                      | 0.4.71b0         |
| Data Fetching    | yfinance + requests            | latest           |
| Retry Logic      | tenacity                       | latest           |
| AI               | Anthropic Claude Haiku         | claude-haiku-4-5 |
| Frontend Charts  | TradingView Lightweight Charts | 4.1.3            |
| Radar Chart      | Chart.js                       | 4.4.2            |
| Frontend UI      | Bootstrap                      | 5.3.3            |
| Draggable Layout | GridStack.js                   | 10.3.1           |
| Environment      | python-dotenv                  | latest           |

---

## Competitive Comparison

| Feature                          | EconoWatch | Bloomberg Terminal | TradingView Pro | Yahoo Finance |
| -------------------------------- | ---------- | ------------------ | --------------- | ------------- |
| Stock charts                     | ✅         | ✅                 | ✅              | ✅            |
| Technical analysis signals       | ✅         | ✅                 | ✅              | ❌            |
| Radar chart (TA overview)        | ✅         | ❌                 | ❌              | ❌            |
| Macro regime detection           | ✅         | Manual             | ❌              | ❌            |
| Smart Money rotation model       | ✅         | ❌                 | ❌              | ❌            |
| Capital flow allocation          | ✅         | ❌                 | ❌              | ❌            |
| AI Chat (ask about any ticker)   | ✅         | ❌                 | ❌              | ❌            |
| S&P 100 Screener                 | ✅         | ✅                 | ✅              | ❌            |
| Portfolio tracker                | ✅         | ✅                 | ✅              | ✅            |
| Price alerts                     | ✅         | ✅                 | ✅              | ✅            |
| Daily email newsletter           | ✅         | ❌                 | ❌              | ❌            |
| FRED indicator overlay on charts | ✅         | ❌                 | ❌              | ❌            |
| 52-Week Range bar                | ✅         | ✅                 | ✅              | ✅            |
| Draggable dashboard layout       | ✅         | ❌                 | ❌              | ❌            |
| Print / PDF report               | ✅         | ✅                 | ✅              | ❌            |
| Company fundamentals             | ✅         | ✅                 | ✅              | ✅            |
| CSV export                       | ✅         | ✅                 | ✅              | Limited       |
| Self-hosted / data privacy       | ✅         | ❌                 | ❌              | ❌            |
| Monthly cost (data)              | **$0**     | **$2,000**         | **$60**         | **$0**        |
| Open / customizable              | ✅         | ❌                 | ❌              | ❌            |

---

## Roadmap

- [ ] User authentication (Flask-Login) — multi-user support
- [ ] Telegram alert delivery
- [ ] Backtesting engine — test TA strategies against historical data
- [ ] Sector rotation heatmap
- [ ] Options flow data integration
- [ ] Mobile PWA wrapper
- [ ] Multi-language support
- [ ] Customizable TA parameters (RSI period, SMA windows)
- [ ] White-label branding (custom logo + brand color via Settings)

---

## Security Notes

- API keys are stored in the SQLite `settings` table, not in source code
- The dashboard PIN is hashed before storage — the plain PIN is never saved
- All database queries use parameterized SQL — no SQL injection risk
- Set `SECRET_KEY` to a long random string in production (never use the default)
- Set `FLASK_DEBUG=0` in production
- For network exposure beyond localhost, put EconoWatch behind a reverse proxy (nginx / Caddy) with HTTPS

---

## License

MIT License — free to use, modify, and deploy commercially.

---

_EconoWatch — Built with Python, Flask, and free public financial data._
