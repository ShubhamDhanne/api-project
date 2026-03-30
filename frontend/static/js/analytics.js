/**
 * analytics.js — Loads and renders analytics charts and stability score.
 *   - Weekly / Monthly toggle
 *   - Chart.js bar/line charts for steps, sleep, calories
 *   - Routine Stability Index from classmate API
 */

let stepsChart = null;
let sleepChart = null;
let caloriesChart = null;
let currentPeriod = 'weekly';

document.addEventListener('DOMContentLoaded', async () => {
  if (!requireAuth()) return;

  initPeriodToggle();
  initDateDefaults();
  document.getElementById('load-btn')?.addEventListener('click', loadAnalytics);
  document.getElementById('refresh-stability')?.addEventListener('click', loadStability);

  // Auto-load on page open
  await loadAnalytics();
  await loadStability();
});

// ── Period toggle ─────────────────────────────────────────────────────────────

function initPeriodToggle() {
  document.querySelectorAll('[data-period]').forEach(btn => {
    btn.addEventListener('click', () => {
      currentPeriod = btn.dataset.period;
      document.querySelectorAll('[data-period]').forEach(b => {
        b.classList.toggle('active', b === btn);
        b.classList.toggle('btn-primary', b === btn);
        b.classList.toggle('btn-outline-primary', b !== btn);
      });

      const weeklyControls = document.getElementById('weekly-controls');
      const monthlyControls = document.getElementById('monthly-controls');
      if (currentPeriod === 'weekly') {
        weeklyControls?.classList.remove('d-none');
        monthlyControls?.classList.add('d-none');
      } else {
        weeklyControls?.classList.add('d-none');
        monthlyControls?.classList.remove('d-none');
      }
    });
  });
}

// ── Default date values ───────────────────────────────────────────────────────

function initDateDefaults() {
  const weekStart = document.getElementById('week-start');
  if (weekStart) {
    const d = new Date();
    d.setDate(d.getDate() - 6);
    weekStart.value = d.toISOString().slice(0, 10);
  }

  const monthPicker = document.getElementById('month-picker');
  if (monthPicker) {
    monthPicker.value = new Date().toISOString().slice(0, 7);
  }
}

// ── Load analytics data ───────────────────────────────────────────────────────

async function loadAnalytics() {
  const loader = document.getElementById('analytics-loader');
  const errorEl = document.getElementById('analytics-error');
  const content = document.getElementById('analytics-content');

  loader?.classList.remove('d-none');
  errorEl?.classList.add('d-none');
  content?.classList.add('d-none');

  let res;
  if (currentPeriod === 'weekly') {
    const start = document.getElementById('week-start')?.value;
    res = await apiCall(`/api/analytics/weekly?start_date=${start}`);
  } else {
    const month = document.getElementById('month-picker')?.value || new Date().toISOString().slice(0, 7);
    const [year, m] = month.split('-');
    res = await apiCall(`/api/analytics/monthly?year=${year}&month=${m}`);
  }

  loader?.classList.add('d-none');

  if (!res?.success) {
    errorEl.textContent = res?.error || 'No data found for this period.';
    errorEl?.classList.remove('d-none');
    return;
  }

  const data = res.data;
  renderSummaryCards(data);
  renderCharts(data);
  content?.classList.remove('d-none');
}

// ── Summary cards ─────────────────────────────────────────────────────────────

function renderSummaryCards(data) {
  setText('an-avg-steps', data.avg_steps?.toLocaleString() || '—');
  setText('an-avg-sleep', data.avg_sleep_hours ? `${data.avg_sleep_hours}h` : '—');
  setText('an-avg-calories', data.avg_calories ? `${data.avg_calories} kcal` : '—');
  setText('an-avg-hr', data.avg_heart_rate ? `${data.avg_heart_rate} bpm` : '—');
}

// ── Charts ────────────────────────────────────────────────────────────────────

function renderCharts(data) {
  const breakdown = (data.daily_breakdown || []).sort((a, b) => a.date.localeCompare(b.date));
  const labels = breakdown.map(d => formatDate(d.date));

  // Destroy existing charts before recreating
  if (stepsChart) stepsChart.destroy();
  if (sleepChart) sleepChart.destroy();
  if (caloriesChart) caloriesChart.destroy();

  const stepsCtx = document.getElementById('steps-chart')?.getContext('2d');
  if (stepsCtx) {
    stepsChart = new Chart(stepsCtx, {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: 'Steps',
          data: breakdown.map(d => d.steps || 0),
          backgroundColor: 'rgba(13,110,253,0.75)',
          borderRadius: 5,
        }],
      },
      options: chartOptions('Steps'),
    });
  }

  const sleepCtx = document.getElementById('sleep-chart')?.getContext('2d');
  if (sleepCtx) {
    sleepChart = new Chart(sleepCtx, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: 'Sleep Hours',
          data: breakdown.map(d => d.sleep_hours || 0),
          borderColor: '#6f42c1',
          backgroundColor: 'rgba(111,66,193,0.15)',
          tension: 0.4,
          fill: true,
          pointRadius: 4,
        }],
      },
      options: chartOptions('Hours', 10),
    });
  }

  const calCtx = document.getElementById('calories-chart')?.getContext('2d');
  if (calCtx) {
    caloriesChart = new Chart(calCtx, {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: 'Calories',
          data: breakdown.map(d => d.calories || 0),
          backgroundColor: 'rgba(220,53,69,0.7)',
          borderRadius: 5,
        }],
      },
      options: chartOptions('kcal'),
    });
  }
}

function chartOptions(yLabel, suggestedMax = null) {
  return {
    responsive: true,
    plugins: { legend: { display: false } },
    scales: {
      y: {
        beginAtZero: true,
        suggestedMax,
        title: { display: true, text: yLabel },
      },
    },
  };
}

// ── Stability score ───────────────────────────────────────────────────────────

async function loadStability() {
  const loaderEl = document.getElementById('stability-loader');
  const dataEl = document.getElementById('stability-data');
  const errorMsg = document.getElementById('stability-error-msg');

  loaderEl?.classList.remove('d-none');
  dataEl?.classList.add('d-none');
  errorMsg?.classList.add('d-none');

  const res = await apiCall('/api/analytics/stability?days=7');

  loaderEl?.classList.add('d-none');

  if (!res?.success) {
    errorMsg.textContent = res?.error || 'Not enough data for stability score.';
    errorMsg?.classList.remove('d-none');
    return;
  }

  const rsi = res.data.routine_stability_index;
  if (!rsi) { errorMsg.textContent = 'No stability data returned.'; errorMsg?.classList.remove('d-none'); return; }

  setText('stab-score', rsi.overall_score);
  const labelEl = document.getElementById('stab-label');
  if (labelEl) {
    labelEl.textContent = rsi.label;
    labelEl.className = `badge fs-5 px-3 py-2 ${stabilityBadgeClass(rsi.label)}`;
  }

  // Score breakdown
  const breakdown = rsi.breakdown || {};
  setBar('stab-sleep-bar', breakdown.sleep?.score);
  setBar('stab-meals-bar', breakdown.meals?.score);
  setBar('stab-exercise-bar', breakdown.exercise?.score);
  setText('stab-sleep-score', breakdown.sleep?.score != null ? `${breakdown.sleep.score}` : '—');
  setText('stab-meals-score', breakdown.meals?.score != null ? `${breakdown.meals.score}` : '—');
  setText('stab-exercise-score', breakdown.exercise?.score != null ? `${breakdown.exercise.score}` : '—');

  // Recommendations
  const recsEl = document.getElementById('stab-recs');
  if (recsEl) {
    const recs = res.data.recommendations || [];
    recsEl.innerHTML = recs.map(r => `<li>${r}</li>`).join('') || '<li>Keep up the great work!</li>';
  }

  // Alerts
  const alertsEl = document.getElementById('stab-alerts');
  const alerts = res.data.irregularity_alerts || [];
  if (alertsEl && alerts.length) {
    alertsEl.innerHTML = alerts.map(a =>
      `<div class="alert alert-warning py-1 small mb-1">${a}</div>`
    ).join('');
  }

  dataEl?.classList.remove('d-none');
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

function setBar(id, score) {
  const el = document.getElementById(id);
  if (el && score != null) el.style.width = `${Math.min(score, 100)}%`;
}

function stabilityBadgeClass(label) {
  const map = {
    'Excellent': 'badge-excellent',
    'Good': 'badge-good',
    'Moderate': 'badge-moderate',
    'Needs Improvement': 'badge-needs',
    'Critical': 'badge-critical',
  };
  return map[label] || 'bg-secondary';
}
