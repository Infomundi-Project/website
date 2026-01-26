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

        // Update badge counts in modal
        const allFriendsCount = document.getElementById('allFriendsCount');
        const onlineFriendsCountBadge = document.getElementById('onlineFriendsCount');
        if (allFriendsCount) allFriendsCount.textContent = data.total_friends;
        if (onlineFriendsCountBadge) onlineFriendsCountBadge.textContent = data.online_friends;
      })
      .catch(error => console.error('Error fetching friend counts:', error));
  }

  const friendsListContainer = document.getElementById('friendsListContainer');
  const paginationControlsContainer = document.getElementById('paginationControls');
  const paginationControls = paginationControlsContainer ? paginationControlsContainer.querySelector('.pagination') : null;
  const loadingState = document.getElementById('friendsLoadingState');
  const emptyState = document.getElementById('friendsEmptyState');
  const searchInput = document.getElementById('friendSearchInput');
  let currentPage = 1;
  const perPage = 10;
  let allFriendsData = [];
  let currentFilter = 'all';
  let searchTerm = '';

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

  function showLoading() {
    if (loadingState) loadingState.classList.remove('d-none');
    if (emptyState) emptyState.classList.add('d-none');
    if (friendsListContainer) friendsListContainer.classList.add('d-none');
    if (paginationControlsContainer) paginationControlsContainer.classList.add('d-none');
  }

  function hideLoading() {
    if (loadingState) loadingState.classList.add('d-none');
  }

  function showEmptyState() {
    if (emptyState) emptyState.classList.remove('d-none');
    if (friendsListContainer) friendsListContainer.classList.add('d-none');
    if (paginationControlsContainer) paginationControlsContainer.classList.add('d-none');
  }

  function showFriendsList() {
    if (friendsListContainer) friendsListContainer.classList.remove('d-none');
    if (emptyState) emptyState.classList.add('d-none');
  }

  function fetchFriends(page) {
    showLoading();
    fetch(`/api/user/friends?page=${page}&per_page=${perPage}`)
      .then(response => response.json())
      .then(data => {
        allFriendsData = data.friends;
        hideLoading();
        filterAndDisplayFriends();
        updatePaginationControls(data.page, data.total_pages);
      })
      .catch(error => {
        console.error('Error fetching friends:', error);
        hideLoading();
        showEmptyState();
      });
  }

  function filterAndDisplayFriends() {
    let filteredFriends = allFriendsData;

    // Apply online filter
    if (currentFilter === 'online') {
      filteredFriends = filteredFriends.filter(friend => friend.is_online);
    }

    // Apply search filter
    if (searchTerm) {
      filteredFriends = filteredFriends.filter(friend => {
        const displayName = (friend.display_name || friend.username).toLowerCase();
        const username = friend.username.toLowerCase();
        const term = searchTerm.toLowerCase();
        return displayName.includes(term) || username.includes(term);
      });
    }

    if (filteredFriends.length === 0) {
      showEmptyState();
    } else {
      showFriendsList();
      displayFriends(filteredFriends);
    }
  }

  function displayFriends(friends) {
    if (!friendsListContainer) return;

    friendsListContainer.innerHTML = '';

    friends.forEach((friend, index) => {
      // Determine online status
      let statusDisplay;
      let statusClass = '';
      if (friend.is_online) {
        statusDisplay = `<span class="online-indicator pulse"></span><span class="ms-1">Online</span>`;
        statusClass = 'online';
      } else {
        const lastActivity = new Date(friend.last_activity);
        statusDisplay = `<i class="fa-solid fa-clock me-1"></i>${friendsTimeAgo(lastActivity)}`;
        statusClass = 'offline';
      }

      // Build friend card with enhanced styling
      const friendCard = document.createElement('div');
      friendCard.className = 'friend-card';
      const profileUrl = `/profile/${friend.username}`;
      friendCard.innerHTML = `
        <div class="friend-card-inner ${statusClass}">
          <a href="${profileUrl}" class="friend-avatar-wrapper" title="View ${friend.display_name || friend.username}'s profile">
            <img src="${friend.avatar_url}" alt="${friend.display_name || friend.username}'s avatar"
                 class="friend-avatar">
            ${friend.is_online ? '<span class="avatar-status-badge"></span>' : ''}
          </a>
          <div class="friend-info">
            <a href="${profileUrl}" class="friend-name-link">
              <div class="friend-name">${friend.display_name || friend.username}</div>
            </a>
            <div class="friend-username text-muted">@${friend.username}</div>
            <div class="friend-status ${friend.is_online ? 'text-success' : 'text-muted'}">${statusDisplay}</div>
          </div>
          <div class="friend-actions">
            <button class="btn btn-sm btn-primary message-btn"
                    data-user-id="${friend.user_id}"
                    data-username="${friend.username}"
                    title="Send message">
              <i class="fa-solid fa-message"></i>
            </button>
          </div>
        </div>
      `;
      friendsListContainer.appendChild(friendCard);
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

  // Search functionality with debounce
  let searchTimeout;
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => {
        searchTerm = e.target.value;
        filterAndDisplayFriends();
      }, 300);
    });
  }

  // Filter tabs functionality
  const filterTabs = document.querySelectorAll('#friendsFilterTabs button');
  filterTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      currentFilter = tab.getAttribute('data-filter');
      filterAndDisplayFriends();
    });
  });

  // Message button click handler
  if (friendsListContainer) {
    friendsListContainer.addEventListener('click', (e) => {
      const btn = e.target.closest('.message-btn');
      if (!btn) return;
      openChat(btn.dataset.userId, btn.dataset.username);
    });
  }

});
