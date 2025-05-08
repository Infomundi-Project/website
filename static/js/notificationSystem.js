document.addEventListener("DOMContentLoaded", () => {
  const inboxBtn          = document.getElementById("inboxBtn");
  const unreadBadge       = document.getElementById("unreadBadge");
  const notificationsList = document.getElementById("notificationsList");
  const markAllReadBtn    = document.getElementById("markAllReadBtn");
  const csrfToken         = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
  const modalEl           = document.getElementById("notificationsModal");
  const bsModal           = new bootstrap.Modal(modalEl);

  // —————————————————————— Helpers ——————————————————————

  // Format as “5m ago”, “2h ago”, or “May 5”
  function relativeTime(iso) {
    const now  = Date.now();
    const diff = (now - new Date(iso + 'Z')) / 1000; // in seconds
    if (diff < 60)    return `${Math.floor(diff)}s ago`;
    if (diff < 3600)  return `${Math.floor(diff/60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff/3600)}h ago`;
    // beyond a day: show month/day
    return new Intl.DateTimeFormat("default", { month: "short", day: "numeric" }).format(new Date(iso));
  }

  // Load unread count
  function loadUnreadCount() {
    fetch("/api/notifications/unread_count", {
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken
      }
    })
    .then(res => res.json())
    .then(data => {
      unreadBadge.textContent = data.unread_count;
      markAllReadBtn.style.display = data.unread_count > 0 ? "inline-block" : "none";
      unreadBadge.style.display = data.unread_count > 0 ? "inline-block" : "none";
    });
  }

  // —————————————————————— Core: fetch & render ——————————————————————

  function loadNotifications() {
    fetch("/api/notifications?per_page=50", {
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken
      }
    })
    .then(res => res.json())
    .then(data => {
      notificationsList.innerHTML = "";
      if (!data.notifications.length) {
        notificationsList.innerHTML = `
          <li class="list-group-item text-center text-muted">
            📭 All quiet here.
          </li>`;
        return;
      }

      let lastDate = null;
      data.notifications.forEach(n => {
        const thisDate = new Date(n.created_at).toDateString();
        // if new calendar day, inject a separator
        if (thisDate !== lastDate) {
          const divider = document.createElement("li");
          divider.className = "list-group-item disabled text-center small";
          divider.textContent = new Intl.DateTimeFormat("default", {
            weekday: "long",
            month: "short",
            day: "numeric"
          }).format(new Date(n.created_at));
          notificationsList.appendChild(divider);
          lastDate = thisDate;
        }

        const li = document.createElement("li");
        li.className = `list-group-item d-flex justify-content-between align-items-start ${
          n.is_read ? "" : "fw-bold"
        }`;

        // choose an icon per type
        let iconClass = n.type === "comment_reply" || n.type === "new_comment"   ? "fa-comment"
                         : n.type === "friend_request"  ? "fa-user-plus"
                         : n.type === "friend_accepted" ? "fa-user-check"
                         : "fa-bell";
        iconClass += n.is_read ? " text-muted" : " text-primary";

        li.innerHTML = `
          <div class="d-flex align-items-center">
            <i class="fa ${iconClass} me-3"></i>
            <div>
              <span>
                <div>${n.message}</div>
                <small class="text-muted">${relativeTime(n.created_at)} - <a href="${n.url||'#'}">View</a></small>
              </span>
            </div>
          </div>
          ${
            n.is_read
              ? ""
              : `<button data-id="${n.id}" class="btn btn-sm btn-outline-primary mark-read-btn"><i class="fa-solid fa-check-double"></i></button>`
          }
        `;
        notificationsList.appendChild(li);
      });
    })
    .catch(console.error);
  }

  // —————————————————————— Event Wiring ——————————————————————

  // Open inbox → refresh list + show modal
  inboxBtn.addEventListener("click", () => {
    loadNotifications();
    bsModal.show();
  });

  // Delegate single-mark-read buttons
  notificationsList.addEventListener("click", e => {
    if (!e.target.matches(".mark-read-btn")) return;
    const notifId = e.target.dataset.id;
    fetch(`/api/notifications/${notifId}/read`, {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken
      }
    })
    .then(() => {
      loadNotifications();  // just refresh contents
      loadUnreadCount();
    })
    .catch(console.error);
  });

  // Bulk “Mark All as Read”
  markAllReadBtn.addEventListener("click", () => {
    fetch("/api/notifications/read_all", {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken
      }
    })
    .then(() => {
      loadNotifications();  // refresh inside the same modal
      loadUnreadCount();
    })
    .catch(console.error);
  });

  // Initial badge load and optional polling
  loadUnreadCount();
  setInterval(loadUnreadCount, 60000);
});
