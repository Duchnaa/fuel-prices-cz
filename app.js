'use strict';

const FUEL_META = {
  natural95: { label: 'Natural 95', color: '#1a6ed8', bg: 'rgba(26,110,216,0.15)' },
  diesel:    { label: 'Nafta',      color: '#f0883e', bg: 'rgba(240,136,62,0.15)' },
  natural98: { label: 'Natural 98', color: '#8957e5', bg: 'rgba(137,87,229,0.15)' },
  lpg:       { label: 'LPG',        color: '#3fb950', bg: 'rgba(63,185,80,0.15)'  },
};

let chartInstance = null;
let priceData = null;

async function loadData() {
  const res = await fetch(`data/prices.json?_=${Date.now()}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function formatPrice(val) {
  return typeof val === 'number' ? val.toFixed(2) : '—';
}

function formatDate(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString('cs-CZ', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function formatShortDate(iso) {
  const [y, m, d] = iso.split('-');
  return `${d}.${m}.`;
}

function calcTrend(current, previous) {
  if (previous == null) return null;
  const diff = +(current - previous).toFixed(2);
  return diff;
}

function renderTrend(containerId, diff) {
  const el = document.getElementById(containerId);
  if (!el) return;
  if (diff === null) { el.innerHTML = ''; return; }

  if (diff > 0) {
    el.innerHTML = `<span class="trend-arrow trend-up">▲</span>
      <span class="trend-up">+${diff.toFixed(2)} Kč</span>
      <span class="trend-label">oproti včera</span>`;
  } else if (diff < 0) {
    el.innerHTML = `<span class="trend-arrow trend-down">▼</span>
      <span class="trend-down">${diff.toFixed(2)} Kč</span>
      <span class="trend-label">oproti včera</span>`;
  } else {
    el.innerHTML = `<span class="trend-same">— beze změny</span>`;
  }
}

function renderCards(data) {
  const curr = data.current;
  const hist = data.history;
  const prev = hist.length >= 2 ? hist[hist.length - 2] : null;

  for (const key of Object.keys(FUEL_META)) {
    const priceEl = document.getElementById(`price-${key}`);
    if (priceEl) priceEl.textContent = formatPrice(curr[key]);

    const diff = prev ? calcTrend(curr[key], prev[key]) : null;
    renderTrend(`trend-${key}`, diff);
  }
}

function renderStats(data) {
  const curr = data.current;
  const hist = data.history;

  // Cheapest / most expensive
  const entries = Object.entries(curr).map(([k, v]) => ({ key: k, val: v, label: FUEL_META[k].label }));
  const sorted = [...entries].sort((a, b) => a.val - b.val);

  const cheapestEl = document.getElementById('stat-cheapest');
  const expensiveEl = document.getElementById('stat-most-expensive');
  if (cheapestEl) cheapestEl.textContent = `${sorted[0].label} (${formatPrice(sorted[0].val)} Kč/l)`;
  if (expensiveEl) expensiveEl.textContent = `${sorted[sorted.length-1].label} (${formatPrice(sorted[sorted.length-1].val)} Kč/l)`;

  // Average N95 + diesel
  const avg = ((curr.natural95 + curr.diesel) / 2).toFixed(2);
  const avgEl = document.getElementById('stat-average');
  if (avgEl) avgEl.textContent = `${avg} Kč/l`;

  // 7-day change for N95
  const weekChange = document.getElementById('stat-week-change');
  if (weekChange && hist.length >= 8) {
    const week = hist[hist.length - 8];
    const diff = +(curr.natural95 - week.natural95).toFixed(2);
    const sign = diff > 0 ? '+' : '';
    weekChange.textContent = `${sign}${diff} Kč/l`;
    weekChange.style.color = diff > 0 ? 'var(--red-light)' : diff < 0 ? 'var(--green)' : 'var(--text-dim)';
  }
}

function renderGovCap(data) {
  const cap = data.government_cap;
  const banner = document.getElementById('gov-cap-banner');
  const text = document.getElementById('gov-cap-text');
  if (!banner || !text) return;

  if (cap && cap.active) {
    text.textContent = cap.info || `Vládní strop na pohonné hmoty je aktivní. Natural 95: max ${cap.cap_price_natural95} Kč/l, Nafta: max ${cap.cap_price_diesel} Kč/l`;
    banner.classList.remove('hidden');
  } else {
    banner.classList.add('hidden');
  }
}

function buildChartData(hist, fuelKeys) {
  const labels = hist.map(h => formatShortDate(h.date));
  const datasets = fuelKeys.map(key => ({
    label: FUEL_META[key].label,
    data: hist.map(h => h[key] ?? null),
    borderColor: FUEL_META[key].color,
    backgroundColor: FUEL_META[key].bg,
    borderWidth: 2.5,
    pointRadius: 0,
    pointHoverRadius: 5,
    pointHoverBackgroundColor: FUEL_META[key].color,
    tension: 0.4,
    fill: false,
  }));
  return { labels, datasets };
}

function renderLegend(fuelKeys) {
  const container = document.getElementById('chart-legend');
  if (!container) return;
  container.innerHTML = fuelKeys.map(key => `
    <div class="legend-item">
      <span class="legend-dot" style="background:${FUEL_META[key].color}"></span>
      ${FUEL_META[key].label}
    </div>`).join('');
}

function renderChart(hist, fuelKeys) {
  const ctx = document.getElementById('priceChart');
  if (!ctx) return;

  if (chartInstance) { chartInstance.destroy(); }

  const { labels, datasets } = buildChartData(hist, fuelKeys);

  chartInstance = new Chart(ctx, {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1c2230',
          borderColor: 'rgba(255,255,255,0.1)',
          borderWidth: 1,
          titleColor: '#e6edf3',
          bodyColor: '#8b949e',
          padding: 12,
          callbacks: {
            label: ctx => ` ${ctx.dataset.label}: ${ctx.parsed.y.toFixed(2)} Kč/l`,
          },
        },
      },
      scales: {
        x: {
          grid: { color: 'rgba(255,255,255,0.04)', drawBorder: false },
          ticks: {
            color: '#6e7681',
            maxTicksLimit: 10,
            maxRotation: 0,
            font: { size: 11 },
          },
        },
        y: {
          grid: { color: 'rgba(255,255,255,0.06)', drawBorder: false },
          ticks: {
            color: '#6e7681',
            font: { size: 11 },
            callback: v => `${v.toFixed(0)} Kč`,
          },
          border: { dash: [4, 4] },
        },
      },
    },
  });
}

function setupFilters(hist) {
  const buttons = document.querySelectorAll('.filter-btn');
  buttons.forEach(btn => {
    btn.addEventListener('click', () => {
      buttons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const fuel = btn.dataset.fuel;
      const keys = fuel === 'all' ? Object.keys(FUEL_META) : [fuel];
      renderLegend(keys);
      renderChart(hist, keys);
    });
  });
}

async function init() {
  const loading = document.getElementById('loading');
  const error   = document.getElementById('error');
  const main    = document.getElementById('main-content');
  const updated = document.getElementById('last-updated');

  try {
    priceData = await loadData();

    if (updated) updated.textContent = formatDate(priceData.last_updated);

    renderGovCap(priceData);
    renderCards(priceData);
    renderStats(priceData);

    const allKeys = Object.keys(FUEL_META);
    renderLegend(allKeys);
    renderChart(priceData.history, allKeys);
    setupFilters(priceData.history);

    if (loading) loading.classList.add('hidden');
    if (main)    main.classList.remove('hidden');
  } catch (err) {
    console.error('Failed to load price data:', err);
    if (loading) loading.classList.add('hidden');
    if (error)   error.classList.remove('hidden');
  }
}

document.addEventListener('DOMContentLoaded', init);
