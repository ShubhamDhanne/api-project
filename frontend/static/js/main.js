/**
 * main.js — Shared utilities used across all HealthTrack pages.
 * Includes: auth helpers, API wrapper, toast notifications, navbar init.
 */

// ── Auth helpers ─────────────────────────────────────────────────────────────

function getToken() {
  return localStorage.getItem('ht_token');
}

function getUser() {
  try {
    return JSON.parse(localStorage.getItem('ht_user') || '{}');
  } catch {
    return {};
  }
}

function saveAuth(token, user) {
  localStorage.setItem('ht_token', token);
  localStorage.setItem('ht_user', JSON.stringify(user));
}

function logout() {
  localStorage.removeItem('ht_token');
  localStorage.removeItem('ht_user');
  window.location.href = '/login';
}

/** Redirect to /login if no token. Call at top of every protected page. */
function requireAuth() {
  const token = getToken();
  if (!token) {
    window.location.href = '/login';
    return false;
  }
  return true;
}

// ── API wrapper ───────────────────────────────────────────────────────────────

/**
 * Authenticated fetch wrapper.
 * @param {string} endpoint  - API path, e.g. '/api/health'
 * @param {string} method    - HTTP method
 * @param {object|null} body - JSON body
 * @returns {Promise<object>} Parsed JSON response body
 */
async function apiCall(endpoint, method = 'GET', body = null) {
  const token = getToken();
  const opts = {
    method,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': token ? `Bearer ${token}` : '',
    },
  };
  if (body) opts.body = JSON.stringify(body);

  const res = await fetch(endpoint, opts);

  if (res.status === 401) {
    logout();
    return null;
  }

  return res.json();
}

// ── Toast notifications ───────────────────────────────────────────────────────

/**
 * Show a Bootstrap toast notification.
 * @param {string} message  - Text to display
 * @param {'success'|'danger'|'warning'|'info'} type
 */
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const icons = {
    success: 'fas fa-check-circle',
    danger:  'fas fa-times-circle',
    warning: 'fas fa-exclamation-triangle',
    info:    'fas fa-info-circle',
  };

  const id = 'toast-' + Date.now();
  const html = `
    <div id="${id}" class="toast align-items-center text-white bg-${type} border-0" role="alert" aria-live="assertive">
      <div class="d-flex">
        <div class="toast-body">
          <i class="${icons[type] || icons.info} me-2"></i>${message}
        </div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
      </div>
    </div>`;
  container.insertAdjacentHTML('beforeend', html);
  const el = document.getElementById(id);
  const toast = new bootstrap.Toast(el, { delay: 3500 });
  toast.show();
  el.addEventListener('hidden.bs.toast', () => el.remove());
}

// ── Navbar init ───────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  const token = getToken();
  const authed = document.getElementById('nav-authed');
  const unauthed = document.getElementById('nav-unauthed');
  const nameEl = document.getElementById('nav-username');

  if (token) {
    if (authed) authed.style.removeProperty('display');
    if (unauthed) unauthed.style.display = 'none';
    if (nameEl) {
      const user = getUser();
      nameEl.textContent = user.name ? `Hi, ${user.name}` : '';
    }
  } else {
    if (authed) authed.style.display = 'none';
    if (unauthed) unauthed.style.removeProperty('display');
  }
});

// ── Date helpers ──────────────────────────────────────────────────────────────

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function formatDate(iso) {
  if (!iso) return '—';
  const [y, m, d] = iso.split('-');
  return `${d}/${m}/${y}`;
}

/** Compute sleep hours from HH:MM sleep and wake times. */
function computeSleepHours(sleepTime, wakeTime) {
  if (!sleepTime || !wakeTime) return null;
  const [sh, sm] = sleepTime.split(':').map(Number);
  const [wh, wm] = wakeTime.split(':').map(Number);
  let mins = (wh * 60 + wm) - (sh * 60 + sm);
  if (mins < 0) mins += 24 * 60;  // cross-midnight
  return Math.round((mins / 60) * 10) / 10;
}
