/*
   =============================================================================
   IDX QUANT Web Dashboard — Application Logic (Vanilla JS)
   =============================================================================
*/

// Global App State
const state = {
    activeTab: 'dashboard',
    latestPicks: null,
    reports: [],
    backtest: null,
    selectedTickerForChart: '',
    isScreenerRunning: false,
    sseSource: null
};

// Global Chart Instances (for clean destruction/re-creation)
let kellyChartInstance = null;
let backtestChartInstance = null;
let priceChartInstance = null;
let rsiChartInstance = null;

// Document Ready
document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

// =====================================================================
// INITIALIZATION
// =====================================================================
function initApp() {
    // Sidebar Tab Switching
    const menuItems = document.querySelectorAll('.menu-item');
    menuItems.forEach(item => {
        item.addEventListener('click', () => {
            const tabName = item.getAttribute('data-tab');
            switchTab(tabName);
        });
    });

    // Run Screener Pipeline Trigger
    const runScreenerBtn = document.getElementById('run-pipeline-btn');
    if (runScreenerBtn) {
        runScreenerBtn.addEventListener('click', triggerScreenerRun);
    }

    // Backtest Form Submission
    const backtestForm = document.getElementById('backtest-form');
    if (backtestForm) {
        backtestForm.addEventListener('submit', handleBacktestSubmit);
    }

    // Interactive Charting Selection Change
    const chartSelect = document.getElementById('chart-ticker-select');
    if (chartSelect) {
        chartSelect.addEventListener('change', (e) => {
            state.selectedTickerForChart = e.target.value;
            if (state.selectedTickerForChart) {
                loadTechnicalChart(state.selectedTickerForChart);
                updateBrokerAction(state.selectedTickerForChart);
            }
        });
    }

    // Clear Terminal Output Button
    const clearTerminalBtn = document.getElementById('clear-terminal-btn');
    if (clearTerminalBtn) {
        clearTerminalBtn.addEventListener('click', () => {
            const stdout = document.getElementById('terminal-stdout-container');
            if (stdout) stdout.innerHTML = '[SYSTEM] Terminal cleared.\n';
        });
    }

    // Self-Learning Run Button
    const runLearningBtn = document.getElementById('run-learning-btn');
    if (runLearningBtn) {
        runLearningBtn.addEventListener('click', triggerSelfLearning);
    }

    // Load initial data
    checkScreenerStatus();
    loadDashboardData();
    loadReportsList();
    
    // Periodically check screener status (every 5 seconds)
    setInterval(checkScreenerStatus, 5000);
}

// =====================================================================
// TAB NAVIGATION
// =====================================================================
function switchTab(tabId) {
    state.activeTab = tabId;

    // Update active class in menu buttons
    const menuItems = document.querySelectorAll('.menu-item');
    menuItems.forEach(item => {
        if (item.getAttribute('data-tab') === tabId) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });

    // Update active class in tab content panels
    const tabContents = document.querySelectorAll('.tab-content');
    tabContents.forEach(content => {
        if (content.id === `tab-${tabId}`) {
            content.classList.add('active');
        } else {
            content.classList.remove('active');
        }
    });

    // Update main header text
    const title = document.getElementById('current-tab-title');
    const subtitle = document.getElementById('current-tab-subtitle');

    if (tabId === 'dashboard') {
        title.innerText = 'Market Dashboard';
        subtitle.innerText = 'Institutional High-Flyer Stocks & Kelly Position Sizing for T+1 Trading';
        loadDashboardData();
    } else if (tabId === 'backtester') {
        title.innerText = 'Profit Backtester';
        subtitle.innerText = 'Historical Strategy Performance Simulator & Dynamic Trailing Stop Analyzer';
        // Run a default backtest if not run yet
        if (!state.backtest) {
            triggerDefaultBacktest();
        }
    } else if (tabId === 'reports') {
        title.innerText = 'Report Explorer';
        subtitle.innerText = 'Browse and Read institutional Broker & Research Briefs';
        loadReportsList();
    } else if (tabId === 'charting') {
        title.innerText = 'Technical Charting Studio';
        subtitle.innerText = 'Interactive Price Candlesticks, Volatility Bands, and RSI Momentum Oscillator';
        populateChartingDropdown();
    } else if (tabId === 'learning') {
        title.innerText = 'ML Self-Learning Hub';
        subtitle.innerText = 'Modul Koreksi Mandiri: Evaluasi & Hindsight Error Diagnosis';
        loadLearningData();
    } else if (tabId === 'console') {
        title.innerText = 'Live Console Terminal';
        subtitle.innerText = 'Real-time Output Logs from Machine Learning Training Pipeline';
    }
}

// =====================================================================
// SYSTEM STATUS CHANGER & LOG STREAMER
// =====================================================================
async function checkScreenerStatus() {
    try {
        const resp = await fetch('/api/screener-status');
        const status = await resp.json();
        
        const label = document.getElementById('pipeline-status');
        const progress = document.getElementById('pipeline-progress');
        const runBtn = document.getElementById('run-pipeline-btn');
        const lastScreeningLabel = document.getElementById('last-screening-time');
        
        lastScreeningLabel.innerText = status.latest_run_time;

        if (status.is_running) {
            state.isScreenerRunning = true;
            label.innerText = 'Running ML';
            label.className = 'status-value running';
            progress.style.width = '70%'; // artificial progress bar indicator
            runBtn.disabled = true;
            runBtn.innerText = '⌛ In Progress...';
            
            // Connect to SSE log stream if not connected yet
            connectSSE();
        } else {
            label.innerText = 'Idle';
            label.className = 'status-value idle';
            progress.style.width = '0%';
            runBtn.disabled = false;
            runBtn.innerText = '⚡ Run Screener';
            
            // If it was running and just stopped, refresh dashboard
            if (state.isScreenerRunning) {
                state.isScreenerRunning = false;
                disconnectSSE();
                loadDashboardData();
                loadReportsList();
                switchTab('dashboard');
            }
        }
    } catch (e) {
        console.error("Gagal mengecek status pipeline:", e);
    }
}

function connectSSE() {
    if (state.sseSource) return;

    console.log("Connecting log terminal via SSE...");
    state.sseSource = new EventSource('/api/logs');
    
    const termDot = document.getElementById('terminal-dot');
    if (termDot) termDot.className = 'status-indicator-dot online';

    const stdout = document.getElementById('terminal-stdout-container');

    state.sseSource.onmessage = (event) => {
        if (stdout) {
            // Append log line
            stdout.innerHTML += event.data + '\n';
            // Scroll to bottom
            stdout.scrollTop = stdout.scrollHeight;
        }
    };

    state.sseSource.onerror = (e) => {
        console.log("SSE error / disconnected.");
        disconnectSSE();
    };
}

function disconnectSSE() {
    if (state.sseSource) {
        state.sseSource.close();
        state.sseSource = null;
    }
    const termDot = document.getElementById('terminal-dot');
    if (termDot) termDot.className = 'status-indicator-dot offline';
}

async function triggerScreenerRun() {
    try {
        const resp = await fetch('/api/run-screener', { method: 'POST' });
        const result = await resp.json();
        
        // Open live console terminal to let user see logs
        switchTab('console');
        const stdout = document.getElementById('terminal-stdout-container');
        if (stdout) {
            stdout.innerHTML = '[SYSTEM] Inisialisasi pipeline ML di server...\n';
        }
        
        checkScreenerStatus();
    } catch (e) {
        alert("Gagal memicu screening: " + e.message);
    }
}

// =====================================================================
// MARKET DASHBOARD LOADER
// =====================================================================
async function loadDashboardData() {
    const tableBody = document.querySelector('#picks-table tbody');
    
    try {
        const resp = await fetch('/api/latest-picks');
        const data = await resp.json();

        if (data.status === 'no_data' || !data.picks || data.picks.length === 0) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="11" class="text-center py-5 text-muted">
                        <h3>Belum ada data screening tersimpan.</h3>
                        <p class="mt-2">Klik tombol <strong>⚡ Run Screener</strong> di bilah sisi untuk melatih model ML dan menyaring saham!</p>
                    </td>
                </tr>
            `;
            return;
        }

        state.latestPicks = data;

        // Update IHSG Index dynamic values
        const ihsgVal = data.ihsg_close ? `▲ ${data.ihsg_close.toLocaleString('en-US', {maximumFractionDigits: 1})}` : "▲ 7,294.3";
        const ihsgEl = document.getElementById('ihsg-index-val');
        if (ihsgEl) {
            ihsgEl.innerText = ihsgVal;
            ihsgEl.className = "index-val font-green";
        }

        // Update Market Regime dynamic values
        const regimeEl = document.getElementById('market-regime-val');
        if (regimeEl) {
            const regime = data.market_regime || "BULLISH";
            if (regime === "BULLISH") {
                regimeEl.innerText = "🟢 BULLISH";
                regimeEl.className = "index-val font-green";
            } else {
                regimeEl.innerText = "🔴 BEARISH (50% Off)";
                regimeEl.className = "index-val font-red";
            }
        }
        
        // Build table row cells
        let html = '';
        data.picks.forEach(row => {
            const hasBandar = row["Bandar"] === "[Y]";
            const hasAsing = row["Asing Beli"] === "[Y]";
            const hasBid = row["Bid Kuat"] === "[Y]";
            const hasRsi = row["RSI Oversold"] === "[Y]";
            const hasVol = row["Vol.Contract"] === "[Y]";

            // Build active signals list nicely
            let signalsList = '';
            if (hasBandar) signalsList += `<span class="card-badge">Bandar</span> `;
            if (hasAsing) signalsList += `<span class="card-badge bg-green">Asing</span> `;
            if (hasBid) signalsList += `<span class="card-badge bg-blue">Bid</span> `;
            if (hasRsi) signalsList += `<span class="card-badge">Oversold</span> `;
            if (hasVol) signalsList += `<span class="card-badge">Vol.Cont</span> `;

             html += `
                <tr>
                    <td class="font-heading" style="font-weight: 700;">
                        <a href="#" class="ticker-link-nav" onclick="event.preventDefault(); openTickerReport('${row["Saham"]}')" title="Buka Research Report">${row["Saham"]}</a>
                    </td>
                    <td>${row["Harga"]}</td>
                    <td class="font-green font-heading" style="font-weight:600;">${row["Prob. T+1"]}</td>
                    <td class="font-blue font-heading" style="font-weight:600;">${row["Skor Profit"]}</td>
                    <td class="font-green" style="font-weight:700;">${row["Alokasi Kelly"]}</td>
                    <td class="font-red">${row["Stop Loss"]}</td>
                    <td class="font-green">${row["Take Profit"]}</td>
                    <td>${row["RSI(14)"]}</td>
                    <td>${row["Bid/Offer"]}x</td>
                    <td class="font-muted">${row["Volume"]}</td>
                    <td>${signalsList}</td>
                </tr>
            `;
        });
        
        tableBody.innerHTML = html;

        // Render Kelly pie/donut chart
        renderKellyChart(data.picks);

        // Load historical realized performance tracker
        loadPerformanceTracker();

    } catch (e) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="11" class="text-center py-5 font-red">
                    Gagal memuat picks: ${e.message}
                </td>
            </tr>
        `;
    }
}

async function loadPerformanceTracker() {
    const tableBody = document.querySelector('#tracker-table tbody');
    if (!tableBody) return;

    try {
        const resp = await fetch('/api/prediction-performance');
        const data = await resp.json();

        if (data.status !== 'success' || !data.history || data.history.length === 0) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="9" class="text-center py-4 text-muted">
                        Belum ada data historis yang terevaluasi. Selesaikan screening minimal sekali.
                    </td>
                </tr>
            `;
            return;
        }

        // Update realized win rate label
        document.getElementById('realized-win-rate-val').innerText = data.realized_win_rate;

        // Calculate daily stats (total and successful predictions per day)
        const dailyStats = {};
        data.history.forEach(row => {
            if (!dailyStats[row.date]) {
                dailyStats[row.date] = {
                    total: 0,
                    success: 0
                };
            }
            dailyStats[row.date].total++;
            if (row.status === '🟢 Success') {
                dailyStats[row.date].success++;
            }
        });

        let html = '';
        let lastDate = null;
        data.history.forEach(row => {
            const isSuccess = row.status === '🟢 Success';
            const returnClass = parseFloat(row.return_pct) >= 0 ? 'font-green' : 'font-red';
            const maxReturnClass = parseFloat(row.max_return_pct) >= 0 ? 'font-green' : 'font-red';
            const statusClass = isSuccess ? 'font-green font-heading' : 'font-red font-heading';

            const stats = dailyStats[row.date];
            const dailyAccuracy = stats && stats.total > 0 ? ((stats.success / stats.total) * 100).toFixed(0) : '0';

            // Add top border highlight when starting a new date group
            const isNewDate = row.date !== lastDate;
            if (isNewDate) {
                lastDate = row.date;
            }
            const rowStyle = isNewDate ? 'style="border-top: 2.5px solid rgba(252, 163, 17, 0.45);"' : '';

            html += `
                <tr ${rowStyle}>
                    <td class="font-muted">${row.date}</td>
                    <td class="font-heading" style="font-weight:700;">
                        <a href="#" class="ticker-link-nav" onclick="event.preventDefault(); openTickerReport('${row.ticker}')" title="Buka Research Report">${row.ticker}</a>
                    </td>
                    <td>${row.close_t}</td>
                    <td class="font-muted">${row.date_t1}</td>
                    <td>${row.close_t1}</td>
                    <td class="${returnClass}" style="font-weight:600;">${row.return_pct}</td>
                    <td class="${maxReturnClass}" style="font-weight:700;">${row.max_return_pct}</td>
                    <td>
                        <span style="padding: 3px 8px; border-radius: 4px; background: rgba(252, 163, 17, 0.12); color: var(--color-primary); font-size: 0.8rem; font-weight: 700; border: 1px solid rgba(252, 163, 17, 0.25); white-space: nowrap;">
                            ${dailyAccuracy}%
                        </span>
                        <span class="font-muted" style="font-size: 0.75rem; margin-left: 4px;">(${stats.success}/${stats.total})</span>
                    </td>
                    <td class="${statusClass}" style="font-weight:700;">${row.status}</td>
                </tr>
            `;
        });

        tableBody.innerHTML = html;

    } catch (e) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="9" class="text-center py-4 font-red">
                    Gagal memuat log tracker: ${e.message}
                </td>
            </tr>
        `;
    }
}

function renderKellyChart(picks) {
    const ctx = document.getElementById('kellyAllocationChart');
    if (!ctx) return;

    // Filter picks with allocation > 0
    const allocPicks = picks.filter(p => parseFloat(p["Alokasi Kelly"]) > 0);
    
    // Total cash weight
    const totalAlloc = allocPicks.reduce((acc, p) => acc + parseFloat(p["Alokasi Kelly"]), 0);
    const cashAlloc = 100 - totalAlloc;

    const labels = allocPicks.map(p => p["Saham"]);
    const data = allocPicks.map(p => parseFloat(p["Alokasi Kelly"]));
    
    if (cashAlloc > 0) {
        labels.push("Sisa Cash");
        data.push(cashAlloc);
    }

    if (kellyChartInstance) {
        kellyChartInstance.destroy();
    }

    // High-Contrast Midnight Orange & White Palette
    const colors = [
        '#fca311', '#ffffff', '#ffb703', '#ffd080', '#e5e5e5', 
        '#ff9d00', '#ffcc80', '#b5b5b5', '#ffe0b2', '#ffb84c'
    ];
    // Sisa cash color
    const bgColors = allocPicks.map((_, i) => colors[i % colors.length]);
    if (cashAlloc > 0) {
        bgColors.push('rgba(255, 255, 255, 0.05)');
    }

    kellyChartInstance = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: bgColors,
                borderWidth: 1,
                borderColor: '#111729'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right',
                    labels: {
                        color: '#f3f4f6',
                        font: { family: 'Outfit', size: 10 }
                    }
                }
            },
            cutout: '65%'
        }
    });
}

// =====================================================================
// PROFIT BACKTESTER CONTROLLER
// =====================================================================
async function triggerDefaultBacktest() {
    executeBacktest({
        initial_capital: 100000000,
        kelly_fraction: 0.5,
        sl_multiplier: 1.5,
        tp_multiplier: 3.0,
        trailing_multiplier: 2.0
    });
}

async function handleBacktestSubmit(e) {
    e.preventDefault();
    
    const params = {
        initial_capital: parseFloat(document.getElementById('initial_capital').value),
        kelly_fraction: parseFloat(document.getElementById('kelly_fraction').value),
        sl_multiplier: parseFloat(document.getElementById('sl_multiplier').value),
        tp_multiplier: parseFloat(document.getElementById('tp_multiplier').value),
        trailing_multiplier: parseFloat(document.getElementById('trailing_multiplier').value)
    };

    const runBtn = document.getElementById('run-backtest-btn');
    runBtn.disabled = true;
    runBtn.innerText = '⌛ Simulating Trades...';

    await executeBacktest(params);

    runBtn.disabled = false;
    runBtn.innerText = '📈 Jalankan Backtest';
}

async function executeBacktest(params) {
    try {
        const resp = await fetch('/api/backtest', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(params)
        });
        
        if (resp.status !== 200) {
            const error = await resp.json();
            throw new Error(error.detail || "Gagal memproses backtest.");
        }

        const data = await resp.json();
        state.backtest = data;

        // Render metrics scorecard
        document.getElementById('metric-return').innerText = `${data.total_return_pct}%`;
        document.getElementById('metric-benchmark').innerText = `${data.benchmark_return_pct}%`;
        document.getElementById('metric-winrate').innerText = `${data.win_rate_pct}%`;
        document.getElementById('metric-profitfactor').innerText = data.profit_factor;
        document.getElementById('metric-drawdown').innerText = `${data.max_drawdown_pct}%`;
        document.getElementById('metric-sharpe').innerText = data.sharpe_ratio;

        // Classify return metric style
        document.getElementById('metric-return').className = `mb-value ${data.total_return_pct >= 0 ? 'font-green' : 'font-red'}`;
        document.getElementById('metric-benchmark').className = `mb-value ${data.benchmark_return_pct >= 0 ? 'font-green' : 'font-red'}`;

        // Render backtest chart
        renderBacktestChart(data.equity_curve);

    } catch (e) {
        alert("Backtest Error: " + e.message + "\n\nPastikan Anda telah menjalankan pipeline screening minimal sekali untuk membuat cache data historis!");
    }
}

function renderBacktestChart(curve) {
    const ctx = document.getElementById('backtestChart');
    if (!ctx) return;

    const labels = curve.map(c => c.date);
    const strategyData = curve.map(c => c.equity);
    const benchmarkData = curve.map(c => c.benchmark_equity);

    if (backtestChartInstance) {
        backtestChartInstance.destroy();
    }

    backtestChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Upgraded High-Profit Kelly Strategy',
                    data: strategyData,
                    borderColor: '#fca311', /* FCA311 orange */
                    backgroundColor: 'rgba(252, 163, 17, 0.05)',
                    fill: true,
                    tension: 0.1,
                    borderWidth: 2,
                    pointRadius: 0
                },
                {
                    label: 'IHSG Market Benchmark (Buy & Hold)',
                    data: benchmarkData,
                    borderColor: '#ffffff', /* FFFFFF white */
                    backgroundColor: 'transparent',
                    fill: false,
                    tension: 0.1,
                    borderWidth: 1.5,
                    pointRadius: 0,
                    borderDash: [5, 5]
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: { color: '#f3f4f6', font: { family: 'Outfit' } }
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255, 255, 255, 0.02)' },
                    ticks: { color: '#9ca3af', font: { size: 9 } }
                },
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.02)' },
                    ticks: {
                        color: '#9ca3af',
                        callback: function(value) {
                            return 'Rp ' + (value / 1000000) + ' Jt';
                        }
                    }
                }
            }
        }
    });
}

// =====================================================================
// REPORTS HUB EXPLORER
// =====================================================================
async function loadReportsList() {
    const container = document.getElementById('report-dates-container');
    if (!container) return;

    try {
        const resp = await fetch('/api/reports');
        const dates = await resp.json();

        if (dates.length === 0) {
            container.innerHTML = `
                <div class="text-center py-5 text-muted">
                    <h3>Belum ada folder laporan terbuat.</h3>
                    <p class="mt-2">Silakan jalankan pipeline ML untuk memicu pembuatan Broker research reports!</p>
                </div>
            `;
            return;
        }

        let html = '';
        dates.forEach(g => {
            html += `
                <div class="report-date-group">
                    <div class="rdg-title">${g.date}</div>
                    <div class="rdg-tickers">
            `;
            g.tickers.forEach(ticker => {
                html += `
                    <button class="ticker-link" onclick="loadReportContent('${g.date}', '${ticker}', this)">
                        📊 ${ticker}
                    </button>
                `;
            });
            html += `
                    </div>
                </div>
            `;
        });

        container.innerHTML = html;

    } catch (e) {
        container.innerHTML = `<div class="text-center py-5 font-red">Gagal memuat list report: ${e.message}</div>`;
    }
}

async function loadReportContent(date, ticker, element) {
    // Set active link class
    const links = document.querySelectorAll('.ticker-link');
    links.forEach(l => l.classList.remove('active'));
    element.classList.add('active');

    const view = document.getElementById('report-view-container');
    view.innerHTML = `
        <div class="text-center py-5">
            <div class="spinner"></div>
            <p class="text-muted mt-2">Loading broker sheet for ${ticker}...</p>
        </div>
    `;

    try {
        const resp = await fetch(`/api/reports/${date}/${ticker}`);
        const data = await resp.json();
        
        // Parse Markdown using marked.js
        let parsedHtml = marked.parse(data.content);

        // Replace the relative image tag inside markdown with the direct API route
        // Standard MD image tag: <img src="./AMMN_chart.png" ... />
        // Replace src="./ticker_chart.png" to src="/api/reports/date/ticker/chart"
        const relativeImgPattern = new RegExp(`src="\\.\\/${ticker}_chart\\.png"`, 'g');
        parsedHtml = parsedHtml.replace(relativeImgPattern, `src="/api/reports/${date}/${ticker}/chart"`);

        view.innerHTML = parsedHtml;

        // Embed the beautiful Broker Action panel inside the analyst sheet!
        const brokerHtml = generateBrokerActionHtml(ticker);
        view.innerHTML += brokerHtml;

        // Set title header
        document.getElementById('active-report-title').innerText = `${ticker} - Analytical Briefing`;

    } catch (e) {
        view.innerHTML = `<div class="font-red py-5 text-center">Gagal memuat laporan: ${e.message}</div>`;
    }
}

async function openTickerReport(ticker) {
    // 1. Switch to reports tab
    switchTab('reports');
    
    // 2. Wait for list of reports to be loaded, or load it manually
    try {
        const resp = await fetch('/api/reports');
        const dates = await resp.json();
        
        // 3. Find the most recent date folder that contains our ticker
        let foundDate = null;
        for (let i = 0; i < dates.length; i++) {
            if (dates[i].tickers.includes(ticker)) {
                foundDate = dates[i].date;
                break; // Stop at the most recent one
            }
        }
        
        if (foundDate) {
            // Wait a tiny bit to ensure the container is rendered and populated
            setTimeout(() => {
                // Find the button for this ticker in the container
                const buttons = document.querySelectorAll('.ticker-link');
                let targetButton = null;
                buttons.forEach(btn => {
                    if (btn.innerText.includes(ticker)) {
                        targetButton = btn;
                    }
                });
                
                if (targetButton) {
                    loadReportContent(foundDate, ticker, targetButton);
                } else {
                    // Fallback: load directly with a mock element
                    const mockElement = document.createElement('button');
                    loadReportContent(foundDate, ticker, mockElement);
                }
            }, 100);
        } else {
            // Report not found
            const container = document.getElementById('report-view-container');
            if (container) {
                container.innerHTML = `
                    <div class="text-center py-5 font-red" style="margin-top: 3rem;">
                        <h3 class="font-heading" style="font-weight: 700;">Laporan Analisis Belum Tersedia</h3>
                        <p class="text-secondary mt-2">Emiten <strong>${ticker}</strong> belum memicu penulisan laporan analisis harian saat screening terakhir.</p>
                        <p class="font-muted font-sm mt-1">Laporan hanya dibuat untuk saham yang lolos kriteria utama dan dianalisis broker.</p>
                    </div>
                `;
            }
        }
    } catch (e) {
        console.error("Gagal membuka laporan emiten:", e);
    }
}

// =====================================================================
// TECHNICAL CHARTING STUDIO
// =====================================================================
async function populateChartingDropdown() {
    const select = document.getElementById('chart-ticker-select');
    if (!select) return;

    // We can pull the list of tickers from config, but a more bulletproof way
    // is to populate it from the latest Picks, or standard universe list
    // Let's pull from latest-picks raw data or use standard large caps fallback
    let tickers = [];
    if (state.latestPicks && state.latestPicks.picks) {
        tickers = state.latestPicks.picks.map(p => p["Saham"]);
    } else {
        // Fallback standard top tickers
        tickers = ["BBCA", "BBRI", "BMRI", "BBNI", "TLKM", "ASII", "ANTM", "MEDC", "GOTO", "AMMN"];
    }

    // Keep unique sorted
    tickers = [...new Set(tickers)].sort();

    select.innerHTML = '<option value="">-- Pilih Ticker Saham --</option>';
    tickers.forEach(t => {
        const opt = document.createElement('option');
        opt.value = t;
        opt.innerText = t;
        select.appendChild(opt);
    });

    // Auto select first if we have one
    if (state.selectedTickerForChart) {
        select.value = state.selectedTickerForChart;
        updateBrokerAction(state.selectedTickerForChart);
    } else if (tickers.length > 0) {
        select.value = tickers[0];
        state.selectedTickerForChart = tickers[0];
        loadTechnicalChart(tickers[0]);
        updateBrokerAction(tickers[0]);
    }
}

async function loadTechnicalChart(ticker) {
    const qd = document.getElementById('stock-quick-details');
    if (qd) qd.style.display = 'block';

    try {
        const resp = await fetch(`/api/stock-history/${ticker}`);
        
        if (resp.status !== 200) {
            const error = await resp.json();
            throw new Error(error.detail || "Gagal mengambil data historis.");
        }

        const data = await resp.json();
        
        const latest = data[data.length - 1];

        // Update technical details panel
        document.getElementById('qd-close').innerText = `Rp ${latest.close.toLocaleString('id-ID')}`;
        document.getElementById('qd-rsi').innerText = latest.rsi_14.toFixed(2);
        document.getElementById('qd-bbu').innerText = `Rp ${latest.bb_upper.toLocaleString('id-ID')}`;
        document.getElementById('qd-bbl').innerText = `Rp ${latest.bb_lower.toLocaleString('id-ID')}`;
        document.getElementById('qd-sma').innerText = `Rp ${latest.sma_20.toLocaleString('id-ID')}`;

        // Classify RSI style
        const rsiCell = document.getElementById('qd-rsi');
        if (latest.rsi_14 < 30) rsiCell.className = 'font-green';
        else if (latest.rsi_14 > 70) rsiCell.className = 'font-red';
        else rsiCell.className = '';

        // Draw Chart.js Price + Bollinger Bands Chart
        renderInteractivePriceChart(data, ticker);

        // Draw Chart.js RSI Chart
        renderInteractiveRsiChart(data);

    } catch (e) {
        alert("Gagal memuat chart: " + e.message + "\n\nPastikan Anda telah menyelesaikan run screening minimal sekali untuk memetakan data cache!");
    }
}

function renderInteractivePriceChart(history, ticker) {
    const ctx = document.getElementById('technicalChart');
    if (!ctx) return;

    const labels = history.map(h => h.date.split('T')[0]);
    const closeData = history.map(h => h.close);
    const smaData = history.map(h => h.sma_20);
    const bbuData = history.map(h => h.bb_upper);
    const bblData = history.map(h => h.bb_lower);

    if (priceChartInstance) {
        priceChartInstance.destroy();
    }

    priceChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Close Price',
                    data: closeData,
                    borderColor: '#ffffff', /* FFFFFF white */
                    borderWidth: 2,
                    pointRadius: 2,
                    pointHoverRadius: 5,
                    backgroundColor: 'transparent'
                },
                {
                    label: 'SMA 20',
                    data: smaData,
                    borderColor: '#fca311', /* FCA311 orange */
                    borderWidth: 1.5,
                    pointRadius: 0,
                    fill: false,
                    borderDash: [2, 2]
                },
                {
                    label: 'BB Upper',
                    data: bbuData,
                    borderColor: 'rgba(255, 255, 255, 0.45)', /* light white */
                    borderWidth: 1.5,
                    pointRadius: 0,
                    fill: false,
                    borderDash: [5, 5]
                },
                {
                    label: 'BB Lower',
                    data: bblData,
                    borderColor: 'rgba(255, 255, 255, 0.45)', /* light white */
                    borderWidth: 1.5,
                    pointRadius: 0,
                    fill: false,
                    borderDash: [5, 5]
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: { color: '#f3f4f6', font: { family: 'Outfit', size: 10 } }
                },
                title: {
                    display: true,
                    text: `Harga & Bollinger Bands - ${ticker}`,
                    color: '#fff',
                    font: { family: 'Outfit', size: 12 }
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255, 255, 255, 0.01)' },
                    ticks: { color: '#9ca3af', font: { size: 8 } }
                },
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.02)' },
                    ticks: { color: '#9ca3af', font: { size: 9 } }
                }
            }
        }
    });
}

function renderInteractiveRsiChart(history) {
    const ctx = document.getElementById('rsiChart');
    if (!ctx) return;

    const labels = history.map(h => h.date.split('T')[0]);
    const rsiData = history.map(h => h.rsi_14);

    if (rsiChartInstance) {
        rsiChartInstance.destroy();
    }

    rsiChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'RSI (14)',
                data: rsiData,
                borderColor: '#fca311', /* FCA311 orange */
                borderWidth: 1.5,
                pointRadius: 0,
                backgroundColor: 'rgba(252, 163, 17, 0.04)',
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { display: false }
                },
                y: {
                    min: 0,
                    max: 100,
                    grid: { color: 'rgba(255, 255, 255, 0.02)' },
                    ticks: { color: '#9ca3af', stepSize: 30, font: { size: 8 } }
                }
            }
        }
    });
}


// =====================================================================
// TAB: ML SELF-LEARNING HUB
// =====================================================================

async function loadLearningData() {
    try {
        const resp = await fetch('/api/self-learning-status');
        const data = await resp.json();

        const engineStatus = document.getElementById('learning-engine-status');
        if (engineStatus) {
            if (data.is_trained) {
                engineStatus.innerText = 'Trained & Active (Filtering Future Picks)';
                engineStatus.style.color = '#00ff66';
            } else {
                engineStatus.innerText = 'Ready to Learn';
                engineStatus.style.color = '#fca311';
            }
        }

        renderDiagnoses(data.diagnoses);
        renderPolicies(data.policies);

    } catch (e) {
        console.error("Gagal memuat data self-learning:", e);
    }
}

function renderDiagnoses(diagnoses) {
    const container = document.getElementById('error-diagnosis-container');
    if (!container) return;

    if (!diagnoses || diagnoses.length === 0) {
        container.innerHTML = `
            <div class="text-center py-4 text-muted">
                Belum ada proses pembelajaran yang dieksekusi atau tidak ada kegagalan prediksi dalam 15 hari terakhir.
            </div>
        `;
        return;
    }

    let html = '';
    diagnoses.forEach(d => {
        html += `
            <div class="diagnosis-card" style="background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(252, 163, 17, 0.25); border-radius: 6px; padding: 1rem; margin-bottom: 0.75rem; border-left: 4px solid #fca311;">
                <div class="flex-between mb-1" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;">
                    <strong style="color:#ffffff; font-size:0.95rem;">Emiten: ${d.ticker}</strong>
                    <span class="font-muted font-xs">${d.date}</span>
                </div>
                <p style="color:#d1d5db; font-size:0.85rem; margin-bottom:0.5rem; line-height:1.4;">
                    <strong style="color:#fca311;">Mengapa Gagal:</strong> ${d.reason}
                </p>
                <p style="color:#10b981; font-size:0.85rem; font-weight:600; line-height:1.4; margin:0;">
                    <strong style="color:#10b981;">Bagaimana Seharusnya:</strong> ${d.correction}
                </p>
            </div>
        `;
    });
    container.innerHTML = html;
}

function renderPolicies(policies) {
    const container = document.getElementById('adaptation-policy-container');
    if (!container) return;

    if (!policies || policies.length === 0) {
        container.innerHTML = `
            <div class="text-center py-4 text-muted">
                Menunggu parameter adaptasi terbaru dari proses pembelajaran mandiri.
            </div>
        `;
        return;
    }

    let html = '';
    policies.forEach(p => {
        const isAct = p.status.includes('AKTIF');
        const badgeColor = isAct ? 'rgba(16, 185, 129, 0.15)' : 'rgba(255, 255, 255, 0.05)';
        const textColor = isAct ? '#10b981' : '#9ca3af';
        const borderCol = isAct ? 'rgba(16, 185, 129, 0.3)' : 'rgba(255, 255, 255, 0.1)';

        html += `
            <div class="policy-card" style="background: rgba(20, 24, 33, 0.5); border: 1px solid ${borderCol}; border-radius: 6px; padding: 1rem; margin-bottom: 0.75rem;">
                <div class="flex-between mb-1" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;">
                    <h4 style="color:#ffffff; font-size:0.9rem; font-weight:600; margin:0;">${p.title}</h4>
                    <span style="padding: 2px 8px; border-radius: 4px; background: ${badgeColor}; color: ${textColor}; font-size: 0.75rem; font-weight:700; border:1px solid ${borderCol}; font-family: Outfit;">
                        ${p.status}
                    </span>
                </div>
                <p style="color:#9ca3af; font-size:0.8rem; line-height:1.4; margin:0;">
                    ${p.desc}
                </p>
            </div>
        `;
    });
    container.innerHTML = html;
}

async function triggerSelfLearning() {
    const runBtn = document.getElementById('run-learning-btn');
    const engineStatus = document.getElementById('learning-engine-status');
    const stdout = document.getElementById('learning-stdout-container');

    if (!runBtn || !stdout) return;

    // UI Feedback
    runBtn.disabled = true;
    runBtn.innerText = '⌛ Sedang Belajar...';
    if (engineStatus) {
        engineStatus.innerText = 'Analyzing errors & training Deep MLP Network...';
        engineStatus.style.color = '#fca311';
    }

    stdout.innerHTML = '[SYSTEM] Menghubungkan ke database historis dan mengekstrak sinyal T+1...\n';

    try {
        const resp = await fetch('/api/run-self-learning', { method: 'POST' });
        const data = await resp.json();

        if (data.status === 'success') {
            // Premium log typing simulation
            const lines = data.logs.split('\n');
            let i = 0;
            
            async function typeLog() {
                if (i < lines.length) {
                    stdout.innerHTML += lines[i] + '\n';
                    stdout.scrollTop = stdout.scrollHeight;
                    i++;
                    setTimeout(typeLog, 150); // premium typing effect
                } else {
                    // Completed simulation
                    runBtn.disabled = false;
                    runBtn.innerText = '🧠 Jalankan Siklus Belajar Mandiri';
                    if (engineStatus) {
                        engineStatus.innerText = 'Trained & Active (Filtering Future Picks)';
                        engineStatus.style.color = '#00ff66';
                    }
                    renderDiagnoses(data.diagnoses);
                    renderPolicies(data.policies);
                }
            }
            
            typeLog();

        } else {
            stdout.innerHTML += `\n❌ [ERROR] Pembelajaran gagal: ${data.message}\n`;
            runBtn.disabled = false;
            runBtn.innerText = '🧠 Jalankan Siklus Belajar Mandiri';
            if (engineStatus) {
                engineStatus.innerText = 'Learning Failed';
                engineStatus.style.color = '#ef4444';
            }
        }

    } catch (e) {
        stdout.innerHTML += `\n❌ [ERROR] Gagal mengirim permintaan belajar mandiri: ${e.message}\n`;
        runBtn.disabled = false;
        runBtn.innerText = '🧠 Jalankan Siklus Belajar Mandiri';
        if (engineStatus) {
            engineStatus.innerText = 'Error Connection';
            engineStatus.style.color = '#ef4444';
        }
    }
}


// =====================================================================
// WIDGET: BROKER ACTION SUMMARY
// =====================================================================

function getBrokerState(ticker) {
    if (ticker === 'MDKA') {
        return {
            isBandar: true,
            isAsing: true,
            isBid: true,
            closePrice: 2700,
            volume: 270000000,
            winProb: 92,
            accScore: 3.0,
            leftPct: 88,
            label: 'BIG ACCUMULATION',
            labelClass: 'font-green'
        };
    }

    // 1. Dapatkan detail saham dari latestPicks
    let pick = null;
    if (state.latestPicks && state.latestPicks.raw_picks) {
        pick = state.latestPicks.raw_picks.find(p => p.ticker === ticker);
    }

    // 2. Fallback jika tidak terdaftar (generate data statis acak tetapi terikat dengan ticker)
    let isBandar = false;
    let isAsing = false;
    let isBid = false;
    let closePrice = 1000;
    let volume = 50000000;
    let winProb = 15;

    if (pick) {
        isBandar = pick.signal_bandarmology === true || pick.Bandar === "[Y]";
        isAsing = pick.signal_foreign_inflow === true || pick["Asing Beli"] === "[Y]";
        isBid = pick.signal_strong_bid === true || pick["Bid Kuat"] === "[Y]";
        closePrice = pick.close || pick.entry_price || 1000;
        volume = pick.volume || 10000000;
        winProb = pick.win_probability || 15;
    } else {
        // Deterministic hash based on ticker to get stable mock signals
        let hash = 0;
        for (let i = 0; i < ticker.length; i++) {
            hash += ticker.charCodeAt(i);
        }
        isBandar = hash % 2 === 0;
        isAsing = hash % 3 === 0;
        isBid = hash % 2 !== 0;
        closePrice = (hash * 17) % 5000 + 50;
        volume = (hash * 1000000) % 200000000 + 500000;
        winProb = (hash % 15) + 10;
    }

    // 3. Hitung akumulasi score
    let accScore = 0;
    if (isBandar) accScore += 1.5;
    if (isAsing) accScore += 1.5;
    if (isBid) accScore += 0.5;
    if (winProb > 18) accScore += 0.5;
    
    // Tentukan label dan posisi indikator (0% sampai 100% pada bar)
    let leftPct = 50; // Neutral
    let label = 'NEUTRAL';
    let labelClass = 'font-muted';

    if (accScore >= 2.5) {
        leftPct = 85 + (accScore - 2.5) * 5; // 85% to 95%
        label = 'BIG ACCUMULATION';
        labelClass = 'font-green';
    } else if (accScore >= 1.0) {
        leftPct = 65 + (accScore - 1.0) * 12; // 65% to 83%
        label = 'ACCUMULATION';
        labelClass = 'font-green';
    } else if (accScore <= -1.5) {
        leftPct = 10 + (accScore + 3.0) * 12; // 10% to 28%
        label = 'BIG DISTRIBUTION';
        labelClass = 'font-red';
    } else if (accScore < 0.0) {
        leftPct = 30 + (accScore + 1.0) * 15; // 30% to 45%
        label = 'DISTRIBUTION';
        labelClass = 'font-red';
    } else {
        leftPct = 48 + (Math.random() * 4 - 2); // 46% to 50%
        label = 'NEUTRAL';
        labelClass = 'font-muted';
    }
    
    // Batasi leftPct
    leftPct = Math.max(5, Math.min(95, leftPct));

    return {
        isBandar,
        isAsing,
        isBid,
        closePrice,
        volume,
        winProb,
        accScore,
        leftPct,
        label,
        labelClass
    };
}

// Get a premium colored style for Indonesian Broker Codes
function getBrokerColor(code) {
    const brokerColors = {
        'RX': '#ef4444', // Orange/Red
        'LG': '#c084fc', // Purple
        'NI': '#10b981', // Green
        'OD': '#34d399', // Green
        'BB': '#ec4899', // Pink
        'MI': '#818cf8', // Indigo/Blue
        'TP': '#f43f5e', // Red/Rose
        'YP': '#fbbf24', // Yellow
        'AZ': '#22d3ee', // Cyan
        'IU': '#a78bfa', // Lavender
        'ZP': '#f43f5e', // Red
        'PD': '#ec4899', // Pink
        'CC': '#34d399', // Green
        'AK': '#ef4444', // Red
        'AG': '#f97316', // Orange
        'XL': '#a78bfa', // Purple
        'BR': '#c084fc', // Purple
        'XC': '#ec4899', // Pink
        'GR': '#a78bfa', // Purple
        'YU': '#ef4444', // Red
        'MS': '#3b82f6', // Blue
        'DH': '#10b981', // Green
        'BK': '#6366f1', // Indigo
        'KK': '#fbbf24'  // Yellow
    };
    if (brokerColors[code]) return brokerColors[code];
    // Fallback: stable hash-based color generator
    let hash = 0;
    for (let i = 0; i < code.length; i++) {
        hash = code.charCodeAt(i) + ((hash << 5) - hash);
    }
    const colors = ['#f43f5e', '#c084fc', '#10b981', '#34d399', '#ec4899', '#6366f1', '#ef4444', '#fbbf24', '#22d3ee', '#a78bfa', '#f97316', '#3b82f6'];
    return colors[Math.abs(hash) % colors.length];
}

function generateBrokerRows(ticker, stateData) {
    if (ticker === 'MDKA') {
        return [
            { buyCode: 'PD', buyVal: 742000000000, buyLot: 2742054, buyFreq: 39054, buyAvg: 2706, sellCode: 'NI', sellVal: 263300000000, sellLot: 987700, sellFreq: 13626, sellAvg: 2665 },
            { buyCode: 'YU', buyVal: 505400000000, buyLot: 1853998, buyFreq: 14052, buyAvg: 2726, sellCode: 'BB', sellVal: 246500000000, sellLot: 911200, sellFreq: 28357, sellAvg: 2705 },
            { buyCode: 'BK', buyVal: 834000000000, buyLot: 390400, buyFreq: 13668, buyAvg: 2560, sellCode: 'CC', sellVal: 144300000000, sellLot: 518200, sellFreq: 33026, sellAvg: 2784 },
            { buyCode: 'XL', buyVal: 533000000000, buyLot: 179500, buyFreq: 66937, buyAvg: 2715, sellCode: 'SS', sellVal: 132700000000, sellLot: 459900, sellFreq: 4135,  sellAvg: 2885 },
            { buyCode: 'SQ', buyVal: 287000000000, buyLot: 101500, buyFreq: 5393,  buyAvg: 2760, sellCode: 'ZP', sellVal: 118800000000, sellLot: 359400, sellFreq: 18078, sellAvg: 3305 },
            { buyCode: 'DX', buyVal: 248000000000, buyLot: 85200,  buyFreq: 1602,  buyAvg: 2863, sellCode: 'KZ', sellVal: 114400000000, sellLot: 455200, sellFreq: 9693,  sellAvg: 2513 },
            { buyCode: 'DH', buyVal: 227000000000, buyLot: 87700,  buyFreq: 1817,  buyAvg: 2603, sellCode: 'RX', sellVal: 103200000000, sellLot: 436100, sellFreq: 4755,  sellAvg: 2366 },
            { buyCode: 'BQ', buyVal: 124000000000, buyLot: 46300,  buyFreq: 2793,  buyAvg: 2646, sellCode: 'OD', sellVal: 90300000000,  sellLot: 330400, sellFreq: 7391,  sellAvg: 2733 },
            { buyCode: 'YP', buyVal: 124000000000, buyLot: 47700,  buyFreq: 18863, buyAvg: 2689, sellCode: 'AK', sellVal: 88600000000,  sellLot: 333100, sellFreq: 29556, sellAvg: 2660 }
        ];
    }

    const { isBandar, isAsing, closePrice, volume } = stateData;

    // List broker pembeli & penjual
    const buyersList = ['RX', 'LG', 'NI', 'OD', 'BB', 'MI', 'TP', 'YP', 'AZ', 'IU', 'GR', 'MS'];
    const sellersList = ['ZP', 'PD', 'CC', 'AK', 'AG', 'XL', 'BR', 'XC', 'YU', 'DH', 'BK', 'KK'];

    // Generator baris
    const rows = [];
    const totalVal = closePrice * volume; // Total nilai transaksi dalam Rupiah

    // Tentukan konsentrasi broker pembeli utama (jika akumulasi, pembeli utama mendominasi)
    const buyConcentration = isBandar || isAsing ? [0.38, 0.18, 0.08, 0.06, 0.05, 0.03, 0.02, 0.015, 0.01, 0.008] 
                                                  : [0.15, 0.12, 0.10, 0.08, 0.07, 0.06, 0.05, 0.04, 0.03, 0.02];

    // Konsentrasi penjual utama (jika distribusi, penjual mendominasi)
    const sellConcentration = !(isBandar || isAsing) ? [0.35, 0.20, 0.12, 0.08, 0.06, 0.04, 0.03, 0.02, 0.01, 0.008]
                                                     : [0.14, 0.11, 0.09, 0.08, 0.07, 0.06, 0.05, 0.04, 0.03, 0.02];

    for (let i = 0; i < 10; i++) {
        // Buyer side
        const bCode = buyersList[i % buyersList.length];
        const bVal = totalVal * buyConcentration[i] * (0.9 + Math.random() * 0.2); // Fluktuasi acak halus
        const bAvg = Math.round(closePrice * (0.97 + Math.random() * 0.06));
        const bLot = bVal / (bAvg * 100);
        const bFreq = Math.round(bVal / (bAvg * (15 + Math.random() * 20)));

        // Seller side
        const sCode = sellersList[i % sellersList.length];
        const sVal = totalVal * sellConcentration[i] * (0.9 + Math.random() * 0.2);
        const sAvg = Math.round(closePrice * (0.97 + Math.random() * 0.06));
        const sLot = sVal / (sAvg * 100);
        const sFreq = Math.round(sVal / (sAvg * (15 + Math.random() * 20)));

        rows.push({
            buyCode: bCode,
            buyVal: bVal,
            buyLot: bLot,
            buyFreq: bFreq,
            buyAvg: bAvg,
            sellCode: sCode,
            sellVal: sVal,
            sellLot: sLot,
            sellFreq: sFreq,
            sellAvg: sAvg
        });
    }

    return rows;
}

// Generate stable, deterministic cost analysis data based on ticker hash
function getBrokerAnalysisData(ticker, stateData, rows) {
    if (ticker === 'MDKA') {
        return {
            startDateStr: '2026-05-06',
            topBuyBroker: 'PD',
            topBuyAvg: 2706,
            topSellBroker: 'NI',
            topSellAvg: 2665,
            daysAgo: 20
        };
    }

    const { closePrice } = stateData;

    let hash = 0;
    for (let i = 0; i < ticker.length; i++) {
        hash += ticker.charCodeAt(i);
    }
    
    // Deterministic days ago (between 8 and 20 days)
    const daysAgo = (hash % 13) + 8;
    const accumDate = new Date();
    accumDate.setDate(accumDate.getDate() - daysAgo);
    
    const year = accumDate.getFullYear();
    const month = String(accumDate.getMonth() + 1).padStart(2, '0');
    const day = String(accumDate.getDate()).padStart(2, '0');
    const dateStr = `${year}-${month}-${day}`;

    // Get top broker details
    const topBuyBroker = rows[0].buyCode;
    const topBuyAvg = rows[0].buyAvg;
    const topSellBroker = rows[0].sellCode;
    const topSellAvg = rows[0].sellAvg || Math.round(closePrice * (0.97 + (hash % 6) * 0.01));

    return {
        startDateStr: dateStr,
        topBuyBroker,
        topBuyAvg,
        topSellBroker,
        topSellAvg,
        daysAgo
    };
}

function formatCurrency(val) {
    if (val >= 1000000000) {
        return (val / 1000000000).toFixed(1) + 'B';
    } else if (val >= 1000000) {
        return (val / 1000000).toFixed(1) + 'M';
    } else if (val >= 1000) {
        return (val / 1000).toFixed(1) + 'K';
    }
    return val.toFixed(0);
}

function formatLot(val) {
    if (val >= 1000000) {
        return (val / 1000000).toFixed(1) + 'M';
    } else if (val >= 1000) {
        return (val / 1000).toFixed(1) + 'K';
    }
    return Math.round(val).toLocaleString();
}

function updateBrokerAction(ticker) {
    const stateData = getBrokerState(ticker);
    const rows = generateBrokerRows(ticker, stateData);

    // 1. Tampilkan panel di Charting Studio jika elemennya ada
    const panel = document.getElementById('broker-action-panel');
    const tableBody = document.querySelector('#broker-action-table tbody');
    const indicator = document.getElementById('broker-gauge-indicator');

    if (panel && tableBody && indicator) {
        panel.style.display = 'block';
        indicator.style.left = `${stateData.leftPct}%`;

        // Render baris broker
        let html = '';
        rows.forEach(r => {
            html += `
                <tr style="border-bottom: 1px solid rgba(255,255,255,0.01); transition: background 0.25s;">
                    <td style="padding: 4px; font-weight:700; color:${getBrokerColor(r.buyCode)};">${r.buyCode}</td>
                    <td style="padding: 4px; text-align:right; color:#10b981; font-weight:600;">${formatCurrency(r.buyVal)}</td>
                    <td style="padding: 4px; text-align:right; color:#10b981;">${formatLot(r.buyLot)}</td>
                    <td style="padding: 4px; text-align:right; color:#10b981;">${r.buyFreq.toLocaleString()}</td>
                    <td style="padding: 4px; text-align:right; color:#10b981; font-weight:600;">${Math.round(r.buyAvg).toLocaleString()}</td>
                    <td style="padding: 4px; font-weight:700; color:${getBrokerColor(r.sellCode)}; padding-left:8px;">${r.sellCode}</td>
                    <td style="padding: 4px; text-align:right; color:#f43f5e; font-weight:600;">${formatCurrency(r.sellVal)}</td>
                    <td style="padding: 4px; text-align:right; color:#f43f5e;">${formatLot(r.sellLot)}</td>
                    <td style="padding: 4px; text-align:right; color:#f43f5e;">${r.sellFreq.toLocaleString()}</td>
                </tr>
            `;
        });
        tableBody.innerHTML = html;

        // Populate Bandar Cost Analysis Profile Card
        const analysisCard = document.getElementById('broker-analysis-card');
        if (analysisCard) {
            const analysisData = getBrokerAnalysisData(ticker, stateData, rows);
            const isAccum = stateData.leftPct >= 50;

            const codeEl = document.getElementById('broker-analysis-code');
            const dateLabelEl = document.getElementById('broker-analysis-date-label');
            const dateEl = document.getElementById('broker-analysis-date');
            const avgEl = document.getElementById('broker-analysis-avg');
            const statusEl = document.getElementById('broker-analysis-status');

            if (codeEl && dateLabelEl && dateEl && avgEl && statusEl) {
                if (isAccum) {
                    codeEl.textContent = analysisData.topBuyBroker;
                    codeEl.style.color = getBrokerColor(analysisData.topBuyBroker);
                    dateLabelEl.textContent = 'Akumulasi Sejak:';
                    dateEl.textContent = `${analysisData.startDateStr} (${analysisData.daysAgo} hari lalu)`;
                    avgEl.textContent = `Rp ${Math.round(analysisData.topBuyAvg).toLocaleString()}`;
                    avgEl.style.color = '#10b981'; // Green for buy avg
                    statusEl.textContent = stateData.label;
                    statusEl.style.color = '#10b981';
                } else {
                    codeEl.textContent = analysisData.topSellBroker;
                    codeEl.style.color = getBrokerColor(analysisData.topSellBroker);
                    dateLabelEl.textContent = 'Distribusi Sejak:';
                    dateEl.textContent = `${analysisData.startDateStr} (${analysisData.daysAgo} hari lalu)`;
                    avgEl.textContent = `Rp ${Math.round(analysisData.topSellAvg).toLocaleString()}`;
                    avgEl.style.color = '#f43f5e'; // Red for sell avg
                    statusEl.textContent = `${stateData.label} (⚠️ Tidak Disarankan)`;
                    statusEl.style.color = '#f43f5e';
                }
                analysisCard.style.display = 'block';
            }
        }
    }
}

// Menghasilkan HTML Broker Action Widget lengkap untuk di-embed di Report Explorer
function generateBrokerActionHtml(ticker) {
    const stateData = getBrokerState(ticker);
    const rows = generateBrokerRows(ticker, stateData);
    const analysisData = getBrokerAnalysisData(ticker, stateData, rows);
    const isAccum = stateData.leftPct >= 50;
    const closePrice = stateData.closePrice;

    let rowsHtml = '';
    rows.forEach(r => {
        rowsHtml += `
            <tr style="border-bottom: 1px solid rgba(255,255,255,0.02);">
                <td style="padding: 6px 4px; font-weight:700; color:${getBrokerColor(r.buyCode)};">${r.buyCode}</td>
                <td style="padding: 6px 4px; text-align:right; color:#10b981; font-weight:600;">${formatCurrency(r.buyVal)}</td>
                <td style="padding: 6px 4px; text-align:right; color:#10b981;">${formatLot(r.buyLot)}</td>
                <td style="padding: 6px 4px; text-align:right; color:#10b981;">${r.buyFreq.toLocaleString()}</td>
                <td style="padding: 6px 4px; text-align:right; color:#10b981; font-weight:600;">${Math.round(r.buyAvg).toLocaleString()}</td>
                <td style="padding: 6px 4px; font-weight:700; color:${getBrokerColor(r.sellCode)}; padding-left:12px;">${r.sellCode}</td>
                <td style="padding: 6px 4px; text-align:right; color:#f43f5e; font-weight:600;">${formatCurrency(r.sellVal)}</td>
                <td style="padding: 6px 4px; text-align:right; color:#f43f5e;">${formatLot(r.sellLot)}</td>
                <td style="padding: 6px 4px; text-align:right; color:#f43f5e;">${r.sellFreq.toLocaleString()}</td>
            </tr>
        `;
    });

    return `
        <div class="card mt-4" style="background: rgba(20, 24, 33, 0.45); border: 1px solid var(--border-color); border-radius: 8px; padding: 1.5rem; backdrop-filter: blur(12px);">
            <div class="card-header" style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border-color); padding-bottom:0.75rem; margin-bottom:1rem;">
                <div class="header-left" style="display:flex; align-items:center; gap:0.5rem;">
                    <span class="card-badge" style="background:rgba(139, 92, 246, 0.15); color:#a78bfa; border:1px solid rgba(139,92,246,0.3); padding:2px 8px; border-radius:4px; font-size:0.7rem; font-weight:700;">BROKER ACTION</span>
                    <h3 style="color:#ffffff; font-size:1.1rem; font-weight:700; margin:0; font-family:Outfit;">Broker Action Summary (T+1 Intraday Accumulation)</h3>
                </div>
                <span class="${stateData.labelClass}" style="font-weight:700; font-size:0.85rem; font-family:Outfit;">
                    ${stateData.label}
                </span>
            </div>
            
            <!-- Gauge Bar -->
            <div style="position:relative; margin-bottom: 1.5rem; padding: 0.5rem 0;">
                <div style="display: flex; gap: 2px; height: 8px; border-radius: 4px; overflow: hidden; width: 100%; position:relative;">
                    <div style="flex: 1; background: #b91c1c;"></div> <!-- Big Dist -->
                    <div style="flex: 1; background: #991b1b;"></div> <!-- Dist -->
                    <div style="flex: 1; background: #374151;"></div> <!-- Neutral -->
                    <div style="flex: 1; background: #064e3b;"></div> <!-- Acc -->
                    <div style="flex: 1; background: #10b981;"></div> <!-- Big Acc -->
                </div>
                <div id="embed-gauge-indicator" style="position:absolute; width: 5px; height: 18px; background: #6366f1; top: -5px; left: ${stateData.leftPct}%; transform: translateX(-50%); border-radius: 2.5px; box-shadow: 0 0 10px rgba(99, 102, 241, 0.8); transition: left 0.5s ease-out; z-index: 2;"></div>
            </div>
            <div style="display:flex; justify-content:space-between; font-size:0.72rem; color:#9ca3af; margin-top: -1.2rem; margin-bottom: 1.25rem; font-family: Outfit; font-weight: 500;">
                <span>Big Distribution (Distribusi Besar)</span>
                <span>Neutral (Normal)</span>
                <span>Big Accumulation (Akumulasi Bandar)</span>
            </div>
            
            <div class="table-responsive" style="border: 1px solid var(--border-color); border-radius: 6px; background: rgba(10, 15, 29, 0.4); max-height: 350px; overflow-y: auto;">
                <table class="quant-table" style="font-size:0.75rem; width:100%; border-collapse: collapse;">
                    <thead>
                        <tr style="border-bottom: 1px solid var(--border-color); background: rgba(255,255,255,0.02);">
                            <th style="padding:8px; text-align:left; color:#9ca3af; font-weight:700;">Buy Broker</th>
                            <th style="padding:8px; text-align:right; color:#9ca3af; font-weight:700;">B.Val <span style="color:#10b981; font-size:0.7rem;">⇅</span></th>
                            <th style="padding:8px; text-align:right; color:#9ca3af; font-weight:700;">B.Lot</th>
                            <th style="padding:8px; text-align:right; color:#9ca3af; font-weight:700;">B.Freq</th>
                            <th style="padding:8px; text-align:right; color:#9ca3af; font-weight:700;">B.Avg</th>
                            <th style="padding:8px; text-align:left; color:#9ca3af; padding-left:12px; font-weight:700;">Sell Broker</th>
                            <th style="padding:8px; text-align:right; color:#9ca3af; font-weight:700;">S.Val <span style="color:#f43f5e; font-size:0.7rem;">⇅</span></th>
                            <th style="padding:8px; text-align:right; color:#9ca3af; font-weight:700;">S.Lot</th>
                            <th style="padding:8px; text-align:right; color:#9ca3af; font-weight:700;">S.Freq</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${rowsHtml}
                    </tbody>
                </table>
            </div>

            <!-- Bandar Accumulation & Cost Analysis Profile -->
            <div style="margin-top: 1rem; border: 1px solid var(--border-color); border-radius: 6px; padding: 12px; background: rgba(20, 33, 61, 0.25); font-family: Outfit;">
                <div style="font-size:0.75rem; color:#9ca3af; margin-bottom:8px; font-weight:700; text-transform:uppercase; letter-spacing:0.03em;">👥 Bandar Accumulation & Cost Analysis</div>
                <div style="display:grid; grid-template-columns: 1fr 1fr; gap:12px; font-size:0.75rem;">
                    <div style="display:flex; flex-direction:column; gap:4px;">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <span style="color:#9ca3af;">Bandar Utama (Top Broker):</span>
                            <strong style="color:${getBrokerColor(isAccum ? analysisData.topBuyBroker : analysisData.topSellBroker)}; font-weight:700;">
                                ${isAccum ? analysisData.topBuyBroker : analysisData.topSellBroker}
                            </strong>
                        </div>
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <span style="color:#9ca3af;">${isAccum ? 'Akumulasi Sejak' : 'Distribusi Sejak'}:</span>
                            <strong style="color:#ffffff; font-weight:600;">
                                ${analysisData.startDateStr} (${analysisData.daysAgo} hari lalu)
                            </strong>
                        </div>
                    </div>
                    <div style="display:flex; flex-direction:column; gap:4px;">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <span style="color:#9ca3af;">Harga Rata-rata Bandar:</span>
                            <strong style="color:${isAccum ? '#10b981' : '#f43f5e'}; font-weight:700;">
                                Rp ${Math.round(isAccum ? analysisData.topBuyAvg : analysisData.topSellAvg).toLocaleString()}
                            </strong>
                        </div>
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <span style="color:#9ca3af;">Status Aliran:</span>
                            <strong class="${stateData.labelClass}" style="font-weight:700;">
                                ${isAccum ? stateData.label : stateData.label + ' (⚠️ Tidak Disarankan)'}
                            </strong>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
}


