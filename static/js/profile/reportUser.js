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
    const profileId = profileUserId;
    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

    // Load reports when modal opens
    const reportModal = document.getElementById('reportModal');
    reportModal.addEventListener('show.bs.modal', loadReports);

    // Populate categories once
    const categories = [{
        value: 'spam',
        label: 'Spam'
      },
      {
        value: 'harassment',
        label: 'Harassment'
      },
      {
        value: 'hate_speech',
        label: 'Hate speech'
      },
      {
        value: 'inappropriate',
        label: 'Inappropriate'
      },
      {
        value: 'other',
        label: 'Other'
      },
    ];
    const newCatSelect = document.getElementById('newReportCategory');
    newCatSelect.innerHTML = categories.map(c => `<option value="${c.value}">${c.label}</option>`).join('');

    document.getElementById('addReportBtn').addEventListener('click', addReport);

    async function loadReports() {
      const listEl = document.getElementById('reportList');
      listEl.innerHTML = `<p class="text-center text-muted">Loading…</p>`;
      try {
        const res = await fetch(`/api/user/${profileId}/reports`, {
          credentials: 'same-origin',
          headers: {
            'X-CSRFToken': csrfToken
          }
        });
        const {
          reports
        } = await res.json();
        if (!reports.length) {
          listEl.innerHTML = `<p class="text-center">No reports yet.</p>`;
          return;
        }
        listEl.innerHTML = reports.map(r => {
          const statusBadge = `<span class="badge bg-secondary text-uppercase"><i class="fa-solid fa-info-circle me-2"></i>${r.status}</span>`;
          const createdAt = `<small class="text-muted"><i class="fa-solid fa-clock me-1"></i>${new Date(r.createdAt).toLocaleString()} UTC</small>`;
          const opts = categories.map(c => `<option value="${c.value}" ${c.value === r.category? 'selected':''}>${c.label}</option>`).join('');
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
              <textarea class="form-control form-control-sm reason-input" rows="2">${r.reason||''}</textarea>
            </div>
            <div class="d-flex gap-2">
              <button class="btn btn-sm btn-primary edit-report-btn"><i class="fa-solid fa-floppy-disk"></i> Save</button>
              <button class="btn btn-sm btn-danger delete-report-btn"><i class="fa-solid fa-trash"></i> Delete</button>
            </div>
          </div>`;
        }).join('');
        document.querySelectorAll('.edit-report-btn').forEach(btn => btn.addEventListener('click', handleEdit));
        document.querySelectorAll('.delete-report-btn').forEach(btn => btn.addEventListener('click', handleDelete));
      } catch (err) {
        listEl.innerHTML = `<p class="text-danger">Failed to load.</p>`;
        console.error(err);
      }
    }

    async function addReport() {
      const btn = document.getElementById('addReportBtn');
      btn.disabled = true;
      const feedback = document.getElementById('reportFeedback');
      feedback.innerHTML = '';
      const category = newCatSelect.value;
      const reason = document.getElementById('newReportReason').value.trim();
      if (!reason) {
        feedback.innerHTML = `<p class="text-danger">Please provide a reason.</p>`;
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
          body: JSON.stringify({
            category,
            reason
          })
        });
        const json = await res.json();
        if (!json.success) throw new Error(json.message);
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
      const container = e.target.closest('.report-item');
      const id = container.dataset.id;
      const category = container.querySelector('.category-select').value;
      const reason = container.querySelector('.reason-input').value.trim();
      e.target.disabled = true;
      try {
        const res = await fetch(`/api/user/${profileId}/reports/${id}`, {
          method: 'PATCH',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
          },
          body: JSON.stringify({
            category,
            reason
          })
        });
        const json = await res.json();
        if (!json.success) throw new Error(json.message);
        showToast('Report updated.', 'success');
        loadReports();
      } catch (err) {
        showToast(`Update failed: ${err.message}`, 'danger');
      } finally {
        e.target.disabled = false;
      }
    }

    async function handleDelete(e) {
      if (!confirm('Are you sure you want to delete this report?')) return;
      const container = e.target.closest('.report-item');
      const id = container.dataset.id;
      e.target.disabled = true;
      try {
        const res = await fetch(`/api/user/${profileId}/reports/${id}`, {
          method: 'DELETE',
          credentials: 'same-origin',
          headers: {
            'X-CSRFToken': csrfToken
          }
        });
        const json = await res.json();
        if (!json.success) throw new Error(json.message);
        showToast('Report deleted.', 'warning');
        loadReports();
      } catch (err) {
        showToast(`Delete failed: ${err.message}`, 'danger');
        e.target.disabled = false;
      }
    }
  });