"use strict";

// ── Constants ─────────────────────────────────────────
const PERIOD_MAP = {
  "1d": "1d",
  "5d": "5d",
  "1w": "1w",
  "1mo": "1mo",
  "3mo": "3mo",
  "6mo": "6mo",
  "1y": "1y",
};
const PERIOD_LABEL = {
  "1d": "1 Day",
  "5d": "5 Days",
  "1w": "1 Week",
  "1mo": "1 Month",
  "3mo": "3 Months",
  "6mo": "6 Months",
  "1y": "1 Year",
};
const REFRESH_INTERVAL_SEC = 300; // 5 minutes
const LS_LAST_TICKER = "ew_last_ticker"; // localStorage key
const LS_ACTIVE_TAB = "ew_active_tab"; // localStorage key
const LS_CUSTOM_WL = "ew_custom_watchlist"; // localStorage key
const LS_PORTFOLIO = "ew_portfolio_positions"; // localStorage key
const PORTFOLIO_COLORS = ["#58a6ff","#3fb950","#ffa657","#f85149","#bc8cff","#f6c343","#26a17b","#e3b341","#79c0ff","#56d364"];

// ── State ─────────────────────────────────────────────
let currentTicker = null;
let currentPeriod = "1mo";
let stockChart = null;
let refreshTimer = REFRESH_INTERVAL_SEC;
let refreshIntervalId = null;
let watchlistData = []; // [{ticker, name}]
let customWatchlist = []; // [{ticker, name}]
let acActiveIndex = -1; // autocomplete keyboard nav

// ── Helpers ───────────────────────────────────────────
function el(id) {
  return document.getElementById(id);
}

function show(id) {
  const e = el(id);
  if (e) e.style.display = "";
}
function hide(id) {
  const e = el(id);
  if (e) e.style.display = "none";
}
function showBlock(id) {
  const e = el(id);
  if (e) e.style.display = "block";
}

function fmtNum(n, decimals = 2) {
  if (n == null) return "—";
  return Number(n).toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function changeClass(pct) {
  if (pct == null) return "change-flat";
  return pct > 0 ? "change-up" : pct < 0 ? "change-down" : "change-flat";
}

function changeIcon(pct) {
  if (pct == null) return "";
  return pct > 0 ? "▲ " : pct < 0 ? "▼ " : "— ";
}

// ── Status ────────────────────────────────────────────
async function loadStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    if (data.status === "ok") {
      el("status-pill").innerHTML =
        '<i class="bi bi-circle-fill me-1" style="font-size:1rem;"></i>live';
      el("status-pill").style.background = "#1c2d1c";
      el("status-pill").style.color = "#3fb950";
      el("last-updated").textContent = "Updated: " + (data.last_updated || "—");
    }
  } catch (e) {
    el("status-pill").textContent = "offline";
    el("status-pill").style.color = "#f85149";
  }
}

// ── Watchlist Load & Quick-Pick ───────────────────────
const STOCK_TICKERS = new Set([
  "AAPL",
  "MSFT",
  "NVDA",
  "GOOGL",
  "AMZN",
  "META",
  "TSLA",
  "NFLX",
  "JPM",
  "V",
  "WMT",
]);
const CRYPTO_TICKERS = new Set(["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD"]);

async function loadWatchlist() {
  try {
    const res = await fetch("/api/watchlist");
    watchlistData = await res.json();

    // Load custom watchlist from local storage
    try {
      customWatchlist = JSON.parse(localStorage.getItem(LS_CUSTOM_WL) || "[]");
    } catch (e) {
      customWatchlist = [];
    }

    renderWatchlistPills();
  } catch (e) {
    console.error("Failed to load watchlist:", e);
    // non-fatal — autocomplete just won't pre-populate
  }
}

function ticketCategory(ticker) {
  if (CRYPTO_TICKERS.has(ticker)) return "crypto";
  if (STOCK_TICKERS.has(ticker)) return "stock";
  return "etf/index";
}

function renderWatchlistPills() {
  const stocks = watchlistData.filter((w) => STOCK_TICKERS.has(w.ticker));
  const etfs = watchlistData.filter(
    (w) => !STOCK_TICKERS.has(w.ticker) && !CRYPTO_TICKERS.has(w.ticker)
  );
  const crypto = watchlistData.filter((w) => CRYPTO_TICKERS.has(w.ticker));

  function makePill(item) {
    const div = document.createElement("div");
    div.className = "watchlist-pill";
    div.innerHTML = `<span class="ticker">${escHtml(item.ticker)}</span><span class="name">${escHtml(item.name)}</span>`;
    div.addEventListener("click", () => {
      el("search-input").value = item.ticker;
      el("search-feedback").innerHTML =
        `<span style="color:#3fb950;font-size:1rem;"><i class="bi bi-check-circle-fill me-1"></i>${escHtml(item.name)}</span>`;
      currentTicker = item.ticker;
      el("price-ticker-name").textContent =
        item.name + " (" + item.ticker + ")";
      loadChart(item.ticker, currentPeriod);
      closeAutocomplete();
    });
    return div;
  }

  ["wl-custom", "wl-stocks", "wl-etfs", "wl-crypto"].forEach(
    (id) => (el(id).innerHTML = "")
  );

  if (customWatchlist.length > 0) {
    show("wl-custom-container");
    customWatchlist.forEach((w) => el("wl-custom").appendChild(makePill(w)));
  } else {
    hide("wl-custom-container");
  }

  stocks.forEach((w) => el("wl-stocks").appendChild(makePill(w)));
  etfs.forEach((w) => el("wl-etfs").appendChild(makePill(w)));
  crypto.forEach((w) => el("wl-crypto").appendChild(makePill(w)));
}

// ── Autocomplete ──────────────────────────────────────
function getAcMatches(query) {
  if (!query) return watchlistData.slice(0, 8);
  const q = query.toUpperCase();
  return watchlistData
    .filter((w) => w.ticker.includes(q) || w.name.toUpperCase().includes(q))
    .slice(0, 8);
}

function renderAutocomplete(matches) {
  const list = el("autocomplete-list");
  if (!matches.length) {
    list.style.display = "none";
    return;
  }

  list.innerHTML = matches
    .map(
      (w, i) => `
        <div class="ac-item${i === acActiveIndex ? " active" : ""}" data-ticker="${escHtml(w.ticker)}" data-name="${escHtml(w.name)}">
            <span class="ac-ticker">${escHtml(w.ticker)}</span>
            <span class="ac-name">${escHtml(w.name)}</span>
            <span class="ac-category">${ticketCategory(w.ticker)}</span>
        </div>`
    )
    .join("");

  list.style.display = "block";

  list.querySelectorAll(".ac-item").forEach((item) => {
    item.addEventListener("mousedown", (e) => {
      e.preventDefault();
      selectTicker(item.dataset.ticker, item.dataset.name);
    });
  });
}

function closeAutocomplete() {
  el("autocomplete-list").style.display = "none";
  acActiveIndex = -1;
}

function selectTicker(ticker, name) {
  el("search-input").value = ticker;
  el("search-feedback").innerHTML =
    `<span style="color:#3fb950;font-size:1rem;"><i class="bi bi-check-circle-fill me-1"></i>${escHtml(name)}</span>`;
  currentTicker = ticker;
  el("price-ticker-name").textContent = name + " (" + ticker + ")";

  // Store selected name for custom watchlists
  el("search-input").dataset.lastName = name;

  loadChart(ticker, currentPeriod);
  closeAutocomplete();
}

el("search-input").addEventListener("input", () => {
  acActiveIndex = -1;
  const q = el("search-input").value.trim();
  renderAutocomplete(getAcMatches(q));
});

el("search-input").addEventListener("keydown", (e) => {
  const list = el("autocomplete-list");
  const items = list.querySelectorAll(".ac-item");

  if (e.key === "ArrowDown") {
    e.preventDefault();
    acActiveIndex = Math.min(acActiveIndex + 1, items.length - 1);
    renderAutocomplete(getAcMatches(el("search-input").value.trim()));
  } else if (e.key === "ArrowUp") {
    e.preventDefault();
    acActiveIndex = Math.max(acActiveIndex - 1, -1);
    renderAutocomplete(getAcMatches(el("search-input").value.trim()));
  } else if (e.key === "Escape") {
    closeAutocomplete();
  } else if (e.key === "Enter") {
    if (acActiveIndex >= 0 && items[acActiveIndex]) {
      const item = items[acActiveIndex];
      selectTicker(item.dataset.ticker, item.dataset.name);
    } else {
      handleSearch();
    }
  }
});

el("search-input").addEventListener("focus", () => {
  const q = el("search-input").value.trim();
  renderAutocomplete(getAcMatches(q));
});

document.addEventListener("click", (e) => {
  if (
    !el("search-input").contains(e.target) &&
    !el("autocomplete-list").contains(e.target)
  ) {
    closeAutocomplete();
  }
});

// ── Search ────────────────────────────────────────────
async function handleSearch() {
  const input = el("search-input").value.trim().toUpperCase();
  const fb = el("search-feedback");

  if (!input) return;

  closeAutocomplete();

  // Check watchlist first (instant, no API call)
  const local = watchlistData.find((w) => w.ticker === input);
  if (local) {
    selectTicker(local.ticker, local.name);
    return;
  }

  fb.innerHTML = '<span class="loading-spinner"></span>';

  try {
    const res = await fetch(`/api/search?q=${encodeURIComponent(input)}`);
    const data = await res.json();

    if (data.valid) {
      fb.innerHTML = `<span style="color:#3fb950;font-size:1rem;"><i class="bi bi-check-circle-fill me-1"></i>${escHtml(data.name)}</span>`;
      currentTicker = data.ticker;
      el("price-ticker-name").textContent =
        data.name + " (" + data.ticker + ")";
      el("search-input").dataset.lastName = data.name;
      loadChart(data.ticker, currentPeriod);
    } else {
      fb.innerHTML = `<span class="error-msg"><i class="bi bi-x-circle-fill me-1"></i>${escHtml(data.error || "Ticker not found")}</span>`;
    }
  } catch (e) {
    fb.innerHTML = `<span class="error-msg">Search failed. Try again.</span>`;
  }
}

el("search-btn").addEventListener("click", handleSearch);

// ── Period Tabs ───────────────────────────────────────
el("period-tabs").addEventListener("click", (e) => {
  const btn = e.target.closest("[data-period]");
  if (!btn) return;
  el("period-tabs")
    .querySelectorAll(".btn")
    .forEach((b) => b.classList.remove("active"));
  btn.classList.add("active");
  currentPeriod = btn.dataset.period;
  if (currentTicker) loadChart(currentTicker, currentPeriod);
});

// ── Chart ─────────────────────────────────────────────
async function loadChart(ticker, period) {
  // Persist last-viewed ticker across page refreshes
  localStorage.setItem(LS_LAST_TICKER, ticker);

  // Always bring the user to Overview so they can see the chart
  switchTab("overview");

  hide("chart-placeholder");
  showBlock("chart-wrapper");
  hide("chart-error");
  hide("price-placeholder");
  showBlock("price-summary");

  // Show loading state on chart
  el("chart-title").innerHTML =
    `<span class="loading-spinner me-2"></span> Loading ${ticker}…`;

  try {
    const res = await fetch(
      `/api/stock/${encodeURIComponent(ticker)}?period=${period}`
    );
    const data = await res.json();

    if (data.error || !data.labels) {
      throw new Error(data.error || "No data returned");
    }

    renderChart(data);
    updatePriceSummary(data, period);
    el("chart-title").textContent =
      `${ticker} — ${PERIOD_LABEL[period] || period}`;

    show("btn-star-ticker");
    updateStarIcon(ticker);

    loadAnalysis(ticker, period);
    loadFundamentals(ticker);
    loadNews(ticker);
  } catch (e) {
    hide("chart-wrapper");
    el("chart-error").textContent = "Error: " + e.message;
    showBlock("chart-error");
    el("chart-title").textContent = "Chart unavailable";
    hide("btn-star-ticker");
    hide("analysis-row");
    hide("fundamentals-row");
    hide("news-row");
  }
}

// ── Star Toggle ───────────────────────────────────────
function updateStarIcon(ticker) {
  const isStarred = customWatchlist.some((w) => w.ticker === ticker);
  const icon = el("star-icon");
  if (isStarred) {
    icon.className = "bi bi-star-fill";
  } else {
    icon.className = "bi bi-star";
  }
}

el("btn-star-ticker").addEventListener("click", () => {
  if (!currentTicker) return;

  const isStarred = customWatchlist.some((w) => w.ticker === currentTicker);

  if (isStarred) {
    // Remove from watchlist
    customWatchlist = customWatchlist.filter((w) => w.ticker !== currentTicker);
  } else {
    // Add to watchlist
    const nameNode =
      document.querySelector(".ac-item[data-ticker='" + currentTicker + "']") ||
      null;
    const fallbackName =
      el("search-input").dataset.lastName ||
      el("price-ticker-name").textContent.split(" (")[0];

    const nameToSave =
      watchlistData.find((w) => w.ticker === currentTicker)?.name ||
      fallbackName ||
      "Unknown";

    customWatchlist.push({ ticker: currentTicker, name: nameToSave });
  }

  localStorage.setItem(LS_CUSTOM_WL, JSON.stringify(customWatchlist));
  updateStarIcon(currentTicker);
  renderWatchlistPills();
});

// ── Chart TA Helpers ──────────────────────────────────
function computeSMA(values, period) {
  return values.map((_, i) => {
    if (i < period - 1) return null;
    const slice = values.slice(i - period + 1, i + 1).filter((v) => v != null);
    return slice.length === period
      ? Math.round((slice.reduce((a, b) => a + b, 0) / period) * 100) / 100
      : null;
  });
}

function computeBollinger(values, period = 20, mult = 2) {
  const sma = computeSMA(values, period);
  return values.map((_, i) => {
    if (sma[i] == null) return { upper: null, lower: null };
    const slice = values.slice(i - period + 1, i + 1).filter((v) => v != null);
    if (slice.length < period) return { upper: null, lower: null };
    const variance =
      slice.reduce((a, b) => a + Math.pow(b - sma[i], 2), 0) / period;
    const std = Math.sqrt(variance);
    return {
      upper: Math.round((sma[i] + mult * std) * 100) / 100,
      lower: Math.round((sma[i] - mult * std) * 100) / 100,
    };
  });
}

function renderChart(data) {
  // Destroy previous chart instance
  if (stockChart) {
    stockChart.remove();
    stockChart = null;
  }

  const chartEl = el("tv-chart");
  chartEl.innerHTML = "";

  const chart = LightweightCharts.createChart(chartEl, {
    width: chartEl.clientWidth || 600,
    height: 300,
    layout: {
      background: { color: "#161b22" },
      textColor: "#8b949e",
    },
    grid: {
      vertLines: { color: "#21262d" },
      horzLines: { color: "#21262d" },
    },
    crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
    rightPriceScale: { borderColor: "#30363d" },
    timeScale: {
      borderColor: "#30363d",
      timeVisible: true,
    },
  });

  stockChart = chart;

  const hasCandleData =
    Array.isArray(data.opens) &&
    Array.isArray(data.highs) &&
    Array.isArray(data.lows);

  if (hasCandleData) {
    // ── Candlestick series ──────────────────────────
    const candleSeries = chart.addCandlestickSeries({
      upColor: "#3fb950",
      downColor: "#f85149",
      borderUpColor: "#3fb950",
      borderDownColor: "#f85149",
      wickUpColor: "#3fb950",
      wickDownColor: "#f85149",
    });

    const candleData = data.labels
      .map((date, i) => ({
        time: date,
        open: data.opens[i] ?? data.prices[i],
        high: data.highs[i] ?? data.prices[i],
        low: data.lows[i] ?? data.prices[i],
        close: data.prices[i],
      }))
      .filter((d) => d.close != null);

    candleSeries.setData(candleData);

    // ── SMA20 overlay ───────────────────────────────
    const sma20vals = computeSMA(data.prices, 20);
    const sma20Series = chart.addLineSeries({
      color: "#58a6ff",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });
    const sma20Data = data.labels
      .map((date, i) => ({ time: date, value: sma20vals[i] }))
      .filter((d) => d.value != null);
    if (sma20Data.length) sma20Series.setData(sma20Data);

    // ── SMA50 overlay ───────────────────────────────
    const sma50vals = computeSMA(data.prices, 50);
    const sma50Series = chart.addLineSeries({
      color: "#d29922",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });
    const sma50Data = data.labels
      .map((date, i) => ({ time: date, value: sma50vals[i] }))
      .filter((d) => d.value != null);
    if (sma50Data.length) sma50Series.setData(sma50Data);

    // ── Bollinger Bands ─────────────────────────────
    const bbVals = computeBollinger(data.prices, 20);
    const bbLineOpts = {
      color: "rgba(88,166,255,0.45)",
      lineWidth: 1,
      lineStyle: LightweightCharts.LineStyle.Dashed,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    };
    const bbUpperSeries = chart.addLineSeries(bbLineOpts);
    const bbLowerSeries = chart.addLineSeries(bbLineOpts);

    const bbUpperData = data.labels
      .map((date, i) => ({ time: date, value: bbVals[i].upper }))
      .filter((d) => d.value != null);
    const bbLowerData = data.labels
      .map((date, i) => ({ time: date, value: bbVals[i].lower }))
      .filter((d) => d.value != null);
    if (bbUpperData.length) bbUpperSeries.setData(bbUpperData);
    if (bbLowerData.length) bbLowerSeries.setData(bbLowerData);

    // ── Legend ──────────────────────────────────────
    const legend = el("chart-legend");
    legend.innerHTML = `
            <span><span style="display:inline-block;width:14px;height:2px;background:#58a6ff;vertical-align:middle;"></span> SMA20</span>
            <span><span style="display:inline-block;width:14px;height:2px;background:#d29922;vertical-align:middle;"></span> SMA50</span>
            <span><span style="display:inline-block;width:14px;height:1px;border-top:2px dashed rgba(88,166,255,0.6);vertical-align:middle;"></span> BB(20)</span>
        `;
    legend.style.display = "flex";
  } else {
    // ── Fallback: area chart ────────────────────────
    const prices = data.prices;
    const isPositive =
      prices.length >= 2 && prices[prices.length - 1] >= prices[0];
    const areaSeries = chart.addAreaSeries({
      lineColor: isPositive ? "#3fb950" : "#f85149",
      topColor: isPositive ? "rgba(63,185,80,0.15)" : "rgba(248,81,73,0.15)",
      bottomColor: isPositive ? "rgba(63,185,80,0.0)" : "rgba(248,81,73,0.0)",
      lineWidth: 2,
    });
    const lineData = data.labels
      .map((date, i) => ({ time: date, value: data.prices[i] }))
      .filter((d) => d.value != null);
    areaSeries.setData(lineData);
    el("chart-legend").style.display = "none";
  }

  chart.timeScale().fitContent();

  // Responsive resize
  const ro = new ResizeObserver(() => {
    chart.applyOptions({ width: chartEl.clientWidth });
  });
  ro.observe(chartEl);
}

function updatePriceSummary(data, period) {
  el("price-latest").textContent =
    data.latest_close != null ? "$" + fmtNum(data.latest_close) : "—";

  const pct = data.change_pct;
  const badge = el("price-change");
  badge.textContent =
    pct != null ? changeIcon(pct) + fmtNum(Math.abs(pct)) + "%" : "—";
  badge.className = "change-badge " + changeClass(pct);

  el("price-period").textContent = PERIOD_LABEL[period] || period;
  el("price-points").textContent = data.labels ? data.labels.length : "—";

  const csvBtn = el("csv-download-btn");
  if (csvBtn && data.ticker) {
    csvBtn.href = `/api/export/${encodeURIComponent(data.ticker)}?period=${period}`;
    csvBtn.style.display = "";
  }
}

// ── Indicators ────────────────────────────────────────
async function loadIndicators() {
  try {
    const res = await fetch("/api/indicators");
    const data = await res.json();

    hide("indicators-placeholder");

    if (data.error || !data.indicators) {
      el("indicators-error").textContent = data.error || "No indicator data.";
      showBlock("indicators-error");
      return;
    }

    const grid = el("indicators-grid");
    grid.innerHTML = "";

    data.indicators.forEach((ind) => {
      const trendIcon =
        ind.trend === "up" ? "▲" : ind.trend === "down" ? "▼" : "—";
      const trendCls = "trend-" + ind.trend;
      const col = document.createElement("div");
      col.className = "col-6 col-md-4 col-xl-3";
      col.innerHTML = `
                <div class="card indicator-card h-100" style="background:#0d1117;">
                    <div class="card-body py-3 px-3">
                        <div class="text-muted mb-1" style="font-size:1rem;text-transform:uppercase;letter-spacing:0.05em;">
                            ${escHtml(ind.name)}
                        </div>
                        <div class="d-flex align-items-end gap-2">
                            <span class="value">${fmtNum(ind.value, 1)}</span>
                            <span class="unit pb-1">${escHtml(ind.unit)}</span>
                            <span class="${trendCls} pb-1 ms-auto fw-bold">${trendIcon}</span>
                        </div>
                        <div class="text-muted mt-1" style="font-size:1rem;">${escHtml(ind.date)}</div>
                    </div>
                </div>`;
      grid.appendChild(col);
    });
  } catch (e) {
    hide("indicators-placeholder");
    el("indicators-error").textContent = "Failed to load indicators.";
    showBlock("indicators-error");
  }
}

// ── Movers ────────────────────────────────────────────
async function loadMovers() {
  try {
    const res = await fetch("/api/movers");
    const data = await res.json();

    renderMovers("gainers", data.gainers || [], true);
    renderMovers("losers", data.losers || [], false);
  } catch (e) {
    console.error("Movers fetch error:", e);
    hide("gainers-loading");
    hide("losers-loading");
    const msg = "Failed to load movers: " + (e.message || "Unknown error");
    el("gainers-error").textContent = msg;
    el("losers-error").textContent = msg;
    showBlock("gainers-error");
    showBlock("losers-error");
  }
}

function renderMovers(type, rows, isGain) {
  hide(type + "-loading");

  if (!rows.length) {
    el(type + "-error").textContent =
      "No significant " + type + " found in watchlist history.";
    showBlock(type + "-error");
    return;
  }

  const tbody = el(type + "-body");
  tbody.innerHTML = rows
    .map((r) => {
      const pct = r.change_pct;
      const cls = isGain ? "trend-up" : "trend-down";
      const icon = isGain ? "▲" : "▼";
      return `<tr>
            <td><span class="ticker-badge">${escHtml(r.ticker)}</span></td>
            <td style="max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;"
                title="${escHtml(r.name)}">${escHtml(r.name)}</td>
            <td class="text-end">$${fmtNum(r.close)}</td>
            <td class="text-end ${cls}">${icon} ${fmtNum(Math.abs(pct))}%</td>
        </tr>`;
    })
    .join("");

  show(type + "-table");
}

// ── Macro Regime Analysis ─────────────────────────────
async function loadMacro() {
  show("macro-loading");
  try {
    const res = await fetch("/api/macro");
    const data = await res.json();
    hide("macro-loading");

    if (data.error) {
      el("macro-error").textContent = data.error;
      showBlock("macro-error");
      hide("macro-placeholder");
      return;
    }

    renderMacro(data);
  } catch (e) {
    hide("macro-loading");
    el("macro-error").textContent = "Failed to load macro analysis.";
    showBlock("macro-error");
    hide("macro-placeholder");
  }
}

function renderFlowDonut(svgEl, vals, colors, labels) {
  // Pure SVG donut — no Chart.js dependency
  const cx = 60,
    cy = 60,
    r = 46,
    innerR = 30;
  const total = vals.reduce((a, b) => a + b, 0) || 1;
  let startAngle = -Math.PI / 2; // start at 12 o'clock

  function polarToXY(angle, radius) {
    return {
      x: cx + radius * Math.cos(angle),
      y: cy + radius * Math.sin(angle),
    };
  }

  function arcPath(startAng, endAng, radius, inner) {
    const s = polarToXY(startAng, radius);
    const e = polarToXY(endAng, radius);
    const si = polarToXY(startAng, inner);
    const ei = polarToXY(endAng, inner);
    const large = endAng - startAng > Math.PI ? 1 : 0;
    return [
      `M ${s.x} ${s.y}`,
      `A ${radius} ${radius} 0 ${large} 1 ${e.x} ${e.y}`,
      `L ${ei.x} ${ei.y}`,
      `A ${inner} ${inner} 0 ${large} 0 ${si.x} ${si.y}`,
      "Z",
    ].join(" ");
  }

  let paths = "";
  vals.forEach((v, i) => {
    if (v <= 0) return;
    const sweep = (v / total) * 2 * Math.PI;
    // SVG arcs cannot draw a full circle (start === end point); split into two halves
    if (sweep >= 2 * Math.PI - 0.001) {
      const mid = startAngle + Math.PI;
      paths += `<path d="${arcPath(startAngle, mid, r, innerR)}" fill="${colors[i]}99" stroke="${colors[i]}" stroke-width="1.5"/>`;
      paths += `<path d="${arcPath(mid, startAngle + 2 * Math.PI - 0.001, r, innerR)}" fill="${colors[i]}99" stroke="${colors[i]}" stroke-width="1.5"/>`;
    } else {
      const endAngle = startAngle + sweep;
      paths += `<path d="${arcPath(startAngle, endAngle, r, innerR)}" fill="${colors[i]}99" stroke="${colors[i]}" stroke-width="1.5"/>`;
      startAngle = endAngle;
    }
  });

  // Center text: dominant allocation
  const maxIdx = vals.indexOf(Math.max(...vals));
  const centerText = `<text x="60" y="57" text-anchor="middle" font-size="16" font-weight="700" fill="${colors[maxIdx]}">${vals[maxIdx]}%</text>
        <text x="60" y="72" text-anchor="middle" font-size="12" fill="#8b949e">${labels[maxIdx]}</text>`;

  svgEl.innerHTML = paths + centerText;
}

function renderMacro(data) {
  hide("macro-placeholder");

  // Regime badge
  const regimeColors = {
    "Risk-On": ["#1a3d1a", "#3fb950"],
    "Risk-Off": ["#3d1a1a", "#f85149"],
    Inflationary: ["#3d2e00", "#d29922"],
    Stagflationary: ["#3d1a00", "#ffa657"],
    Recessionary: ["#2d1a2d", "#bc8cff"],
    "Mixed / Transitional": ["#1c2128", "#8b949e"],
  };
  const [bgCol, txtCol] = regimeColors[data.regime] || ["#1c2128", "#8b949e"];
  const badge = el("macro-regime-badge");
  badge.textContent = data.regime;
  badge.style.background = bgCol;
  badge.style.color = txtCol;
  badge.style.border = `1px solid ${txtCol}`;
  badge.style.fontSize = "0.75rem";
  show("macro-regime-badge");

  // Best asset
  const assetIcons = { STOCKS: "📈", GOLD: "🥇", CRYPTO: "₿", MIXED: "⚖️" };
  const assetColors = {
    STOCKS: "#58a6ff",
    GOLD: "#d29922",
    CRYPTO: "#bc8cff",
    MIXED: "#8b949e",
  };
  const rec = data.recommendation;
  const assetEl = el("macro-best-asset");
  assetEl.textContent = (assetIcons[rec] || "") + " " + rec;
  assetEl.style.color = assetColors[rec] || "#e6edf3";
  el("macro-confidence").textContent = `Confidence: ${data.confidence}%`;

  // 1–10 Point Gauges
  const points = data.points;
  const gaugeItems = [
    { label: "Stocks", key: "stocks", icon: "📈", baseColor: "#58a6ff" },
    { label: "Gold", key: "gold", icon: "🥇", baseColor: "#d29922" },
    { label: "Crypto", key: "crypto", icon: "₿", baseColor: "#bc8cff" },
  ];

  function pointColor(p) {
    if (p >= 7) return "#3fb950";
    if (p >= 4) return "#d29922";
    return "#f85149";
  }
  function pointLabel(p) {
    if (p >= 8) return "Very Bullish";
    if (p >= 7) return "Bullish";
    if (p >= 4) return "Neutral";
    if (p >= 2) return "Bearish";
    return "Very Bearish";
  }

  const detail = data.points_detail;
  el("macro-score-bars").innerHTML = gaugeItems
    .map((b) => {
      const pt = points[b.key];
      const col = pointColor(pt);
      const lbl = pointLabel(pt);
      const d = detail[b.key];

      const explain =
        `${d.bullish} of ${d.total_active} active indicators bullish` +
        ` (${d.bearish} bearish, ${d.neutral} neutral)`;

      const pips = Array.from({ length: 10 }, (_, i) => {
        const filled = i + 1 <= pt;
        return `<div style="flex:1; height:10px; background:${filled ? col : "#21262d"}; border-radius:2px; margin:0 1px;"></div>`;
      }).join("");

      return `<div class="mb-3">
            <div class="d-flex align-items-center justify-content-between mb-1">
                <div style="font-size:1rem; font-weight:600; color:#e6edf3;">${b.icon} ${b.label}</div>
                <div class="d-flex align-items-center gap-2">
                    <span style="font-size:1rem; color:${col};">${lbl}</span>
                    <span style="font-size:1.2rem; font-weight:700; color:${col}; min-width:24px; text-align:right;">${pt}</span>
                    <span style="font-size:1rem; color:#8b949e;">/ 10</span>
                </div>
            </div>
            <div class="d-flex mb-1" style="height:10px;">${pips}</div>
            <div style="font-size:1rem; color:#8b949e;">${explain}</div>
        </div>`;
    })
    .join("");

  // Capital Flow Donut
  if (data.flow_pct) {
    const fp = data.flow_pct;
    const labels = ["Stocks", "Gold", "Crypto"];
    const vals = [fp.stocks, fp.gold, fp.crypto];
    const colors = ["#58a6ff", "#d29922", "#bc8cff"];

    el("flow-verdict").textContent = data.flow_verdict || "";

    el("flow-pct-labels").innerHTML = labels
      .map(
        (lbl, i) =>
          `<div style="text-align:center; min-width:60px;">
                <div style="font-size:1.3rem; font-weight:700; color:${colors[i]};">${vals[i]}%</div>
                <div style="font-size:1rem; color:#8b949e;">${lbl}</div>
            </div>`
      )
      .join("");

    renderFlowDonut(el("flow-donut"), vals, colors, labels);
  }

  // Summary
  el("macro-summary").textContent = data.summary;

  // Yield curve warning
  if (data.yield_curve_inverted) {
    show("macro-yield-warning");
  }

  // Breakdown table
  const voteIcon = (v) =>
    v > 0
      ? '<span style="color:#3fb950; font-weight:700;">+1</span>'
      : v < 0
        ? '<span style="color:#f85149; font-weight:700;">-1</span>'
        : '<span style="color:#8b949e;">0</span>';
  const trendIcon = (t) =>
    t === "up"
      ? '<span style="color:#3fb950">↑ Rising</span>'
      : t === "down"
        ? '<span style="color:#f85149">↓ Falling</span>'
        : '<span style="color:#8b949e">→ Flat</span>';
  const tbody = el("macro-breakdown-body");
  tbody.innerHTML = (data.breakdown || [])
    .map(
      (r) =>
        `<tr>
            <td>${escHtml(r.name)}</td>
            <td class="text-end">${fmtNum(r.value)} ${escHtml(r.unit)}</td>
            <td class="text-center">${trendIcon(r.trend)}</td>
            <td class="text-center">${voteIcon(r.stocks_vote)}</td>
            <td class="text-center">${voteIcon(r.gold_vote)}</td>
            <td class="text-center">${voteIcon(r.crypto_vote)}</td>
            <td class="d-none d-md-table-cell" style="color:#8b949e; font-size:1rem;">${escHtml(r.impact)}</td>
        </tr>`
    )
    .join("");

  show("macro-recommendation");
}

// ── Analysis Panel ────────────────────────────────────
async function loadAnalysis(ticker, period) {
  show("analysis-row");
  el("analysis-ticker-label").textContent = ticker;
  show("analysis-loading");
  el("analysis-body").innerHTML = "";
  el("analysis-updated").textContent = "";

  try {
    const res = await fetch(
      `/api/analysis/${encodeURIComponent(ticker)}?period=${period}`
    );
    const data = await res.json();

    if (data.error) {
      el("analysis-body").innerHTML =
        `<div class="text-muted" style="font-size:1rem;">
                <i class="bi bi-info-circle me-1"></i>${escHtml(data.error)}</div>`;
      return;
    }

    renderAnalysis(data);
  } catch (e) {
    el("analysis-body").innerHTML =
      `<div class="error-msg">Analysis unavailable.</div>`;
  } finally {
    hide("analysis-loading");
  }
}

function voteTag(vote) {
  if (vote > 0) return '<span class="vote-up">▲ Bull</span>';
  if (vote < 0) return '<span class="vote-down">▼ Bear</span>';
  return '<span class="vote-neutral">— Neutral</span>';
}

function renderAnalysis(d) {
  const sigClass =
    d.signal.includes("BUY")
      ? "signal-buy"
      : d.signal.includes("SELL")
        ? "signal-sell"
        : "signal-hold";
  const sigIcon =
    d.signal.includes("BUY")
      ? "bi-arrow-up-circle-fill"
      : d.signal.includes("SELL")
        ? "bi-arrow-down-circle-fill"
        : "bi-dash-circle-fill";
  const confColor =
    d.signal.includes("BUY")
      ? "#3fb950"
      : d.signal.includes("SELL")
        ? "#f85149"
        : "#d29922";

  const rsiI = d.indicators.rsi;
  const smaI = d.indicators.sma;
  const macdI = d.indicators.macd;
  const bollI = d.indicators.bollinger;
  const volI = d.indicators.volume;

  const rsiZone =
    rsiI.value < 30 ? "Oversold" : rsiI.value > 70 ? "Overbought" : "Neutral";
  const bollPos = (bollI.position || "").replace(/_/g, " ");
  const histSign = macdI.histogram >= 0 ? "+" : "";

  el("analysis-body").innerHTML = `
    <div class="row g-3 mb-3">
        <div class="col-6 col-md-3 text-center">
            <div class="ta-metric-label">Signal</div>
            <div class="signal-badge ${sigClass} mt-1">
                <i class="bi ${sigIcon} me-1"></i>${escHtml(d.signal)}
            </div>
            <div class="confidence-bar mt-2">
                <div style="width:${d.confidence}%;background:${confColor};height:6px;" role="progressbar"></div>
            </div>
            <div style="font-size:1rem;color:#8b949e;margin-top:3px;">${d.confidence}% confidence</div>
        </div>
        <div class="col-6 col-md-3">
            <div class="ta-metric-label">Target Price</div>
            <div class="ta-metric-value trend-up">$${fmtNum(d.target_price)}</div>
            <div style="font-size:1rem;color:#8b949e;">60-day ${d.signal === "SELL" ? "support" : "resistance"}</div>
        </div>
        <div class="col-6 col-md-3">
            <div class="ta-metric-label">Stop Loss</div>
            <div class="ta-metric-value trend-down">$${fmtNum(d.stop_loss)}</div>
            <div style="font-size:1rem;color:#8b949e;">2× ATR from price</div>
        </div>
        <div class="col-6 col-md-3">
            <div class="ta-metric-label">Risk / Reward</div>
            <div class="ta-metric-value">${d.risk_reward != null ? d.risk_reward + "×" : "—"}</div>
            <div style="font-size:1rem;color:#8b949e;">${d.data_points} data points</div>
        </div>
    </div>

    <div class="row g-2 mb-3">
        <div class="col-6 col-md">
            <div class="ta-ind-card">
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <span class="ta-metric-label">RSI (14)</span>${voteTag(rsiI.vote)}
                </div>
                <div style="font-size:1.1rem;font-weight:700;color:#e6edf3;">${fmtNum(rsiI.value, 1)}</div>
                <div style="font-size:1rem;color:#8b949e;">${escHtml(rsiZone)}</div>
            </div>
        </div>
        <div class="col-6 col-md">
            <div class="ta-ind-card">
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <span class="ta-metric-label">SMA Cross</span>${voteTag(smaI.vote)}
                </div>
                <div style="font-size:1rem;color:#e6edf3;">20: ${smaI.sma20 != null ? "$" + fmtNum(smaI.sma20) : "—"}</div>
                <div style="font-size:1rem;color:#e6edf3;">50: ${smaI.sma50 != null ? "$" + fmtNum(smaI.sma50) : "—"}</div>
                <div style="font-size:1rem;color:#8b949e;text-transform:capitalize;">${escHtml(smaI.cross)}</div>
            </div>
        </div>
        <div class="col-6 col-md">
            <div class="ta-ind-card">
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <span class="ta-metric-label">MACD</span>${voteTag(macdI.vote)}
                </div>
                <div style="font-size:1rem;color:#e6edf3;">Line: ${fmtNum(macdI.value, 3)}</div>
                <div style="font-size:1rem;color:#e6edf3;">Hist: ${histSign}${fmtNum(macdI.histogram, 3)}</div>
                <div style="font-size:1rem;color:#8b949e;text-transform:capitalize;">${escHtml(macdI.trend)}</div>
            </div>
        </div>
        <div class="col-6 col-md">
            <div class="ta-ind-card">
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <span class="ta-metric-label">Bollinger</span>${voteTag(bollI.vote)}
                </div>
                <div style="font-size:1rem;color:#e6edf3;">%B: ${fmtNum(bollI.pct_b, 2)}</div>
                <div style="font-size:1rem;color:#e6edf3;">$${fmtNum(bollI.lower)} – $${fmtNum(bollI.upper)}</div>
                <div style="font-size:1rem;color:#8b949e;">${escHtml(bollPos)}</div>
            </div>
        </div>
        <div class="col-6 col-md">
            <div class="ta-ind-card">
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <span class="ta-metric-label">Volume</span>${voteTag(volI.vote)}
                </div>
                <div style="font-size:1.1rem;font-weight:700;color:#e6edf3;text-transform:capitalize;">${escHtml(volI.trend)}</div>
                <div style="font-size:1rem;color:#8b949e;">5-day vs 10-day avg</div>
            </div>
        </div>
    </div>

    <div class="p-3" style="background:#0d1117;border-radius:8px;font-size:1rem;color:#8b949e;line-height:1.6;">
        <i class="bi bi-info-circle me-1"></i>${escHtml(d.summary)}
    </div>`;

  el("analysis-updated").textContent = "Updated: " + (d.last_updated || "—");
}

// ── News Feed ─────────────────────────────────────────
async function loadNews(ticker) {
  show("news-row");
  el("news-ticker-label").textContent = ticker;
  show("news-loading");
  el("news-body").innerHTML = "";

  try {
    const res = await fetch(`/api/news/${encodeURIComponent(ticker)}`);
    const data = await res.json();
    hide("news-loading");

    if (!data.articles || !data.articles.length) {
      el("news-body").innerHTML =
        `<div class="p-3 text-muted" style="font-size:1rem;">No recent news found for ${escHtml(ticker)}.</div>`;
      return;
    }

    el("news-body").innerHTML = data.articles
      .map((a) => {
        const ts = a.published_at
          ? new Date(a.published_at * 1000).toLocaleDateString("en-US", {
              month: "short",
              day: "numeric",
            })
          : "";
        return `<div class="d-flex align-items-start gap-2 px-3 py-2" style="border-bottom:1px solid #21262d;">
                <div class="flex-grow-1">
                    <a href="${escHtml(a.link)}" target="_blank" rel="noopener noreferrer" class="news-link">${escHtml(a.title)}</a>
                    <span style="font-size:1rem;color:#8b949e;">${escHtml(a.publisher)}${ts ? " · " + ts : ""}</span>
                </div>
                <i class="bi bi-box-arrow-up-right flex-shrink-0 mt-1" style="color:#484f58;font-size:1rem;"></i>
            </div>`;
      })
      .join("");
  } catch (e) {
    hide("news-loading");
    el("news-body").innerHTML =
      `<div class="p-3 error-msg">Failed to load news.</div>`;
  }
}

// ── Crypto Market Metrics ─────────────────────────────
let _btcDomChart = null;
let _stableMcapChart = null;

async function loadCryptoMetrics() {
  show("btc-dom-loading");
  show("stable-mcap-loading");
  try {
    const [btcRes, stableRes] = await Promise.all([
      fetch("/api/indicator/BTC_DOMINANCE?days=60"),
      fetch("/api/indicator/STABLECOIN_MCAP?days=60"),
    ]);
    const btcData = btcRes.ok ? await btcRes.json() : null;
    const stableData = stableRes.ok ? await stableRes.json() : null;

    renderMetricChart(
      "btc-dom",
      btcData,
      "Bitcoin Dominance (%)",
      "%",
      "#f7931a"
    );
    renderMetricChart(
      "stable-mcap",
      stableData,
      "Stablecoin Market Cap ($B)",
      "B",
      "#26a17b"
    );
  } catch (e) {
    console.error("loadCryptoMetrics error:", e);
  } finally {
    hide("btc-dom-loading");
    hide("stable-mcap-loading");
  }
}

function renderMetricChart(prefix, data, label, unit, color) {
  const placeholder = el(prefix + "-placeholder");
  const chartDiv = el(prefix + "-chart");
  const valueEl = el(prefix + "-value");
  const noteEl = el(prefix + "-note");

  if (!data || !data.values || data.values.length === 0) {
    placeholder.textContent = "No data yet — will populate as scheduler runs.";
    placeholder.style.display = "";
    chartDiv.style.display = "none";
    return;
  }

  const latest = data.values[data.values.length - 1];
  const prev =
    data.values.length > 1 ? data.values[data.values.length - 2] : null;
  const change = prev !== null ? latest - prev : 0;
  const arrow = change > 0 ? "▲" : change < 0 ? "▼" : "—";
  const clr = change > 0 ? "#3fb950" : change < 0 ? "#f85149" : "#8b949e";

  valueEl.innerHTML = `${latest.toFixed(2)}${unit} <span style="color:${clr};font-size:1rem;">${arrow}</span>`;

  placeholder.style.display = "none";
  chartDiv.style.display = "";
  noteEl.style.display = "";

  // Destroy previous TradingView chart instance
  const chartKey = prefix === "btc-dom" ? "_btcDomChart" : "_stableMcapChart";
  if (window[chartKey]) {
    window[chartKey].remove();
    window[chartKey] = null;
  }
  chartDiv.innerHTML = "";

  const chart = LightweightCharts.createChart(chartDiv, {
    width: chartDiv.clientWidth || 300,
    height: 140,
    layout: { background: { color: "#161b22" }, textColor: "#8b949e" },
    grid: { vertLines: { color: "#21262d" }, horzLines: { color: "#21262d" } },
    rightPriceScale: { borderColor: "#30363d" },
    timeScale: { borderColor: "#30363d", timeVisible: false },
    crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
    handleScroll: false,
    handleScale: false,
  });

  const series = chart.addAreaSeries({
    lineColor: color,
    topColor: color + "44",
    bottomColor: color + "00",
    lineWidth: 2,
    priceLineVisible: false,
    lastValueVisible: true,
  });

  const lineData = data.labels
    .map((date, i) => ({ time: date, value: data.values[i] }))
    .filter((d) => d.value != null);
  series.setData(lineData);
  chart.timeScale().fitContent();

  window[chartKey] = chart;

  const ro = new ResizeObserver(() =>
    chart.applyOptions({ width: chartDiv.clientWidth })
  );
  ro.observe(chartDiv);
}

// ── Compare Chart ─────────────────────────────────────
const COMPARE_COLORS = ["#58a6ff", "#3fb950", "#ffa657"];
let _compareChart = null;

async function loadCompare(tickerStr, period) {
  const tickers = tickerStr.toUpperCase().split(",").map(t => t.trim()).filter(Boolean);
  if (tickers.length < 2) {
    el("compare-error").textContent = "Enter at least 2 tickers.";
    showBlock("compare-error");
    return;
  }

  hide("compare-error");
  hide("compare-placeholder");
  show("compare-loading");
  hide("compare-chart");
  el("compare-legend").innerHTML = "";

  try {
    const params = `tickers=${encodeURIComponent(tickers.join(","))}&period=${period}`;
    const res = await fetch(`/api/compare?${params}`);
    const data = await res.json();

    if (data.error) {
      el("compare-error").textContent = data.error;
      showBlock("compare-error");
      showBlock("compare-placeholder");
      return;
    }

    renderCompareChart(data);
  } catch (e) {
    el("compare-error").textContent = "Compare failed: " + e.message;
    showBlock("compare-error");
  } finally {
    hide("compare-loading");
  }
}

function renderCompareChart(data) {
  const chartEl = el("compare-chart");
  chartEl.style.display = "";

  // Destroy previous chart
  if (_compareChart) { _compareChart.remove(); _compareChart = null; }

  _compareChart = LightweightCharts.createChart(chartEl, {
    layout:     { background: { color: "#0d1117" }, textColor: "#8b949e" },
    grid:       { vertLines: { color: "#21262d" }, horzLines: { color: "#21262d" } },
    crosshair:  { mode: LightweightCharts.CrosshairMode.Normal },
    rightPriceScale: { borderColor: "#30363d" },
    timeScale:  { borderColor: "#30363d", timeVisible: true },
    handleScroll: true,
    handleScale:  true,
  });

  const tickers = Object.keys(data.series);
  const legend  = el("compare-legend");

  tickers.forEach((ticker, i) => {
    const color = COMPARE_COLORS[i % COMPARE_COLORS.length];
    const lineSeries = _compareChart.addLineSeries({ color, lineWidth: 2, title: ticker });
    const points = data.labels.map((d, idx) => ({ time: d, value: data.series[ticker][idx] }));
    lineSeries.setData(points);

    legend.innerHTML +=
      `<span style="color:${color};font-size:1rem;font-weight:600;">` +
      `<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${color};margin-right:4px;"></span>` +
      `${escHtml(ticker)}</span>`;
  });

  _compareChart.timeScale().fitContent();
}

// Wire up compare button
document.addEventListener("DOMContentLoaded", () => {
  const btn = el("compare-btn");
  if (btn) {
    btn.addEventListener("click", () => {
      const val = (el("compare-input").value || "").trim();
      loadCompare(val, currentPeriod);
    });
    el("compare-input").addEventListener("keydown", (e) => {
      if (e.key === "Enter") btn.click();
    });
  }
});

// ── Fundamentals Panel ────────────────────────────────
async function loadFundamentals(ticker) {
  show("fundamentals-row");
  hide("fundamentals-placeholder");
  el("fundamentals-ticker-label").textContent = ticker;
  show("fundamentals-loading");
  el("fundamentals-body").innerHTML = "";
  hide("fundamentals-error");

  try {
    const res = await fetch(`/api/fundamentals/${encodeURIComponent(ticker)}`);
    const data = await res.json();
    if (data.error) {
      el("fundamentals-error").textContent = data.error;
      showBlock("fundamentals-error");
      hide("fundamentals-row");
      show("fundamentals-placeholder");
      return;
    }
    renderFundamentals(data);
  } catch (e) {
    el("fundamentals-error").textContent = "Fundamentals unavailable.";
    showBlock("fundamentals-error");
  } finally {
    hide("fundamentals-loading");
  }
}

function fmtLargeNum(n) {
  if (n == null) return "—";
  if (Math.abs(n) >= 1e12) return "$" + (n / 1e12).toFixed(2) + "T";
  if (Math.abs(n) >= 1e9)  return "$" + (n / 1e9).toFixed(2) + "B";
  if (Math.abs(n) >= 1e6)  return "$" + (n / 1e6).toFixed(2) + "M";
  return "$" + n.toLocaleString();
}

function fundRow(label, value) {
  const v = value != null ? value : "—";
  return `<div class="d-flex justify-content-between py-2" style="border-bottom:1px solid #21262d;">
    <span style="color:#8b949e;">${escHtml(label)}</span>
    <span style="font-weight:600;color:#e6edf3;">${escHtml(String(v))}</span>
  </div>`;
}

function renderFundamentals(d) {
  const pct = (v) => v != null ? v + "%" : "—";
  const num = (v, dec=2) => v != null ? fmtNum(v, dec) : "—";

  el("fundamentals-body").innerHTML = `
    <div class="row g-3 mb-3">
      <!-- Company -->
      <div class="col-12 col-md-4">
        <div class="p-3 rounded h-100" style="background:#0d1117;border:1px solid #30363d;">
          <div class="text-muted mb-2" style="font-size:1rem;text-transform:uppercase;letter-spacing:0.05em;">Company</div>
          ${fundRow("Sector",    d.sector)}
          ${fundRow("Industry",  d.industry)}
          ${fundRow("Employees", d.employees != null ? Number(d.employees).toLocaleString() : "—")}
          ${fundRow("Market Cap", fmtLargeNum(d.market_cap))}
          ${fundRow("Enterprise Value", fmtLargeNum(d.enterprise_value))}
          ${fundRow("52W High", d.week_52_high != null ? "$" + num(d.week_52_high) : "—")}
          ${fundRow("52W Low",  d.week_52_low  != null ? "$" + num(d.week_52_low)  : "—")}
        </div>
      </div>
      <!-- Valuation -->
      <div class="col-12 col-md-4">
        <div class="p-3 rounded h-100" style="background:#0d1117;border:1px solid #30363d;">
          <div class="text-muted mb-2" style="font-size:1rem;text-transform:uppercase;letter-spacing:0.05em;">Valuation</div>
          ${fundRow("Trailing P/E",  num(d.trailing_pe))}
          ${fundRow("Forward P/E",   num(d.forward_pe))}
          ${fundRow("Price / Book",  num(d.price_to_book))}
          ${fundRow("Trailing EPS",  d.trailing_eps != null ? "$" + num(d.trailing_eps) : "—")}
          ${fundRow("Forward EPS",   d.forward_eps  != null ? "$" + num(d.forward_eps)  : "—")}
          ${fundRow("Next Earnings", d.next_earnings_date || "—")}
        </div>
      </div>
      <!-- Financials -->
      <div class="col-12 col-md-4">
        <div class="p-3 rounded h-100" style="background:#0d1117;border:1px solid #30363d;">
          <div class="text-muted mb-2" style="font-size:1rem;text-transform:uppercase;letter-spacing:0.05em;">Financials</div>
          ${fundRow("Profit Margin",    pct(d.profit_margin))}
          ${fundRow("Operating Margin", pct(d.operating_margin))}
          ${fundRow("ROE",              pct(d.roe))}
          ${fundRow("ROA",              pct(d.roa))}
          ${fundRow("Revenue Growth",   pct(d.revenue_growth))}
          ${fundRow("Earnings Growth",  pct(d.earnings_growth))}
          ${fundRow("Debt / Equity",    num(d.debt_to_equity))}
          ${fundRow("Free Cash Flow",   fmtLargeNum(d.free_cashflow))}
          ${fundRow("Dividend Yield",   pct(d.dividend_yield))}
          ${fundRow("Annual Dividend",  d.dividend_rate != null ? "$" + num(d.dividend_rate) : "—")}
        </div>
      </div>
    </div>`;
}

// ── Alerts ────────────────────────────────────────────
async function loadAlerts() {
  try {
    const res = await fetch("/api/alerts");
    const data = await res.json();
    const alerts = data.alerts || [];

    const badge = el("alerts-badge");
    if (badge) {
      if (alerts.length > 0) {
        badge.textContent = alerts.length;
        show("alerts-badge");
      } else {
        hide("alerts-badge");
      }
    }

    const modalBody = el("alerts-modal-body");
    if (modalBody) {
      if (alerts.length === 0) {
        modalBody.innerHTML = `
          <div class="text-center text-muted py-5" style="font-size: 1rem;">
            <i class="bi bi-check2-circle mb-2 d-block" style="font-size: 2rem; opacity: 0.3"></i>
            No new alerts right now.
          </div>`;
      } else {
        modalBody.innerHTML = alerts
          .map(function (a) {
            var icon = "bi-info-circle";
            var color = "#8b949e";
            if (a.alert_type === "macro") {
              icon = "bi-globe";
              color = "#bc8cff";
            } else if (a.alert_type === "rsi") {
              icon = "bi-graph-down-arrow";
              color = "#f85149";
            } else if (a.alert_type === "sma") {
              icon = "bi-activity";
              color = "#58a6ff";
            }

            var title = a.ticker ? a.ticker : "Macro";

            return (
              '<div class="px-3 py-3" style="border-bottom: 1px solid #30363d;">' +
              '<div class="d-flex w-100 justify-content-between align-items-center mb-1">' +
              '<strong style="color: ' +
              color +
              ';">' +
              '<i class="bi ' +
              icon +
              ' me-1"></i> ' +
              escHtml(title) +
              " Alert</strong>" +
              '<small class="text-muted" style="font-size: 1rem;">' +
              escHtml(a.created_at || "") +
              "</small>" +
              "</div>" +
              '<p class="mb-0 text-light" style="font-size: 1rem;">' +
              escHtml(a.message) +
              "</p>" +
              "</div>"
            );
          })
          .join("");
      }
    }
  } catch (e) {
    console.error("Failed to load alerts:", e);
  }
}

async function markAlertsRead() {
  try {
    const res = await fetch("/api/alerts/read", { method: "POST" });
    if (res.ok) {
      hide("alerts-badge");
    }
  } catch (e) {
    console.error("Failed to mark alerts as read:", e);
  }
}

const alertsBtn = el("alerts-btn");
if (alertsBtn) {
  alertsBtn.addEventListener("click", () => {
    const alertModalEl = document.getElementById("alertsModal");
    if (alertModalEl) {
      const modal = new bootstrap.Modal(alertModalEl);
      modal.show();

      // Add event listener to mark as read when modal is closed
      alertModalEl.addEventListener("hidden.bs.modal", function onHidden() {
        markAlertsRead();
        // Remove listener to prevent multiple triggers
        alertModalEl.removeEventListener("hidden.bs.modal", onHidden);
      });
    }
  });
}

// ── Refresh Countdown ─────────────────────────────────
function startRefreshCountdown() {
  refreshTimer = REFRESH_INTERVAL_SEC;
  el("refresh-countdown").textContent = refreshTimer;

  if (refreshIntervalId) clearInterval(refreshIntervalId);

  refreshIntervalId = setInterval(() => {
    refreshTimer--;
    el("refresh-countdown").textContent = refreshTimer;

    if (refreshTimer <= 0) {
      refreshTimer = REFRESH_INTERVAL_SEC;
      refreshAll();
    }
  }, 1000);
}

function refreshAll() {
  loadStatus();
  loadIndicators();
  loadMacro();
  loadCryptoMetrics();
  loadMovers();
  loadAlerts();
  if (currentTicker) loadChart(currentTicker, currentPeriod);
}

// ── Screener ──────────────────────────────────────────
let screenerTable = null;
let screenerLoaded = false;
let screenerEs = null; // active EventSource

const _scoreColor = (s) => s >= 8 ? "#3fb950" : s >= 6 ? "#58a6ff" : s <= 2 ? "#f85149" : s <= 4 ? "#e3b341" : "#8b949e";
const _macdBadge  = (m) => m === "buy"
  ? `<span class="badge" style="background:#3fb950;color:#000">buy</span>`
  : m === "sell"
  ? `<span class="badge" style="background:#f85149">sell</span>`
  : `<span class="badge bg-secondary">neutral</span>`;
const _smaBadge   = (s) => s === "golden_cross"
  ? `<span class="badge" style="background:#f6c343;color:#000">golden ✕</span>`
  : s === "death_cross"
  ? `<span class="badge" style="background:#f85149">death ✕</span>`
  : `<span class="badge bg-secondary">neutral</span>`;

function _buildScreenerRow(r) {
  return `<tr style="cursor:pointer" data-ticker="${escHtml(r.ticker)}">
    <td class="fw-bold" style="color:#58a6ff">${escHtml(r.ticker)}</td>
    <td class="text-truncate" style="max-width:160px">${escHtml(r.name || "—")}</td>
    <td><span class="fw-bold" style="color:${_scoreColor(r.bullish_score)}">${r.bullish_score ?? "—"}</span></td>
    <td>${r.rsi != null ? Number(r.rsi).toFixed(1) : "—"}</td>
    <td>${_macdBadge(r.macd_signal)}</td>
    <td>${_smaBadge(r.sma_signal)}</td>
    <td>$${r.close != null ? Number(r.close).toFixed(2) : "—"}</td>
  </tr>`;
}

function _initScreenerTable() {
  if (screenerTable) { screenerTable.destroy(); screenerTable = null; }
  screenerTable = $("#screener-dt").DataTable({
    order:      [[2, "desc"]],
    pageLength: 25,
    language:   { search: "Filter:", lengthMenu: "Show _MENU_" },
  });
  // Row click → load ticker
  document.querySelectorAll("#screener-tbody tr[data-ticker]").forEach((row) => {
    row.addEventListener("click", () => {
      const t = row.dataset.ticker;
      if (t) { loadChart(t, currentPeriod); }
    });
  });
}

function _screenerReady() {
  const loading = el("screener-loading");
  const scanBtn = el("screener-scan-btn");
  if (loading) loading.style.display = "none";
  if (scanBtn) { scanBtn.disabled = false; scanBtn.innerHTML = '<i class="bi bi-arrow-repeat me-1"></i>Scan Now'; }
  screenerLoaded = true;
}

function loadScreener(force = false) {
  if (screenerLoaded && !force) return;

  // Cancel any in-progress stream
  if (screenerEs) { screenerEs.close(); screenerEs = null; }

  const loading = el("screener-loading");
  const errEl   = el("screener-error");
  const tbody   = el("screener-tbody");
  const countEl = el("screener-count");
  const scanBtn = el("screener-scan-btn");

  if (errEl)   errEl.style.display = "none";
  if (loading) loading.style.display = "";
  if (scanBtn) { scanBtn.disabled = true; scanBtn.innerHTML = '<i class="bi bi-hourglass-split me-1"></i>Scanning…'; }

  // If not forcing, try the cache first
  if (!force) {
    fetch("/api/screener").then((r) => r.json()).then((data) => {
      if (data.results && data.results.length >= 10) {
        // Render from cache instantly
        if (screenerTable) { screenerTable.destroy(); screenerTable = null; }
        tbody.innerHTML = data.results.map(_buildScreenerRow).join("");
        _initScreenerTable();
        if (countEl) countEl.textContent = `(${data.results.length} tickers)`;
        const scannedEl = el("screener-scanned");
        const scannedAt = el("screener-scanned-at");
        if (data.scanned_at && scannedEl && scannedAt) {
          scannedAt.textContent = data.scanned_at;
          scannedEl.style.display = "";
        }
        _screenerReady();
        return;
      }
      // Not enough cached data — fall through to SSE scan
      _startScreenerStream(tbody, countEl, errEl);
    }).catch(() => _startScreenerStream(tbody, countEl, errEl));
    return;
  }

  // Force refresh — clear table and stream fresh
  if (screenerTable) { screenerTable.destroy(); screenerTable = null; }
  tbody.innerHTML = "";
  _startScreenerStream(tbody, countEl, errEl);
}

function _startScreenerStream(tbody, countEl, errEl) {
  if (countEl) countEl.textContent = "Downloading prices…";

  screenerEs = new EventSource("/api/screener/stream");

  screenerEs.onmessage = (event) => {
    const msg = JSON.parse(event.data);

    if (msg.status === "downloading") {
      if (countEl) countEl.textContent = "Downloading 100 tickers…";

    } else if (msg.status === "analyzing") {
      if (countEl) countEl.textContent = `Prices ready — running analysis…`;

    } else if (msg.status === "row") {
      tbody.insertAdjacentHTML("beforeend", _buildScreenerRow(msg));
      if (countEl) countEl.textContent = `Scanning… ${msg.processed} / 100`;

    } else if (msg.status === "done") {
      screenerEs.close();
      screenerEs = null;
      _initScreenerTable();
      if (countEl) countEl.textContent = `(${msg.count} tickers)`;
      const scannedEl = el("screener-scanned");
      const scannedAt = el("screener-scanned-at");
      if (scannedEl && scannedAt) {
        scannedAt.textContent = new Date().toLocaleString();
        scannedEl.style.display = "";
      }
      _screenerReady();
    }
  };

  screenerEs.onerror = () => {
    screenerEs.close();
    screenerEs = null;
    if (errEl) { errEl.textContent = "Stream connection lost. Try Scan Now."; errEl.style.display = ""; }
    _screenerReady();
  };
}

// ── Portfolio ─────────────────────────────────────────
function getPortfolioPositions() {
  try {
    return JSON.parse(localStorage.getItem(LS_PORTFOLIO) || "[]");
  } catch { return []; }
}

function savePortfolioPositions(positions) {
  localStorage.setItem(LS_PORTFOLIO, JSON.stringify(positions));
}

async function loadPortfolio() {
  const positions = getPortfolioPositions();

  if (positions.length === 0) {
    hide("port-table-row");
    hide("portfolio-summary");
    show("portfolio-placeholder");
    el("portfolio-donut").innerHTML = "";
    el("portfolio-donut-legend").innerHTML = "";
    return;
  }

  hide("portfolio-placeholder");
  show("port-loading");
  hide("port-error");

  try {
    const tickers = positions.map((p) => p.ticker).join(",");
    const res = await fetch(`/api/portfolio/prices?tickers=${encodeURIComponent(tickers)}`);
    const data = await res.json();
    hide("port-loading");

    if (data.error) {
      el("port-error").textContent = data.error;
      showBlock("port-error");
      return;
    }

    _renderPortfolio(positions, data.prices);
  } catch (e) {
    hide("port-loading");
    el("port-error").textContent = "Failed to load portfolio prices.";
    showBlock("port-error");
  }
}

function _renderPortfolio(positions, prices) {
  let totalInvested = 0;
  let totalValue = 0;
  const rows = [];

  positions.forEach((p) => {
    const currentPrice = prices[p.ticker] != null ? prices[p.ticker] : null;
    const invested = p.shares * p.avg_price;
    const marketValue = currentPrice != null ? p.shares * currentPrice : null;
    const pnlDollar = marketValue != null ? marketValue - invested : null;
    const pnlPct = pnlDollar != null && invested ? (pnlDollar / invested) * 100 : null;

    totalInvested += invested;
    if (marketValue != null) totalValue += marketValue;

    rows.push({ ticker: p.ticker, shares: p.shares, avg_price: p.avg_price,
      current: currentPrice, market_value: marketValue,
      pnl_dollar: pnlDollar, pnl_pct: pnlPct });
  });

  const totalPnl = totalValue - totalInvested;
  const totalPnlPct = totalInvested ? (totalPnl / totalInvested) * 100 : 0;
  const pnlClass = totalPnl > 0 ? "trend-up" : totalPnl < 0 ? "trend-down" : "";
  const pnlSign = totalPnl > 0 ? "+" : "";

  el("port-invested").textContent = "$" + fmtNum(totalInvested);
  el("port-value").textContent = "$" + fmtNum(totalValue);
  el("port-pnl").innerHTML =
    `<span class="${pnlClass}">${pnlSign}$${fmtNum(Math.abs(totalPnl))} (${pnlSign}${fmtNum(Math.abs(totalPnlPct))}%)</span>`;
  el("port-count").textContent = positions.length;
  show("portfolio-summary");

  el("port-tbody").innerHTML = rows.map((r) => {
    const rc = r.pnl_dollar == null ? "" : r.pnl_dollar > 0 ? "trend-up" : r.pnl_dollar < 0 ? "trend-down" : "";
    const rs = r.pnl_dollar != null && r.pnl_dollar > 0 ? "+" : "";
    const sharesStr = Number(r.shares).toLocaleString("en-US", { maximumFractionDigits: 4 });
    return `<tr>
      <td class="fw-bold" style="color:#58a6ff;cursor:pointer;" data-action="load" data-ticker="${escHtml(r.ticker)}">${escHtml(r.ticker)}</td>
      <td class="text-end">${sharesStr}</td>
      <td class="text-end">$${fmtNum(r.avg_price)}</td>
      <td class="text-end">${r.current != null ? "$" + fmtNum(r.current) : "—"}</td>
      <td class="text-end">${r.market_value != null ? "$" + fmtNum(r.market_value) : "—"}</td>
      <td class="text-end ${rc}">${r.pnl_dollar != null ? rs + "$" + fmtNum(Math.abs(r.pnl_dollar)) : "—"}</td>
      <td class="text-end ${rc}">${r.pnl_pct != null ? rs + fmtNum(Math.abs(r.pnl_pct)) + "%" : "—"}</td>
      <td class="text-end">
        <button class="btn btn-sm" style="color:#f85149;padding:1px 6px;border:none;background:transparent;"
          data-action="remove" data-ticker="${escHtml(r.ticker)}" title="Remove position">
          <i class="bi bi-trash3"></i>
        </button>
      </td>
    </tr>`;
  }).join("");

  show("port-table-row");
  _renderPortfolioDonut(rows);
}

function _renderPortfolioDonut(rows) {
  const svgEl = el("portfolio-donut");
  const legendEl = el("portfolio-donut-legend");
  if (!svgEl) return;

  const withVal = rows.filter((r) => r.market_value != null && r.market_value > 0);
  if (withVal.length === 0) {
    svgEl.innerHTML = "";
    if (legendEl) legendEl.innerHTML = "";
    return;
  }

  const totalMv = withVal.reduce((s, r) => s + r.market_value, 0) || 1;
  const vals   = withVal.map((r) => Math.round((r.market_value / totalMv) * 100));
  const colors = withVal.map((_, i) => PORTFOLIO_COLORS[i % PORTFOLIO_COLORS.length]);
  const labels = withVal.map((r) => r.ticker);

  renderFlowDonut(svgEl, vals, colors, labels);

  if (legendEl) {
    legendEl.innerHTML = withVal.map((r, i) =>
      `<span style="display:inline-flex;align-items:center;gap:4px;margin:2px 6px;">
        <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${colors[i]};"></span>
        <span style="color:${colors[i]};font-weight:600;">${escHtml(r.ticker)}</span>
      </span>`
    ).join("");
  }
}

async function addPosition(ticker, qty, avgPrice, txType) {
  const feedbackEl = el("port-add-feedback");
  ticker = ticker.trim().toUpperCase();

  if (!ticker) {
    feedbackEl.innerHTML = '<span class="error-msg">Ticker is required.</span>';
    return;
  }
  qty = parseFloat(qty);
  if (isNaN(qty) || qty <= 0) {
    feedbackEl.innerHTML = '<span class="error-msg">Quantity must be greater than 0.</span>';
    return;
  }

  // Avg price only required for buys
  if (txType === "buy") {
    avgPrice = parseFloat(avgPrice);
    if (isNaN(avgPrice) || avgPrice <= 0) {
      feedbackEl.innerHTML = '<span class="error-msg">Avg buy price must be greater than 0.</span>';
      return;
    }
  }

  feedbackEl.innerHTML = '<span class="loading-spinner me-1" style="display:inline-block;"></span> Validating…';
  const addBtn = el("port-add-btn");
  if (addBtn) addBtn.disabled = true;

  try {
    const positions = getPortfolioPositions();
    const idx = positions.findIndex((p) => p.ticker === ticker);

    if (txType === "sell") {
      // Sell: position must exist
      if (idx < 0) {
        feedbackEl.innerHTML = `<span class="error-msg">${escHtml(ticker)} is not in your portfolio.</span>`;
        return;
      }
      const held = positions[idx].shares;
      if (qty > held + 0.00001) {
        feedbackEl.innerHTML =
          `<span class="error-msg">You only hold ${held.toLocaleString("en-US", {maximumFractionDigits:4})} — can't sell ${qty}.</span>`;
        return;
      }
      const remaining = parseFloat((held - qty).toFixed(4));
      if (remaining <= 0.00001) {
        positions.splice(idx, 1); // fully sold — remove position
      } else {
        positions[idx].shares = remaining; // partial sell — reduce qty, keep avg_price
      }
      savePortfolioPositions(positions);
      feedbackEl.innerHTML = `<span style="color:#f85149;">&#10003; Sold ${qty} ${escHtml(ticker)}.</span>`;

    } else {
      // Buy: validate ticker via API first
      const res = await fetch(`/api/search?q=${encodeURIComponent(ticker)}`);
      const data = await res.json();
      if (!data.valid) {
        feedbackEl.innerHTML = `<span class="error-msg">Ticker "${escHtml(ticker)}" not found.</span>`;
        return;
      }

      if (idx >= 0) {
        // Average into existing position (weighted avg)
        const prev = positions[idx];
        const newQty = prev.shares + qty;
        positions[idx].avg_price = parseFloat(
          ((prev.shares * prev.avg_price + qty * avgPrice) / newQty).toFixed(4)
        );
        positions[idx].shares = parseFloat(newQty.toFixed(4));
      } else {
        positions.push({ ticker, shares: parseFloat(qty.toFixed(4)), avg_price: parseFloat(avgPrice.toFixed(4)) });
      }
      savePortfolioPositions(positions);
      feedbackEl.innerHTML = `<span style="color:#3fb950;">&#10003; Bought ${qty} ${escHtml(ticker)}.</span>`;
    }

    el("port-ticker-input").value = "";
    el("port-shares-input").value = "";
    el("port-price-input").value = "";
    await loadPortfolio();
  } catch (e) {
    feedbackEl.innerHTML = '<span class="error-msg">Action failed. Try again.</span>';
  } finally {
    if (addBtn) addBtn.disabled = false;
  }
}

function removePosition(ticker) {
  const positions = getPortfolioPositions().filter((p) => p.ticker !== ticker);
  savePortfolioPositions(positions);
  loadPortfolio();
}

// ── Tab Switching ─────────────────────────────────────
const TAB_IDS = ["overview", "technical", "macro", "market", "fundamentals", "screener", "portfolio"];

function switchTab(tabName) {
  if (!TAB_IDS.includes(tabName)) tabName = "overview";
  TAB_IDS.forEach((t) => {
    const pane = el("tab-" + t);
    if (pane) pane.style.display = t === tabName ? "" : "none";
  });
  document.querySelectorAll(".dash-tab-btn[data-tab]").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tabName);
  });
  localStorage.setItem(LS_ACTIVE_TAB, tabName);
}

// ── Escape HTML ───────────────────────────────────────
function escHtml(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ── Init ──────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  // Restore active tab
  const restoredTab = localStorage.getItem(LS_ACTIVE_TAB) || "overview";
  switchTab(restoredTab);
  if (restoredTab === "screener") loadScreener();
  if (restoredTab === "portfolio") loadPortfolio();

  // Tab click handler
  el("dash-tabs").addEventListener("click", (e) => {
    const btn = e.target.closest(".dash-tab-btn[data-tab]");
    if (!btn) return;
    switchTab(btn.dataset.tab);
    if (btn.dataset.tab === "screener") loadScreener();
    if (btn.dataset.tab === "portfolio") loadPortfolio();
  });

  // Portfolio: Buy/Sell toggle
  function _getPortTxType() {
    return el("port-tx-sell") && el("port-tx-sell").checked ? "sell" : "buy";
  }
  function _updatePortToggleUI(type) {
    const btn  = el("port-add-btn");
    const icon = el("port-btn-icon");
    const lbl  = el("port-btn-label");
    const priceCol = el("port-price-col");
    if (!btn) return;
    if (type === "sell") {
      btn.className  = "btn btn-danger w-100";
      icon.className = "bi bi-dash-circle me-1";
      lbl.textContent = "Sell";
      if (priceCol) priceCol.style.visibility = "hidden";
    } else {
      btn.className  = "btn btn-success w-100";
      icon.className = "bi bi-plus me-1";
      lbl.textContent = "Buy";
      if (priceCol) priceCol.style.visibility = "";
    }
  }
  const portTxBuy  = el("port-tx-buy");
  const portTxSell = el("port-tx-sell");
  if (portTxBuy)  portTxBuy.addEventListener("change",  () => _updatePortToggleUI("buy"));
  if (portTxSell) portTxSell.addEventListener("change", () => _updatePortToggleUI("sell"));

  // Portfolio: Add/Sell button
  const portAddBtn = el("port-add-btn");
  if (portAddBtn) {
    portAddBtn.addEventListener("click", () => {
      addPosition(
        el("port-ticker-input").value,
        el("port-shares-input").value,
        el("port-price-input").value,
        _getPortTxType()
      );
    });
  }
  // Portfolio: Enter key in ticker input
  const portTickerInput = el("port-ticker-input");
  if (portTickerInput) {
    portTickerInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        const sharesEl = el("port-shares-input");
        if (sharesEl && !sharesEl.value) { sharesEl.focus(); } else { portAddBtn && portAddBtn.click(); }
      }
    });
  }
  // Portfolio: event delegation on positions table
  const portTbody = el("port-tbody");
  if (portTbody) {
    portTbody.addEventListener("click", (e) => {
      const removeBtn = e.target.closest("[data-action='remove']");
      if (removeBtn) { removePosition(removeBtn.dataset.ticker); return; }
      const loadCell = e.target.closest("[data-action='load']");
      if (loadCell) { loadChart(loadCell.dataset.ticker, currentPeriod); }
    });
  }

  loadStatus();
  loadWatchlist();
  loadIndicators();
  loadMacro();
  loadCryptoMetrics();
  loadMovers();
  loadAlerts();
  startRefreshCountdown();

  // Screener "Scan Now" button
  const scanBtn = el("screener-scan-btn");
  if (scanBtn) {
    scanBtn.addEventListener("click", () => {
      screenerLoaded = false;
      loadScreener(true);
    });
  }

  // Restore last-viewed ticker from localStorage
  const savedTicker = localStorage.getItem(LS_LAST_TICKER);
  if (savedTicker) {
    el("search-input").value = savedTicker;
    currentTicker = savedTicker;
    loadChart(savedTicker, currentPeriod);
  }
});
