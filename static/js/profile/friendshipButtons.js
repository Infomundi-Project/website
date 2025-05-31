document.addEventListener("DOMContentLoaded", () => {
  const container = document.getElementById("friendActionContainer");
  const profileId = profileUserId;
  const profileName = profileUserName;
  const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

  // The one modal elements
  const modalEl = document.getElementById("confirmFriendModal");
  const modalTitleEl = document.getElementById("confirmFriendModalLabel");
  const modalBodyEl = document.getElementById("confirmFriendModalBody");
  const modalBtnEl = document.getElementById("confirmFriendModalBtn");
  const bsModal = new bootstrap.Modal(modalEl);

  // Map actions to modal content
  const actionConfigs = {
    add: {
      title: `<i class="fa-solid fa-user-plus me-2"></i> Send Friend Request`,
      body: `Are you sure you want to send a friend request to <strong>${profileName}</strong>? They’ll have to accept before you become friends.`,
      btnClass: "btn-primary",
      btnHtml: `<i class="fa-solid fa-paper-plane me-1"></i> Send Request`
    },
    delete_pending: {
      title: `<i class="fa-solid fa-ban me-2"></i> Cancel Friend Request`,
      body: `Sure you want to cancel your pending request to <strong>${profileName}</strong>?`,
      btnClass: "btn-warning",
      btnHtml: `<i class="fa-solid fa-ban me-1"></i> Cancel Request`
    },
    delete_accepted: {
      title: `<i class="fa-solid fa-user-slash me-2"></i> Unfriend`,
      body: `This will remove <strong>${profileName}</strong> from your friends. Are you sure?`,
      btnClass: "btn-outline-danger",
      btnHtml: `<i class="fa-solid fa-user-slash me-1"></i> Unfriend`
    }
  };

  // Show the modal configured for a given action key
  function showConfirmModal(key, action) {
    const cfg = actionConfigs[key];
    modalTitleEl.innerHTML = cfg.title;
    modalBodyEl.innerHTML = cfg.body;
    modalBtnEl.className = `btn ${cfg.btnClass}`;
    modalBtnEl.innerHTML = cfg.btnHtml;
    modalBtnEl.dataset.action = action;
    bsModal.show();
  }

  // Helper to POST friend actions
  async function doFriendAction(action) {
    const btns = container.querySelectorAll("button");
    btns.forEach(b => b.disabled = true);

    try {
      const res = await fetch("/api/user/friend", {
        method: "POST",
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        },
        credentials: "same-origin",
        body: JSON.stringify({
          friend_id: profileId,
          action
        })
      });

      if (!res.ok) {
        // Attempt to parse a JSON error message
        let errMsg = res.statusText;
        try {
          const errJson = await res.json();
          if (errJson.error) {
            errMsg = errJson.message;
          }
        } catch (parseErr) {
          // If parsing fails, just leave errMsg as res.statusText
        }
        throw new Error(errMsg);
      }

      // Re-initialize UI on success
      await initFriendUI();
    } catch (err) {
      console.error("Friend-action failed:", err);
      alert("Whoops: " + err.message);
      // re-enable buttons so they can retry
      container.querySelectorAll("button").forEach(b => b.disabled = false);
    }
  }

  modalBtnEl.addEventListener("click", () => {
    const action = modalBtnEl.dataset.action;
    doFriendAction(action);
  });

  // Builds & inserts the right buttons
  async function initFriendUI() {
    if (!container) { 
      return
    }
    
    container.innerHTML = `<span class="spinner-border spinner-border-sm"></span> Loading...`;
    try {
      const res = await fetch(`/api/user/${profileId}/friend/status`, {
        credentials: "same-origin",
        headers: {
          'X-CSRFToken': csrfToken
        }
      });
      const {
        status,
        is_sent_by_current_user
      } = await res.json();
      let html = "";

      if (status === "not_friends") {
        html = `<button id="addBtn" class="btn btn-primary btn-sm">
                  Add Friend <i class="ms-1 fa-solid fa-plus"></i>
                </button>`;
      } else if (status === "pending") {
        if (is_sent_by_current_user) {
          html = `<button id="cancelBtn" class="btn btn-warning btn-sm">
                    Cancel Request <i class="ms-1 fa-solid fa-ban"></i>
                  </button>`;
        } else {
          html = `
            <button id="acceptBtn" class="btn btn-success btn-sm">
              Accept <i class="ms-1 fa-solid fa-check"></i>
            </button>
            <button id="rejectBtn" class="btn btn-danger btn-sm">
              Reject <i class="ms-1 fa-solid fa-xmark"></i>
            </button>
          `;
        }
      } else if (status === "accepted") {
        html = `<button id="deleteBtn" class="btn btn-outline-danger btn-sm">
                  Unfriend <i class="ms-1 fa-solid fa-user-slash"></i>
                </button>`;
      } else {
        html = `<em>—</em>`;
      }

      container.innerHTML = html;

      // Hook every button into our dynamic modal
      let btn;
      if (btn = document.getElementById("addBtn")) {
        btn.addEventListener("click", () => showConfirmModal("add", "add"));
      }
      if (btn = document.getElementById("cancelBtn")) {
        btn.addEventListener("click", () => showConfirmModal("delete_pending", "delete"));
      }
      if (btn = document.getElementById("deleteBtn")) {
        btn.addEventListener("click", () => showConfirmModal("delete_accepted", "delete"));
      }
      if (btn = document.getElementById("acceptBtn")) {
        btn.addEventListener("click", () => doFriendAction("accept"));
      }
      if (btn = document.getElementById("rejectBtn")) {
        btn.addEventListener("click", () => doFriendAction("reject"));
      }

    } catch (err) {
      console.error("Could not load friendship status:", err);
      container.innerHTML = `<button disabled class="btn btn-outline-secondary btn-sm">Error</button>`;
    }
  }


  // Kick it off
  initFriendUI();
});