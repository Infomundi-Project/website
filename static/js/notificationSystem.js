document.addEventListener("DOMContentLoaded", () => {
  const inboxBtn        = document.getElementById("inboxBtn");
  const unreadBadge     = document.getElementById("unreadBadge");
  const notificationsList = document.getElementById("notificationsList");
  const markAllReadBtn  = document.getElementById("markAllReadBtn");
  const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

  // Helper: format ISO date
  function formatDate(iso) {
    const d = new Date(iso);
    return d.toLocaleString(); 
  }

  // 1️⃣ Load the unread count on page load (and maybe poll every minute)
  function loadUnreadCount() {
    fetch("/api/notifications/unread_count", { credentials: "include", headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        } })
      .then(res => res.json())
      .then(data => {
        unreadBadge.textContent = data.unread_count;
        unreadBadge.style.display = data.unread_count > 0 ? "inline-block" : "none";
      });
  }

  // 2️⃣ When clicking the inbox, fetch the list and show modal
  inboxBtn.addEventListener("click", () => {
    fetch("/api/notifications?per_page=50", { credentials: "include", headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        } })
      .then(res => res.json())
      .then(data => {
        notificationsList.innerHTML = ""; // clear old
        if (data.notifications.length === 0) {
          notificationsList.innerHTML = `<li class="list-group-item text-center text-muted">No notifications</li>`;
        } else {
          data.notifications.forEach(n => {
            const li = document.createElement("li");
            li.className = `list-group-item d-flex justify-content-between align-items-start ${n.is_read ? "" : "fw-bold"}`;
            li.innerHTML = `
              <a href="${n.url || '#'}" class="flex-grow-1 text-decoration-none text-dark">
                <div>${n.message}</div>
                <small class="text-muted">${formatDate(n.created_at)}</small>
              </a>
              ${n.is_read 
                ? "" 
                : `<button data-id="${n.id}" class="btn btn-sm btn-link mark-read-btn">Mark read</button>`}
            `;
            notificationsList.appendChild(li);
          });
        }
        new bootstrap.Modal(document.getElementById("notificationsModal")).show();
      });
  });

  // 3️⃣ Delegate “Mark read” clicks inside the list
  notificationsList.addEventListener("click", e => {
    if (e.target.matches(".mark-read-btn")) {
      const notifId = e.target.dataset.id;
      fetch(`/api/notifications/${notifId}/read`, {
        method: "POST",
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        },
        credentials: "include",
      })
      .then(() => {
        // refresh list and badge
        inboxBtn.click();
        loadUnreadCount();
      });
    }
  });

  // 4️⃣ Mark All as Read
  markAllReadBtn.addEventListener("click", () => {
    fetch("/api/notifications/read_all", {
      method: "POST",
      headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        },
      credentials: "include",
    })
    .then(() => {
      inboxBtn.click();      // re-open (refresh) modal
      loadUnreadCount();     // update badge
    });
  });

  // initial badge
  loadUnreadCount();

  // optional: poll every 60s
  setInterval(loadUnreadCount, 60000);
});
