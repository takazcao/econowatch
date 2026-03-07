"use strict";

// ── Constants ─────────────────────────────────────────
const PERIOD_MAP = { "1d": "1d", "5d": "5d", "1w": "1w", "1mo": "1mo", "3mo": "3mo", "6mo": "6mo", "1y": "1y" };
const PERIOD_LABEL = { "1d": "1 Day", "5d": "5 Days", "1w": "1 Week", "1mo": "1 Month", "3mo": "3 Months", "6mo": "6 Months", "1y": "1 Year" };
const REFRESH_INTERVAL_SEC = 300; // 5 minutes
const LS_LAST_TICKER  = "ew_last_ticker";  // localStorage key
const LS_ACTIVE_TAB   = "ew_active_tab";   // localStorage key

// ── State ─────────────────────────────────────────────
let currentTicker  = null;
let currentPeriod  = "1mo";
let stockChart     = null;
let refreshTimer   = REFRESH_INTERVAL_SEC;
let refreshIntervalId = null;
let watchlistData  = [];   // [{ticker, name}]
let acActiveIndex  = -1;   // autocomplete keyboard nav

// ── Helpers ───────────────────────────────────────────
function el(id) { return document.getElementById(id); }

function show(id) { const e = el(id); if (e) e.style.display = ""; }
function hide(id) { const e = el(id); if (e) e.style.display = "none"; }
function showBlock(id) { const e = el(id); if (e) e.style.display = "block"; }

function fmtNum(n, decimals = 2) {
    if (n == null) return "—";
    return Number(n).toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
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
            el("status-pill").innerHTML = '<i class="bi bi-circle-fill me-1" style="font-size:0.5rem;"></i>live';
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
const STOCK_TICKERS  = new Set(["AAPL","MSFT","NVDA","GOOGL","AMZN","META","TSLA","NFLX","JPM","V","WMT"]);
const CRYPTO_TICKERS = new Set(["BTC-USD","ETH-USD","SOL-USD","BNB-USD"]);

async function loadWatchlist() {
    try {
        const res  = await fetch("/api/watchlist");
        watchlistData = await res.json();
        renderWatchlistPills();
    } catch (e) {
        // non-fatal — autocomplete just won't pre-populate
    }
}

function ticketCategory(ticker) {
    if (CRYPTO_TICKERS.has(ticker)) return "crypto";
    if (STOCK_TICKERS.has(ticker))  return "stock";
    return "etf/index";
}

function renderWatchlistPills() {
    const stocks = watchlistData.filter(w => STOCK_TICKERS.has(w.ticker));
    const etfs   = watchlistData.filter(w => !STOCK_TICKERS.has(w.ticker) && !CRYPTO_TICKERS.has(w.ticker));
    const crypto = watchlistData.filter(w => CRYPTO_TICKERS.has(w.ticker));

    function makePill(item) {
        const div = document.createElement("div");
        div.className = "watchlist-pill";
        div.innerHTML = `<span class="ticker">${escHtml(item.ticker)}</span><span class="name">${escHtml(item.name)}</span>`;
        div.addEventListener("click", () => {
            el("search-input").value = item.ticker;
            el("search-feedback").innerHTML = `<span style="color:#3fb950;font-size:0.8rem;"><i class="bi bi-check-circle-fill me-1"></i>${escHtml(item.name)}</span>`;
            currentTicker = item.ticker;
            el("price-ticker-name").textContent = item.name + " (" + item.ticker + ")";
            loadChart(item.ticker, currentPeriod);
            closeAutocomplete();
        });
        return div;
    }

    ["wl-stocks","wl-etfs","wl-crypto"].forEach(id => el(id).innerHTML = "");
    stocks.forEach(w => el("wl-stocks").appendChild(makePill(w)));
    etfs.forEach(w   => el("wl-etfs").appendChild(makePill(w)));
    crypto.forEach(w => el("wl-crypto").appendChild(makePill(w)));
}

// ── Autocomplete ──────────────────────────────────────
function getAcMatches(query) {
    if (!query) return watchlistData.slice(0, 8);
    const q = query.toUpperCase();
    return watchlistData.filter(w =>
        w.ticker.includes(q) || w.name.toUpperCase().includes(q)
    ).slice(0, 8);
}

function renderAutocomplete(matches) {
    const list = el("autocomplete-list");
    if (!matches.length) { list.style.display = "none"; return; }

    list.innerHTML = matches.map((w, i) => `
        <div class="ac-item${i === acActiveIndex ? " active" : ""}" data-ticker="${escHtml(w.ticker)}" data-name="${escHtml(w.name)}">
            <span class="ac-ticker">${escHtml(w.ticker)}</span>
            <span class="ac-name">${escHtml(w.name)}</span>
            <span class="ac-category">${ticketCategory(w.ticker)}</span>
        </div>`).join("");

    list.style.display = "block";

    list.querySelectorAll(".ac-item").forEach(item => {
        item.addEventListener("mousedown", e => {
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
    el("search-feedback").innerHTML = `<span style="color:#3fb950;font-size:0.8rem;"><i class="bi bi-check-circle-fill me-1"></i>${escHtml(name)}</span>`;
    currentTicker = ticker;
    el("price-ticker-name").textContent = name + " (" + ticker + ")";
    loadChart(ticker, currentPeriod);
    closeAutocomplete();
}

el("search-input").addEventListener("input", () => {
    acActiveIndex = -1;
    const q = el("search-input").value.trim();
    renderAutocomplete(getAcMatches(q));
});

el("search-input").addEventListener("keydown", e => {
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

document.addEventListener("click", e => {
    if (!el("search-input").contains(e.target) && !el("autocomplete-list").contains(e.target)) {
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
    const local = watchlistData.find(w => w.ticker === input);
    if (local) {
        selectTicker(local.ticker, local.name);
        return;
    }

    fb.innerHTML = '<span class="loading-spinner"></span>';

    try {
        const res  = await fetch(`/api/search?q=${encodeURIComponent(input)}`);
        const data = await res.json();

        if (data.valid) {
            fb.innerHTML = `<span style="color:#3fb950;font-size:0.8rem;"><i class="bi bi-check-circle-fill me-1"></i>${escHtml(data.name)}</span>`;
            currentTicker = data.ticker;
            el("price-ticker-name").textContent = data.name + " (" + data.ticker + ")";
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
el("period-tabs").addEventListener("click", e => {
    const btn = e.target.closest("[data-period]");
    if (!btn) return;
    el("period-tabs").querySelectorAll(".btn").forEach(b => b.classList.remove("active"));
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
    el("chart-title").innerHTML = `<span class="loading-spinner me-2"></span> Loading ${ticker}…`;

    try {
        const res  = await fetch(`/api/stock/${encodeURIComponent(ticker)}?period=${period}`);
        const data = await res.json();

        if (data.error || !data.labels) {
            throw new Error(data.error || "No data returned");
        }

        renderChart(data);
        updatePriceSummary(data, period);
        el("chart-title").textContent = `${ticker} — ${PERIOD_LABEL[period] || period}`;
        loadAnalysis(ticker, period);
        loadNews(ticker);
    } catch (e) {
        hide("chart-wrapper");
        el("chart-error").textContent = "Error: " + e.message;
        showBlock("chart-error");
        el("chart-title").textContent = "Chart unavailable";
        hide("analysis-row");
        hide("news-row");
    }
}

// ── Chart TA Helpers ──────────────────────────────────
function computeSMA(values, period) {
    return values.map((_, i) => {
        if (i < period - 1) return null;
        const slice = values.slice(i - period + 1, i + 1).filter(v => v != null);
        return slice.length === period ? Math.round(slice.reduce((a, b) => a + b, 0) / period * 100) / 100 : null;
    });
}

function computeBollinger(values, period = 20, mult = 2) {
    const sma = computeSMA(values, period);
    return values.map((_, i) => {
        if (sma[i] == null) return { upper: null, lower: null };
        const slice = values.slice(i - period + 1, i + 1).filter(v => v != null);
        if (slice.length < period) return { upper: null, lower: null };
        const variance = slice.reduce((a, b) => a + Math.pow(b - sma[i], 2), 0) / period;
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
        width:  chartEl.clientWidth || 600,
        height: 300,
        layout: {
            background: { color: "#161b22" },
            textColor:  "#8b949e",
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

    const hasCandleData = Array.isArray(data.opens) && Array.isArray(data.highs) && Array.isArray(data.lows);

    if (hasCandleData) {
        // ── Candlestick series ──────────────────────────
        const candleSeries = chart.addCandlestickSeries({
            upColor:        "#3fb950",
            downColor:      "#f85149",
            borderUpColor:  "#3fb950",
            borderDownColor:"#f85149",
            wickUpColor:    "#3fb950",
            wickDownColor:  "#f85149",
        });

        const candleData = data.labels
            .map((date, i) => ({
                time:  date,
                open:  data.opens[i]  ?? data.prices[i],
                high:  data.highs[i]  ?? data.prices[i],
                low:   data.lows[i]   ?? data.prices[i],
                close: data.prices[i],
            }))
            .filter(d => d.close != null);

        candleSeries.setData(candleData);

        // ── SMA20 overlay ───────────────────────────────
        const sma20vals = computeSMA(data.prices, 20);
        const sma20Series = chart.addLineSeries({
            color: "#58a6ff", lineWidth: 1,
            priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
        });
        const sma20Data = data.labels
            .map((date, i) => ({ time: date, value: sma20vals[i] }))
            .filter(d => d.value != null);
        if (sma20Data.length) sma20Series.setData(sma20Data);

        // ── SMA50 overlay ───────────────────────────────
        const sma50vals = computeSMA(data.prices, 50);
        const sma50Series = chart.addLineSeries({
            color: "#d29922", lineWidth: 1,
            priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
        });
        const sma50Data = data.labels
            .map((date, i) => ({ time: date, value: sma50vals[i] }))
            .filter(d => d.value != null);
        if (sma50Data.length) sma50Series.setData(sma50Data);

        // ── Bollinger Bands ─────────────────────────────
        const bbVals = computeBollinger(data.prices, 20);
        const bbLineOpts = {
            color: "rgba(88,166,255,0.45)", lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
        };
        const bbUpperSeries = chart.addLineSeries(bbLineOpts);
        const bbLowerSeries = chart.addLineSeries(bbLineOpts);

        const bbUpperData = data.labels.map((date, i) => ({ time: date, value: bbVals[i].upper })).filter(d => d.value != null);
        const bbLowerData = data.labels.map((date, i) => ({ time: date, value: bbVals[i].lower })).filter(d => d.value != null);
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
        const isPositive = prices.length >= 2 && prices[prices.length - 1] >= prices[0];
        const areaSeries = chart.addAreaSeries({
            lineColor:   isPositive ? "#3fb950" : "#f85149",
            topColor:    isPositive ? "rgba(63,185,80,0.15)"  : "rgba(248,81,73,0.15)",
            bottomColor: isPositive ? "rgba(63,185,80,0.0)"   : "rgba(248,81,73,0.0)",
            lineWidth: 2,
        });
        const lineData = data.labels
            .map((date, i) => ({ time: date, value: data.prices[i] }))
            .filter(d => d.value != null);
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
    el("price-latest").textContent = data.latest_close != null ? "$" + fmtNum(data.latest_close) : "—";

    const pct = data.change_pct;
    const badge = el("price-change");
    badge.textContent = pct != null ? changeIcon(pct) + fmtNum(Math.abs(pct)) + "%" : "—";
    badge.className = "change-badge " + changeClass(pct);

    el("price-period").textContent = PERIOD_LABEL[period] || period;
    el("price-points").textContent = data.labels ? data.labels.length : "—";
}

// ── Indicators ────────────────────────────────────────
async function loadIndicators() {
    try {
        const res  = await fetch("/api/indicators");
        const data = await res.json();

        hide("indicators-placeholder");

        if (data.error || !data.indicators) {
            el("indicators-error").textContent = data.error || "No indicator data.";
            showBlock("indicators-error");
            return;
        }

        const grid = el("indicators-grid");
        grid.innerHTML = "";

        data.indicators.forEach(ind => {
            const trendIcon = ind.trend === "up" ? "▲" : ind.trend === "down" ? "▼" : "—";
            const trendCls  = "trend-" + ind.trend;
            const col = document.createElement("div");
            col.className = "col-6 col-md-4 col-xl-3";
            col.innerHTML = `
                <div class="card indicator-card h-100" style="background:#0d1117;">
                    <div class="card-body py-3 px-3">
                        <div class="text-muted mb-1" style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.05em;">
                            ${escHtml(ind.name)}
                        </div>
                        <div class="d-flex align-items-end gap-2">
                            <span class="value">${fmtNum(ind.value, 1)}</span>
                            <span class="unit pb-1">${escHtml(ind.unit)}</span>
                            <span class="${trendCls} pb-1 ms-auto fw-bold">${trendIcon}</span>
                        </div>
                        <div class="text-muted mt-1" style="font-size:0.7rem;">${escHtml(ind.date)}</div>
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
        const res  = await fetch("/api/movers");
        const data = await res.json();

        renderMovers("gainers", data.gainers || [], true);
        renderMovers("losers",  data.losers  || [], false);
    } catch (e) {
        hide("gainers-loading");
        hide("losers-loading");
        el("gainers-error").textContent = "Failed to load movers.";
        el("losers-error").textContent  = "Failed to load movers.";
        showBlock("gainers-error");
        showBlock("losers-error");
    }
}

function renderMovers(type, rows, isGain) {
    hide(type + "-loading");

    if (!rows.length) {
        el(type + "-error").textContent = "No data available.";
        showBlock(type + "-error");
        return;
    }

    const tbody = el(type + "-body");
    tbody.innerHTML = rows.map(r => {
        const pct    = r.change_pct;
        const cls    = isGain ? "trend-up" : "trend-down";
        const icon   = isGain ? "▲" : "▼";
        return `<tr>
            <td><span class="ticker-badge">${escHtml(r.ticker)}</span></td>
            <td style="max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;"
                title="${escHtml(r.name)}">${escHtml(r.name)}</td>
            <td class="text-end">$${fmtNum(r.close)}</td>
            <td class="text-end ${cls}">${icon} ${fmtNum(Math.abs(pct))}%</td>
        </tr>`;
    }).join("");

    show(type + "-table");
}

// ── Macro Regime Analysis ─────────────────────────────
async function loadMacro() {
    show("macro-loading");
    try {
        const res  = await fetch("/api/macro");
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
    const cx = 60, cy = 60, r = 46, innerR = 30;
    const total = vals.reduce((a, b) => a + b, 0) || 1;
    let startAngle = -Math.PI / 2; // start at 12 o'clock

    function polarToXY(angle, radius) {
        return { x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle) };
    }

    function arcPath(startAng, endAng, radius, inner) {
        const s  = polarToXY(startAng, radius);
        const e  = polarToXY(endAng, radius);
        const si = polarToXY(startAng, inner);
        const ei = polarToXY(endAng, inner);
        const large = (endAng - startAng) > Math.PI ? 1 : 0;
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
        const sweep = (v / total) * 2 * Math.PI;
        const endAngle = startAngle + sweep;
        paths += `<path d="${arcPath(startAngle, endAngle, r, innerR)}" fill="${colors[i]}99" stroke="${colors[i]}" stroke-width="1.5"/>`;
        startAngle = endAngle;
    });

    // Center text: dominant allocation
    const maxIdx = vals.indexOf(Math.max(...vals));
    const centerText = `<text x="60" y="57" text-anchor="middle" font-size="13" font-weight="700" fill="${colors[maxIdx]}">${vals[maxIdx]}%</text>
        <text x="60" y="70" text-anchor="middle" font-size="7" fill="#8b949e">${labels[maxIdx]}</text>`;

    svgEl.innerHTML = paths + centerText;
}

function renderMacro(data) {
    hide("macro-placeholder");

    // Regime badge
    const regimeColors = {
        "Risk-On":             ["#1a3d1a", "#3fb950"],
        "Risk-Off":            ["#3d1a1a", "#f85149"],
        "Inflationary":        ["#3d2e00", "#d29922"],
        "Stagflationary":      ["#3d1a00", "#ffa657"],
        "Recessionary":        ["#2d1a2d", "#bc8cff"],
        "Mixed / Transitional":["#1c2128", "#8b949e"],
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
    const assetColors = { STOCKS: "#58a6ff", GOLD: "#d29922", CRYPTO: "#bc8cff", MIXED: "#8b949e" };
    const rec = data.recommendation;
    const assetEl = el("macro-best-asset");
    assetEl.textContent = (assetIcons[rec] || "") + " " + rec;
    assetEl.style.color = assetColors[rec] || "#e6edf3";
    el("macro-confidence").textContent = `Confidence: ${data.confidence}%`;

    // 1–10 Point Gauges
    const points = data.points;
    const gaugeItems = [
        { label: "Stocks", key: "stocks", icon: "📈", baseColor: "#58a6ff" },
        { label: "Gold",   key: "gold",   icon: "🥇", baseColor: "#d29922" },
        { label: "Crypto", key: "crypto", icon: "₿",  baseColor: "#bc8cff" },
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
    el("macro-score-bars").innerHTML = gaugeItems.map(b => {
        const pt  = points[b.key];
        const col = pointColor(pt);
        const lbl = pointLabel(pt);
        const d   = detail[b.key];

        const explain = `${d.bullish} of ${d.total_active} active indicators bullish`
            + ` (${d.bearish} bearish, ${d.neutral} neutral)`;

        const pips = Array.from({length: 10}, (_, i) => {
            const filled = (i + 1) <= pt;
            return `<div style="flex:1; height:10px; background:${filled ? col : "#21262d"}; border-radius:2px; margin:0 1px;"></div>`;
        }).join("");

        return `<div class="mb-3">
            <div class="d-flex align-items-center justify-content-between mb-1">
                <div style="font-size:0.85rem; font-weight:600; color:#e6edf3;">${b.icon} ${b.label}</div>
                <div class="d-flex align-items-center gap-2">
                    <span style="font-size:0.72rem; color:${col};">${lbl}</span>
                    <span style="font-size:1.2rem; font-weight:700; color:${col}; min-width:24px; text-align:right;">${pt}</span>
                    <span style="font-size:0.72rem; color:#8b949e;">/ 10</span>
                </div>
            </div>
            <div class="d-flex mb-1" style="height:10px;">${pips}</div>
            <div style="font-size:0.72rem; color:#8b949e;">${explain}</div>
        </div>`;
    }).join("");

    // Capital Flow Donut
    if (data.flow_pct) {
        const fp     = data.flow_pct;
        const labels = ["Stocks", "Gold", "Crypto"];
        const vals   = [fp.stocks, fp.gold, fp.crypto];
        const colors = ["#58a6ff", "#d29922", "#bc8cff"];

        el("flow-verdict").textContent = data.flow_verdict || "";

        el("flow-pct-labels").innerHTML = labels.map((lbl, i) =>
            `<div style="text-align:center; min-width:60px;">
                <div style="font-size:1.3rem; font-weight:700; color:${colors[i]};">${vals[i]}%</div>
                <div style="font-size:0.72rem; color:#8b949e;">${lbl}</div>
            </div>`
        ).join("");

        renderFlowDonut(el("flow-donut"), vals, colors, labels);
    }

    // Summary
    el("macro-summary").textContent = data.summary;

    // Yield curve warning
    if (data.yield_curve_inverted) {
        show("macro-yield-warning");
    }

    // Breakdown table
    const voteIcon = v => v > 0
        ? '<span style="color:#3fb950; font-weight:700;">+1</span>'
        : v < 0
        ? '<span style="color:#f85149; font-weight:700;">-1</span>'
        : '<span style="color:#8b949e;">0</span>';
    const trendIcon = t => t === "up" ? '<span style="color:#3fb950">↑ Rising</span>' : t === "down" ? '<span style="color:#f85149">↓ Falling</span>' : '<span style="color:#8b949e">→ Flat</span>';
    const tbody = el("macro-breakdown-body");
    tbody.innerHTML = (data.breakdown || []).map(r =>
        `<tr>
            <td>${escHtml(r.name)}</td>
            <td class="text-end">${fmtNum(r.value)} ${escHtml(r.unit)}</td>
            <td class="text-center">${trendIcon(r.trend)}</td>
            <td class="text-center">${voteIcon(r.stocks_vote)}</td>
            <td class="text-center">${voteIcon(r.gold_vote)}</td>
            <td class="text-center">${voteIcon(r.crypto_vote)}</td>
            <td class="d-none d-md-table-cell" style="color:#8b949e; font-size:0.78rem;">${escHtml(r.impact)}</td>
        </tr>`
    ).join("");

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
        const res  = await fetch(`/api/analysis/${encodeURIComponent(ticker)}?period=${period}`);
        const data = await res.json();

        if (data.error) {
            el("analysis-body").innerHTML = `<div class="text-muted" style="font-size:0.85rem;">
                <i class="bi bi-info-circle me-1"></i>${escHtml(data.error)}</div>`;
            return;
        }

        renderAnalysis(data);
    } catch (e) {
        el("analysis-body").innerHTML = `<div class="error-msg">Analysis unavailable.</div>`;
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
    const sigClass = d.signal === "BUY"  ? "signal-buy"
                   : d.signal === "SELL" ? "signal-sell"
                   :                       "signal-hold";
    const sigIcon  = d.signal === "BUY"  ? "bi-arrow-up-circle-fill"
                   : d.signal === "SELL" ? "bi-arrow-down-circle-fill"
                   :                       "bi-dash-circle-fill";
    const confColor = d.signal === "BUY"  ? "#3fb950"
                    : d.signal === "SELL" ? "#f85149"
                    :                       "#d29922";

    const rsiI  = d.indicators.rsi;
    const smaI  = d.indicators.sma;
    const macdI = d.indicators.macd;
    const bollI = d.indicators.bollinger;
    const volI  = d.indicators.volume;

    const rsiZone  = rsiI.value < 30 ? "Oversold" : rsiI.value > 70 ? "Overbought" : "Neutral";
    const bollPos  = (bollI.position || "").replace(/_/g, " ");
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
            <div style="font-size:0.72rem;color:#8b949e;margin-top:3px;">${d.confidence}% confidence</div>
        </div>
        <div class="col-6 col-md-3">
            <div class="ta-metric-label">Target Price</div>
            <div class="ta-metric-value trend-up">$${fmtNum(d.target_price)}</div>
            <div style="font-size:0.72rem;color:#8b949e;">60-day ${d.signal === "SELL" ? "support" : "resistance"}</div>
        </div>
        <div class="col-6 col-md-3">
            <div class="ta-metric-label">Stop Loss</div>
            <div class="ta-metric-value trend-down">$${fmtNum(d.stop_loss)}</div>
            <div style="font-size:0.72rem;color:#8b949e;">2× ATR from price</div>
        </div>
        <div class="col-6 col-md-3">
            <div class="ta-metric-label">Risk / Reward</div>
            <div class="ta-metric-value">${d.risk_reward != null ? d.risk_reward + "×" : "—"}</div>
            <div style="font-size:0.72rem;color:#8b949e;">${d.data_points} data points</div>
        </div>
    </div>

    <div class="row g-2 mb-3">
        <div class="col-6 col-md">
            <div class="ta-ind-card">
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <span class="ta-metric-label">RSI (14)</span>${voteTag(rsiI.vote)}
                </div>
                <div style="font-size:1.1rem;font-weight:700;color:#e6edf3;">${fmtNum(rsiI.value, 1)}</div>
                <div style="font-size:0.72rem;color:#8b949e;">${escHtml(rsiZone)}</div>
            </div>
        </div>
        <div class="col-6 col-md">
            <div class="ta-ind-card">
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <span class="ta-metric-label">SMA Cross</span>${voteTag(smaI.vote)}
                </div>
                <div style="font-size:0.8rem;color:#e6edf3;">20: ${smaI.sma20 != null ? "$" + fmtNum(smaI.sma20) : "—"}</div>
                <div style="font-size:0.8rem;color:#e6edf3;">50: ${smaI.sma50 != null ? "$" + fmtNum(smaI.sma50) : "—"}</div>
                <div style="font-size:0.72rem;color:#8b949e;text-transform:capitalize;">${escHtml(smaI.cross)}</div>
            </div>
        </div>
        <div class="col-6 col-md">
            <div class="ta-ind-card">
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <span class="ta-metric-label">MACD</span>${voteTag(macdI.vote)}
                </div>
                <div style="font-size:0.8rem;color:#e6edf3;">Line: ${fmtNum(macdI.value, 3)}</div>
                <div style="font-size:0.8rem;color:#e6edf3;">Hist: ${histSign}${fmtNum(macdI.histogram, 3)}</div>
                <div style="font-size:0.72rem;color:#8b949e;text-transform:capitalize;">${escHtml(macdI.trend)}</div>
            </div>
        </div>
        <div class="col-6 col-md">
            <div class="ta-ind-card">
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <span class="ta-metric-label">Bollinger</span>${voteTag(bollI.vote)}
                </div>
                <div style="font-size:0.8rem;color:#e6edf3;">%B: ${fmtNum(bollI.pct_b, 2)}</div>
                <div style="font-size:0.8rem;color:#e6edf3;">$${fmtNum(bollI.lower)} – $${fmtNum(bollI.upper)}</div>
                <div style="font-size:0.72rem;color:#8b949e;">${escHtml(bollPos)}</div>
            </div>
        </div>
        <div class="col-6 col-md">
            <div class="ta-ind-card">
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <span class="ta-metric-label">Volume</span>${voteTag(volI.vote)}
                </div>
                <div style="font-size:1.1rem;font-weight:700;color:#e6edf3;text-transform:capitalize;">${escHtml(volI.trend)}</div>
                <div style="font-size:0.72rem;color:#8b949e;">5-day vs 10-day avg</div>
            </div>
        </div>
    </div>

    <div class="p-3" style="background:#0d1117;border-radius:8px;font-size:0.82rem;color:#8b949e;line-height:1.6;">
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
        const res  = await fetch(`/api/news/${encodeURIComponent(ticker)}`);
        const data = await res.json();
        hide("news-loading");

        if (!data.articles || !data.articles.length) {
            el("news-body").innerHTML = `<div class="p-3 text-muted" style="font-size:0.85rem;">No recent news found for ${escHtml(ticker)}.</div>`;
            return;
        }

        el("news-body").innerHTML = data.articles.map(a => {
            const ts = a.published_at
                ? new Date(a.published_at * 1000).toLocaleDateString("en-US", { month: "short", day: "numeric" })
                : "";
            return `<div class="d-flex align-items-start gap-2 px-3 py-2" style="border-bottom:1px solid #21262d;">
                <div class="flex-grow-1">
                    <a href="${escHtml(a.link)}" target="_blank" rel="noopener noreferrer" class="news-link">${escHtml(a.title)}</a>
                    <span style="font-size:0.72rem;color:#8b949e;">${escHtml(a.publisher)}${ts ? " · " + ts : ""}</span>
                </div>
                <i class="bi bi-box-arrow-up-right flex-shrink-0 mt-1" style="color:#484f58;font-size:0.75rem;"></i>
            </div>`;
        }).join("");
    } catch (e) {
        hide("news-loading");
        el("news-body").innerHTML = `<div class="p-3 error-msg">Failed to load news.</div>`;
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
        const btcData    = btcRes.ok    ? await btcRes.json()    : null;
        const stableData = stableRes.ok ? await stableRes.json() : null;

        renderMetricChart("btc-dom", btcData,    "Bitcoin Dominance (%)",       "%",       "#f7931a");
        renderMetricChart("stable-mcap", stableData, "Stablecoin Market Cap ($B)", "B",    "#26a17b");
    } catch (e) {
        console.error("loadCryptoMetrics error:", e);
    } finally {
        hide("btc-dom-loading");
        hide("stable-mcap-loading");
    }
}

function renderMetricChart(prefix, data, label, unit, color) {
    const placeholder = el(prefix + "-placeholder");
    const chartDiv    = el(prefix + "-chart");
    const valueEl     = el(prefix + "-value");
    const noteEl      = el(prefix + "-note");

    if (!data || !data.values || data.values.length === 0) {
        placeholder.textContent = "No data yet — will populate as scheduler runs.";
        placeholder.style.display = "";
        chartDiv.style.display = "none";
        return;
    }

    const latest = data.values[data.values.length - 1];
    const prev   = data.values.length > 1 ? data.values[data.values.length - 2] : null;
    const change = prev !== null ? latest - prev : 0;
    const arrow  = change > 0 ? "▲" : change < 0 ? "▼" : "—";
    const clr    = change > 0 ? "#3fb950" : change < 0 ? "#f85149" : "#8b949e";

    valueEl.innerHTML = `${latest.toFixed(2)}${unit} <span style="color:${clr};font-size:0.8rem;">${arrow}</span>`;

    placeholder.style.display = "none";
    chartDiv.style.display = "";
    noteEl.style.display = "";

    // Destroy previous TradingView chart instance
    const chartKey = prefix === "btc-dom" ? "_btcDomChart" : "_stableMcapChart";
    if (window[chartKey]) { window[chartKey].remove(); window[chartKey] = null; }
    chartDiv.innerHTML = "";

    const chart = LightweightCharts.createChart(chartDiv, {
        width:  chartDiv.clientWidth || 300,
        height: 140,
        layout: { background: { color: "#161b22" }, textColor: "#8b949e" },
        grid:   { vertLines: { color: "#21262d" }, horzLines: { color: "#21262d" } },
        rightPriceScale: { borderColor: "#30363d" },
        timeScale: { borderColor: "#30363d", timeVisible: false },
        crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
        handleScroll: false,
        handleScale:  false,
    });

    const series = chart.addAreaSeries({
        lineColor:   color,
        topColor:    color + "44",
        bottomColor: color + "00",
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: true,
    });

    const lineData = data.labels
        .map((date, i) => ({ time: date, value: data.values[i] }))
        .filter(d => d.value != null);
    series.setData(lineData);
    chart.timeScale().fitContent();

    window[chartKey] = chart;

    const ro = new ResizeObserver(() => chart.applyOptions({ width: chartDiv.clientWidth }));
    ro.observe(chartDiv);
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
    if (currentTicker) loadChart(currentTicker, currentPeriod);
}

// ── Tab Switching ─────────────────────────────────────
const TAB_IDS = ["overview", "technical", "macro", "market"];

function switchTab(tabName) {
    if (!TAB_IDS.includes(tabName)) tabName = "overview";
    TAB_IDS.forEach(t => {
        const pane = el("tab-" + t);
        if (pane) pane.style.display = t === tabName ? "" : "none";
    });
    document.querySelectorAll(".dash-tab-btn[data-tab]").forEach(btn => {
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
    switchTab(localStorage.getItem(LS_ACTIVE_TAB) || "overview");

    // Tab click handler
    el("dash-tabs").addEventListener("click", e => {
        const btn = e.target.closest(".dash-tab-btn[data-tab]");
        if (btn) switchTab(btn.dataset.tab);
    });

    loadStatus();
    loadWatchlist();
    loadIndicators();
    loadMacro();
    loadCryptoMetrics();
    loadMovers();
    startRefreshCountdown();

    // Restore last-viewed ticker from localStorage
    const savedTicker = localStorage.getItem(LS_LAST_TICKER);
    if (savedTicker) {
        el("search-input").value = savedTicker;
        currentTicker = savedTicker;
        loadChart(savedTicker, currentPeriod);
    }
});
