// Helper to show Bootstrap toasts
function showToast(message, type = 'info') {
  const container = document.getElementById('reportToastContainer');
  const toastEl = document.createElement('div');
  toastEl.className = `toast align-items-center text-bg-${type} border-0`;
  toastEl.role = 'alert';
  toastEl.ariaLive = 'assertive';
  toastEl.ariaAtomic = 'true';
  toastEl.dataset.bsDelay = 3000;
  toastEl.innerHTML = `
    <div class="d-flex">
      <div class="toast-body">
        ${message}
      </div>
      <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
    </div>
  `;
  container.appendChild(toastEl);
  const toast = new bootstrap.Toast(toastEl);
  toast.show();
  toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
}

document.addEventListener('DOMContentLoaded', () => {
  const profileId = window.profileUserId;
  const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

  // Categories (static)
  const categories = [
    { value: 'spam', label: 'Spam' },
    { value: 'harassment', label: 'Harassment' },
    { value: 'hate_speech', label: 'Hate speech' },
    { value: 'inappropriate', label: 'Inappropriate' },
    { value: 'other', label: 'Other' },
  ];
  const newCatSelect = document.getElementById('newReportCategory');
  newCatSelect.innerHTML = categories
    .map(c => `<option value="${c.value}">${c.label}</option>`)
    .join('');

  // Wire up buttons
  document.getElementById('addReportBtn').addEventListener('click', addReport);
  document.getElementById('reportModal')
    .addEventListener('show.bs.modal', loadReports);

  async function loadReports() {
    const listEl = document.getElementById('reportList');
    listEl.innerHTML = `<p class="text-center text-muted">Loading…</p>`;

    try {
      const res = await fetch(`/api/user/${profileId}/reports`, {
        credentials: 'same-origin',
        headers: { 'X-CSRFToken': csrfToken }
      });
      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || data.message || res.statusText);
      }

      const reports = data.reports;
      if (!reports.length) {
        listEl.innerHTML = `<p class="text-center">No reports yet.</p>`;
        return;
      }

      listEl.innerHTML = reports.map(r => {
        const statusBadge = `
          <span class="badge bg-secondary text-uppercase">
            <i class="fa-solid fa-info-circle me-2"></i>${r.status}
          </span>`;
        const createdAt = `
          <small class="text-muted">
            <i class="fa-solid fa-clock me-1"></i>
            ${new Date(r.created_at).toLocaleString()} UTC
          </small>`;
        const opts = categories
          .map(c => `<option value="${c.value}" ${c.value === r.category ? 'selected' : ''}>${c.label}</option>`)
          .join('');

        return `
          <div class="report-item mb-3" data-id="${r.id}">
            <div class="d-flex justify-content-between align-items-center mb-2">
              ${statusBadge}
              ${createdAt}
            </div>
            <div class="mb-2">
              <label class="form-label"><i class="fa-solid fa-list"></i> Category</label>
              <select class="form-select form-select-sm category-select">${opts}</select>
            </div>
            <div class="mb-2">
              <label class="form-label"><i class="fa-solid fa-pencil-alt"></i> Reason</label>
              <textarea class="form-control form-control-sm reason-input" rows="2">${r.reason || ''}</textarea>
            </div>
            <div class="d-flex gap-2">
              <button class="btn btn-sm btn-primary edit-report-btn">
                <i class="fa-solid fa-floppy-disk"></i> Save
              </button>
              <button class="btn btn-sm btn-danger delete-report-btn">
                <i class="fa-solid fa-trash"></i> Delete
              </button>
            </div>
          </div>`;
      }).join('');

      // Hook up the newly rendered buttons
      document.querySelectorAll('.edit-report-btn')
        .forEach(btn => btn.addEventListener('click', handleEdit));
      document.querySelectorAll('.delete-report-btn')
        .forEach(btn => btn.addEventListener('click', handleDelete));

    } catch (err) {
      listEl.innerHTML = `<p class="text-danger">Failed to load: ${err.message}</p>`;
      console.error(err);
    }
  }

  async function addReport() {
    const btn = document.getElementById('addReportBtn');
    btn.disabled = true;
    document.getElementById('reportFeedback').innerHTML = '';

    const category = newCatSelect.value;
    const reason = document.getElementById('newReportReason').value.trim();
    if (!reason) {
      document.getElementById('reportFeedback')
        .innerHTML = `<p class="text-danger">Please provide a reason.</p>`;
      btn.disabled = false;
      return;
    }

    try {
      const res = await fetch(`/api/user/${profileId}/reports`, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({ category, reason })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || data.message || res.statusText);
      }

      showToast('Report submitted successfully!', 'success');
      document.getElementById('newReportReason').value = '';
      newCatSelect.value = 'other';
      loadReports();
    } catch (err) {
      showToast(`Error: ${err.message}`, 'danger');
    } finally {
      btn.disabled = false;
    }
  }

  async function handleEdit(e) {
    const btn = e.currentTarget;
    const container = btn.closest('.report-item');
    const id = container.dataset.id;
    const category = container.querySelector('.category-select').value;
    const reason = container.querySelector('.reason-input').value.trim();

    btn.disabled = true;
    try {
      const res = await fetch(`/api/user/${profileId}/reports/${id}`, {
        method: 'PATCH',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({ category, reason })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || data.message || res.statusText);
      }

      showToast('Report updated.', 'success');
      loadReports();
    } catch (err) {
      showToast(`Update failed: ${err.message}`, 'danger');
    } finally {
      btn.disabled = false;
    }
  }

  async function handleDelete(e) {
    if (!confirm('Are you sure you want to delete this report?')) return;
    const btn = e.currentTarget;
    const container = btn.closest('.report-item');
    const id = container.dataset.id;

    btn.disabled = true;
    try {
      const res = await fetch(`/api/user/${profileId}/reports/${id}`, {
        method: 'DELETE',
        credentials: 'same-origin',
        headers: { 'X-CSRFToken': csrfToken }
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || data.message || res.statusText);
      }

      showToast('Report deleted.', 'warning');
      loadReports();
    } catch (err) {
      showToast(`Delete failed: ${err.message}`, 'danger');
      btn.disabled = false;
    }
  }
});
