/**
 * dashboard.js — Loads and renders dashboard data:
 *   - Today's health stats
 *   - Weekly steps mini-chart
 *   - Routine Stability score
 *   - Recent records table
 */

let weekStepsChart = null;

document.addEventListener('DOMContentLoaded', async () => {
  if (!requireAuth()) return;

  // Display user's name
  const user = getUser();
  const nameEl = document.getElementById('user-name');
  if (nameEl && user.name) nameEl.textContent = user.name.split(' ')[0];

  // Display today's date
  const todayEl = document.getElementById('today-date');
  if (todayEl) {
    todayEl.textContent = new Date().toLocaleDateString('en-GB', {
      weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
    });
  }

  // Load all data in parallel
  await Promise.all([
    loadTodayStats(),
    loadWeeklyChart(),
    loadRecentRecords(),
    loadStabilityScore(),
  ]);

  document.getElementById('page-loader').classList.add('d-none');
  document.getElementById('dashboard-content').classList.remove('d-none');

  initBmiCalculator();
});

// ── Today's stats ─────────────────────────────────────────────────────────────

async function loadTodayStats() {
  const today = todayISO();
  const res = await apiCall(`/api/analytics/daily?date=${today}`);

  if (!res || !res.success) {
    document.getElementById('no-today-data').classList.remove('d-none');
    return;
  }

  const a = res.data;

  setValue('stat-steps', a.steps ? a.steps.toLocaleString() : '—');
  setValue('stat-calories', a.calories_burned ? `${a.calories_burned} kcal` : '—');
  setValue('stat-sleep', a.sleep_hours ? `${a.sleep_hours}h` : '—');
  setValue('stat-hr', a.heart_rate ? `${a.heart_rate} bpm` : '—');

  // Steps progress bar
  const bar = document.getElementById('steps-bar');
  const goalText = document.getElementById('steps-goal-text');
  if (bar && a.steps) {
    bar.style.width = Math.min((a.steps / 10000) * 100, 100) + '%';
    if (goalText) goalText.textContent = `${a.step_goal_pct}% of 10k goal`;
  }

  // Sleep quality badge
  const badge = document.getElementById('sleep-badge');
  if (badge && a.sleep_quality) {
    const colours = {
      Excellent: 'bg-success', Good: 'bg-primary',
      Fair: 'bg-warning text-dark', Poor: 'bg-danger',
    };
    badge.className = `badge mt-1 ${colours[a.sleep_quality] || 'bg-secondary'}`;
    badge.textContent = a.sleep_quality;
  }
}

// ── Weekly steps chart ────────────────────────────────────────────────────────

async function loadWeeklyChart() {
  const sevenDaysAgo = new Date();
  sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 6);
  const start = sevenDaysAgo.toISOString().slice(0, 10);

  const res = await apiCall(`/api/analytics/weekly?start_date=${start}`);

  if (!res || !res.success || !res.data.daily_breakdown?.length) {
    document.getElementById('no-weekly-data')?.classList.remove('d-none');
    return;
  }

  const breakdown = res.data.daily_breakdown;
  const labels = breakdown.map(d => formatDate(d.date));
  const steps = breakdown.map(d => d.steps || 0);

  const ctx = document.getElementById('week-steps-chart')?.getContext('2d');
  if (!ctx) return;

  weekStepsChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Steps',
        data: steps,
        backgroundColor: 'rgba(13,110,253,0.7)',
        borderRadius: 6,
      }],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        y: { beginAtZero: true, ticks: { stepSize: 2000 } },
      },
    },
  });
}

// ── Stability score ───────────────────────────────────────────────────────────

async function loadStabilityScore() {
  const spinner = document.getElementById('stability-spinner');
  const resultEl = document.getElementById('stability-result');
  const errorEl = document.getElementById('stability-error');

  const res = await apiCall('/api/analytics/stability?days=7');

  if (spinner) spinner.classList.add('d-none');

  if (!res || !res.success) {
    if (errorEl) {
      errorEl.textContent = (res?.error) || 'Not enough data for stability score. Add at least 2 days.';
      errorEl.classList.remove('d-none');
    }
    return;
  }

  const rsi = res.data.routine_stability_index;
  if (!rsi) return;

  const scoreEl = document.getElementById('stability-score');
  const labelEl = document.getElementById('stability-label');
  const recsEl = document.getElementById('stability-recs');

  if (scoreEl) scoreEl.textContent = rsi.overall_score;
  if (labelEl) {
    labelEl.textContent = rsi.label;
    labelEl.className = `badge fs-6 mt-1 ${stabilityBadgeClass(rsi.label)}`;
  }

  const recs = res.data.recommendations || [];
  if (recsEl && recs.length) {
    recsEl.innerHTML = recs.slice(0, 3).map(r => `<p class="mb-1">${r}</p>`).join('');
  }

  if (resultEl) resultEl.classList.remove('d-none');
}

// ── Recent records table ──────────────────────────────────────────────────────

async function loadRecentRecords() {
  const tbody = document.getElementById('recent-records-body');
  const res = await apiCall('/api/health');

  if (!res || !res.success || !res.data.length) {
    if (tbody) tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-3">No records yet.</td></tr>';
    return;
  }

  const rows = res.data.slice(0, 5).map(r => {
    const cal = r.calories_burned || ((r.steps || 0) * 0.04).toFixed(0);
    return `<tr>
      <td><strong>${formatDate(r.date)}</strong></td>
      <td>${r.steps ? r.steps.toLocaleString() : '—'}</td>
      <td>${r.sleep_hours ? r.sleep_hours + 'h' : '—'}</td>
      <td>${r.heart_rate ? r.heart_rate + ' bpm' : '—'}</td>
      <td>${cal ? cal + ' kcal' : '—'}</td>
      <td>
        <a href="/health/edit/${r.date}" class="btn btn-sm btn-outline-primary me-1">
          <i class="fas fa-edit"></i>
        </a>
      </td>
    </tr>`;
  }).join('');

  if (tbody) tbody.innerHTML = rows;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function setValue(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
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

// ── BMI Calculator ────────────────────────────────────────────────────────────

function initBmiCalculator() {
  const btn = document.getElementById('bmi-btn');
  if (!btn) return;

  btn.addEventListener('click', async () => {
    const weight = parseFloat(document.getElementById('bmi-weight')?.value);
    const height = parseFloat(document.getElementById('bmi-height')?.value);
    const resultEl = document.getElementById('bmi-result');
    const errorEl = document.getElementById('bmi-error');
    const spinner = document.getElementById('bmi-spinner');
    const icon = document.getElementById('bmi-icon');

    errorEl.classList.add('d-none');
    resultEl.classList.add('d-none');

    if (!weight || !height || isNaN(weight) || isNaN(height)) {
      errorEl.textContent = 'Please enter both weight (kg) and height (cm).';
      errorEl.classList.remove('d-none');
      return;
    }

    btn.disabled = true;
    spinner.classList.remove('d-none');
    icon.classList.add('d-none');

    const res = await apiCall('/api/analytics/bmi', 'POST', { weight_kg: weight, height_cm: height });

    btn.disabled = false;
    spinner.classList.add('d-none');
    icon.classList.remove('d-none');

    if (!res?.success) {
      errorEl.textContent = res?.error || 'BMI calculation failed.';
      errorEl.classList.remove('d-none');
      return;
    }

    const d = res.data;
    document.getElementById('bmi-value').textContent = d.bmi ?? '—';
    document.getElementById('bmi-category').textContent = d.category ?? '—';
    document.getElementById('bmi-healthy-range').textContent = d.healthy_bmi_range ?? '18.5 – 24.9';

    // colour-code the BMI value
    const bmiVal = document.getElementById('bmi-value');
    const bmi = parseFloat(d.bmi);
    if (bmi < 18.5)       bmiVal.className = 'h3 fw-bold mb-0 text-warning';
    else if (bmi < 25)    bmiVal.className = 'h3 fw-bold mb-0 text-success';
    else if (bmi < 30)    bmiVal.className = 'h3 fw-bold mb-0 text-warning';
    else                  bmiVal.className = 'h3 fw-bold mb-0 text-danger';

    resultEl.classList.remove('d-none');
  });
}
