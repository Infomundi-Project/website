  document.addEventListener("DOMContentLoaded", function () {
    function timeSince(date) {
      const seconds = Math.floor((new Date() - date) / 1000);
      let interval = seconds / 31536000;

      if (interval > 1) {
        return Math.floor(interval) + "years ago";
      }
      interval = seconds / 2592000;
      if (interval > 1) {
        return Math.floor(interval) + "months ago";
      }
      interval = seconds / 86400;
      if (interval > 1) {
        return Math.floor(interval) + "days ago";
      }
      interval = seconds / 3600;
      if (interval > 1) {
        return Math.floor(interval) + "hours ago";
      }
      interval = seconds / 60;
      if (interval > 1) {
        return Math.floor(interval) + "minutes ago";
      }
      return Math.floor(seconds) + "seconds ago";
    }

    function updateLastSeenElements() {
      document.querySelectorAll('[data-last-seen]').forEach(function (
        element) {
        const lastSeenDate = new Date(element.getAttribute(
          'data-last-seen'));
        element.innerText = timeSince(lastSeenDate);
      });
    }
    async function fetchUserStatus(userId) {
      const response = await fetch(
        `/api/user/${userId}/status`);
      const data = await response.json();
      const statusElement = document.getElementById('user-status');
      const profileAvatar = document.getElementById('profile-avatar');

      if (data.error) {
        statusElement.innerText = 'User not found';
      } else {
        const lastActivity = new Date(data.last_activity);
        const now = new Date();
        const timeDifference = Math.floor((now - lastActivity) / 1000);

        let lastSeenText = '';
        if (timeDifference < 60) {
          lastSeenText = `${timeDifference} seconds ago`;
        } else if (timeDifference < 3600) {
          lastSeenText = `${Math.floor(timeDifference / 60)} minutes ago`;
        } else if (timeDifference < 86400) {
          lastSeenText = `${Math.floor(timeDifference / 3600)} hours ago`;
        } else {
          lastSeenText = `${Math.floor(timeDifference / 86400)} days ago`;
        }

        if (data.is_online) {
          statusElement.innerHTML = '<h4>Currently Online</h4>';
          statusElement.className = 'text-primary-emphasis';
          profileAvatar.classList.remove('border-secondary');
          profileAvatar.classList.add('border-primary');
        } else {
          statusElement.innerHTML =
            `<h4>Currently Offline</h4><p>Last seen ${lastSeenText}</p>`;
          statusElement.className = 'text-muted';
          profileAvatar.classList.remove('border-primary');
          profileAvatar.classList.add('border-secondary');
        }
      }
    }

    function startPolling(userId) {
      fetchUserStatus(userId);

      setInterval(async () => {
        await fetchUserStatus(userId);
      }, 60000);
    }

    startPolling(profileUserPublicId);

    updateLastSeenElements();
  });