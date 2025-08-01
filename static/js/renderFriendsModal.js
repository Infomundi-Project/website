document.addEventListener('DOMContentLoaded', () => {
  // Check if the totalFriends element exists before making the API call
  const totalFriendsElement = document.getElementById('totalFriends');
  if (totalFriendsElement) {
    // Fetch friend counts on load
    fetch('/api/user/friends?page=1&per_page=1')
      .then(response => response.json())
      .then(data => {
        // Adjust message based on friend count
        totalFriendsElement.innerHTML = `${data.total_friends}<i class="fa-solid fa-user-group ms-2 fa-sm"></i>`;

        const onlineFriendsElement = document.getElementById('onlineFriends');
        if (onlineFriendsElement) {
          onlineFriendsElement.innerHTML = `
            <span class="dot" style="height: 8px; width: 8px; background-color: ${data.online_friends > 0 ? '#00FF00' : 'gray'}; display: inline-block; border-radius: 5px; margin-right: 4px;"></span>
            ${data.online_friends}&nbsp;online
          `;
        }
      })
      .catch(error => console.error('Error fetching friend counts:', error));
  }

  const friendsListContainer = document.getElementById('friendsListContainer');
  const paginationControlsContainer = document.getElementById('paginationControls');
  const paginationControls = paginationControlsContainer ? paginationControlsContainer.querySelector('.pagination') : null;
  let currentPage = 1;
  const perPage = 10;

  function friendsTimeAgo(date) {
    const seconds = Math.floor((new Date() - date) / 1000);

    if (seconds < 60) {
      return `${seconds} &nbsp;seconds&nbsp; ago`;
    }

    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) {
      return `${minutes} &nbsp;minute${minutes !== 1 ? 's' : ''}&nbsp; ago`;
    }

    const hours = Math.floor(minutes / 60);
    if (hours < 24) {
      return `${hours} &nbsp;hour${hours !== 1 ? 's' : ''}&nbsp; ago`;
    }

    const days = Math.floor(hours / 24);
    if (days < 7) {
      return `${days} &nbsp;day${days !== 1 ? 's' : ''}&nbsp; ago`;
    }

    const weeks = Math.floor(days / 7);
    if (weeks < 4) {
      return `${weeks} &nbsp;week${weeks !== 1 ? 's' : ''}&nbsp; ago`;
    }

    const months = Math.floor(days / 30);
    if (months < 12) {
      return `${months} &nbsp;month${months !== 1 ? 's' : ''}&nbsp; ago`;
    }

    const years = Math.floor(days / 365);
    return `${years}&nbsp;year${years !== 1 ? 's' : ''}&nbsp;ago`;
  }

  function fetchFriends(page) {
    fetch(`/api/user/friends?page=${page}&per_page=${perPage}`)
      .then(response => response.json())
      .then(data => {
        displayFriends(data.friends);
        updatePaginationControls(data.page, data.total_pages);
      })
      .catch(error => console.error('Error fetching friends:', error));
  }

  function displayFriends(friends) {
    if (!friendsListContainer) return;

    friendsListContainer.innerHTML = '';
    let row;

    friends.forEach((friend, index) => {
      if (index % 2 === 0) {
        row = document.createElement('div');
        row.className = 'row mb-2';
        friendsListContainer.appendChild(row);
      }

      const col = document.createElement('div');
      col.className = 'col-6 mb-2';

      // Determine online status text
      let statusDisplay;
      if (friend.is_online) {
        statusDisplay = `<span class="dot" style="background-color: #00FF00;"></span>&nbsp;Online`;
      } else {
        const lastActivity = new Date(friend.last_activity);
        statusDisplay = `Last activity: ${friendsTimeAgo(lastActivity)}`;
      }

      // Build friend entry with a Message button
      col.innerHTML = `
        <div class="friend-item">
          <img src="${friend.avatar_url}" alt="${friend.display_name || friend.username}'s avatar" 
               class="img-thumbnail rounded me-3" style="height: auto; width: 3rem">
          <div class="flex-grow-1">
            <h6>${friend.display_name || friend.username}
              <span class="ms-2 text-muted small">@${friend.username}</span>
            </h6>
            <small>${statusDisplay}</small>
          </div>
          <button class="btn btn-sm btn-outline-primary ms-2 message-btn" 
                  data-user-id="${friend.user_id}"
      data-username="${friend.username}">
            <i class="fa-solid fa-message"></i> Message
          </button>
        </div>
      `;
      row.appendChild(col);
    });
  }

  function updatePaginationControls(currentPage, totalPages) {
    if (!paginationControlsContainer) return;

    if (totalPages <= 1) {
      paginationControlsContainer.style.display = 'none';
      return;
    } else {
      paginationControlsContainer.style.display = 'block';
    }

    if (paginationControls) {
      paginationControls.innerHTML = '';

      // Previous page button
      paginationControls.innerHTML += `
        <li class="page-item ${currentPage === 1 ? 'disabled' : ''}">
          <button class="page-link" ${currentPage !== 1 ? `onclick="fetchFriends(${currentPage - 1})"` : ''}>Previous</button>
        </li>
      `;

      // Page number buttons
      for (let i = 1; i <= totalPages; i++) {
        paginationControls.innerHTML += `
          <li class="page-item ${i === currentPage ? 'active' : ''}">
            <button class="page-link" onclick="fetchFriends(${i})">${i}</button>
          </li>
        `;
      }

      // Next page button
      paginationControls.innerHTML += `
        <li class="page-item ${currentPage === totalPages ? 'disabled' : ''}">
          <button class="page-link" ${currentPage !== totalPages ? `onclick="fetchFriends(${currentPage + 1})"` : ''}>Next</button>
        </li>
      `;
    }
  }

  const friendsModal = document.getElementById('friendsModal');
  if (friendsModal) {
    friendsModal.addEventListener('show.bs.modal', () => {
      fetchFriends(currentPage);
    });
  }

  friendsListContainer.addEventListener('click', (e) => {
  const btn = e.target.closest('.message-btn');
  if (!btn) return;
  openChat(btn.dataset.userId, btn.dataset.username);
});

});
