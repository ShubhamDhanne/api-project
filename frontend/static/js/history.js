/**
 * history.js — Health records history page.
 *   - Loads all records with optional date filter
 *   - Paginated table with edit/delete actions
 *   - Confirm-delete modal
 */

const PAGE_SIZE = 10;
let allRecords = [];
let currentPage = 1;
let pendingDeleteDate = null;
let deleteModalInstance = null;

document.addEventListener('DOMContentLoaded', async () => {
  if (!requireAuth()) return;

  deleteModalInstance = new bootstrap.Modal(document.getElementById('delete-modal'));

  document.getElementById('apply-filter')?.addEventListener('click', applyFilter);
  document.getElementById('clear-filter')?.addEventListener('click', clearFilter);
  document.getElementById('confirm-delete-btn')?.addEventListener('click', confirmDelete);

  await loadRecords();
});

// ── Load records ──────────────────────────────────────────────────────────────

async function loadRecords(startDate = null, endDate = null) {
  const loader = document.getElementById('history-loader');
  const content = document.getElementById('history-content');
  const noRecords = document.getElementById('no-records');

  loader?.classList.remove('d-none');
  content?.classList.add('d-none');
  noRecords?.classList.add('d-none');

  let url = '/api/health';
  const params = [];
  if (startDate) params.push(`start_date=${startDate}`);
  if (endDate) params.push(`end_date=${endDate}`);
  if (params.length) url += '?' + params.join('&');

  const res = await apiCall(url);

  loader?.classList.add('d-none');

  if (!res?.success || !res.data.length) {
    noRecords?.classList.remove('d-none');
    return;
  }

  allRecords = res.data;
  currentPage = 1;
  renderPage();
  content?.classList.remove('d-none');
}

// ── Render current page ───────────────────────────────────────────────────────

function renderPage() {
  const tbody = document.getElementById('history-body');
  const countEl = document.getElementById('records-count');
  const paginationEl = document.getElementById('pagination-controls');

  const total = allRecords.length;
  const start = (currentPage - 1) * PAGE_SIZE;
  const pageRecords = allRecords.slice(start, start + PAGE_SIZE);

  if (countEl) {
    countEl.textContent = `Showing ${start + 1}–${Math.min(start + PAGE_SIZE, total)} of ${total} records`;
  }

  if (tbody) {
    tbody.innerHTML = pageRecords.map(r => {
      const ex = r.exercise || {};
      const cal = r.calories_burned || ((r.steps || 0) * 0.04).toFixed(0);
      return `<tr>
        <td><strong>${formatDate(r.date)}</strong></td>
        <td>${r.steps ? r.steps.toLocaleString() : '—'}</td>
        <td>${r.heart_rate ? r.heart_rate + ' bpm' : '—'}</td>
        <td>${r.sleep_hours ? r.sleep_hours + 'h' : '—'}</td>
        <td>${r.sleep_time || '—'}</td>
        <td>${r.wake_time || '—'}</td>
        <td>${cal ? cal + ' kcal' : '—'}</td>
        <td>${r.weight_kg ? r.weight_kg + ' kg' : '—'}</td>
        <td>${ex.type ? `${ex.type} ${ex.duration_minutes ? '(' + ex.duration_minutes + 'm)' : ''}` : '—'}</td>
        <td>
          <a href="/health/edit/${r.date}" class="btn btn-sm btn-outline-primary me-1" title="Edit">
            <i class="fas fa-edit"></i>
          </a>
          <button class="btn btn-sm btn-outline-danger" title="Delete"
                  onclick="openDeleteModal('${r.date}')">
            <i class="fas fa-trash"></i>
          </button>
        </td>
      </tr>`;
    }).join('');
  }

  renderPagination(total, paginationEl);
}

// ── Pagination ────────────────────────────────────────────────────────────────

function renderPagination(total, container) {
  if (!container) return;
  const pages = Math.ceil(total / PAGE_SIZE);
  if (pages <= 1) { container.innerHTML = ''; return; }

  let html = '<nav><ul class="pagination pagination-sm mb-0">';
  html += `<li class="page-item ${currentPage === 1 ? 'disabled' : ''}">
    <button class="page-link" onclick="gotoPage(${currentPage - 1})">
      <i class="fas fa-chevron-left"></i>
    </button>
  </li>`;

  for (let p = 1; p <= pages; p++) {
    html += `<li class="page-item ${p === currentPage ? 'active' : ''}">
      <button class="page-link" onclick="gotoPage(${p})">${p}</button>
    </li>`;
  }

  html += `<li class="page-item ${currentPage === pages ? 'disabled' : ''}">
    <button class="page-link" onclick="gotoPage(${currentPage + 1})">
      <i class="fas fa-chevron-right"></i>
    </button>
  </li></ul></nav>`;

  container.innerHTML = html;
}

function gotoPage(p) {
  const pages = Math.ceil(allRecords.length / PAGE_SIZE);
  if (p < 1 || p > pages) return;
  currentPage = p;
  renderPage();
}

// ── Filter ────────────────────────────────────────────────────────────────────

async function applyFilter() {
  const start = document.getElementById('filter-start')?.value;
  const end = document.getElementById('filter-end')?.value;
  await loadRecords(start || null, end || null);
}

async function clearFilter() {
  const startEl = document.getElementById('filter-start');
  const endEl = document.getElementById('filter-end');
  if (startEl) startEl.value = '';
  if (endEl) endEl.value = '';
  await loadRecords();
}

// ── Delete ────────────────────────────────────────────────────────────────────

function openDeleteModal(date) {
  pendingDeleteDate = date;
  const textEl = document.getElementById('delete-date-text');
  if (textEl) textEl.textContent = formatDate(date);
  deleteModalInstance?.show();
}

async function confirmDelete() {
  if (!pendingDeleteDate) return;

  const btn = document.getElementById('confirm-delete-btn');
  const spinner = document.getElementById('delete-spinner');
  btn.disabled = true;
  spinner?.classList.remove('d-none');

  const res = await apiCall(`/api/health/${pendingDeleteDate}`, 'DELETE');

  btn.disabled = false;
  spinner?.classList.add('d-none');
  deleteModalInstance?.hide();

  if (res?.success) {
    showToast('Record deleted successfully.', 'success');
    allRecords = allRecords.filter(r => r.date !== pendingDeleteDate);
    pendingDeleteDate = null;
    if (allRecords.length === 0) {
      document.getElementById('history-content')?.classList.add('d-none');
      document.getElementById('no-records')?.classList.remove('d-none');
    } else {
      if (currentPage > Math.ceil(allRecords.length / PAGE_SIZE)) currentPage--;
      renderPage();
    }
  } else {
    showToast(res?.error || 'Failed to delete record.', 'danger');
  }
}
