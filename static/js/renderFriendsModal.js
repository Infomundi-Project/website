document.addEventListener('DOMContentLoaded', () => {
  const friendsListContainer = document.getElementById('friendsListContainer');
  const paginationControls = document.getElementById('paginationControls').querySelector('.pagination');
  let currentPage = 1;
  const perPage = 10;

  function friendsTimeAgo(date) {
  const seconds = Math.floor((new Date() - date) / 1000);

  if (seconds < 60) {
    return `${seconds} seconds ago`;
  }
  
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) {
    return `${minutes} minute${minutes !== 1 ? 's' : ''} ago`;
  }
  
  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    return `${hours} hour${hours !== 1 ? 's' : ''} ago`;
  }
  
  const days = Math.floor(hours / 24);
  if (days < 7) {
    return `${days} day${days !== 1 ? 's' : ''} ago`;
  }
  
  const weeks = Math.floor(days / 7);
  if (weeks < 4) {
    return `${weeks} week${weeks !== 1 ? 's' : ''} ago`;
  }
  
  const months = Math.floor(days / 30);
  if (months < 12) {
    return `${months} month${months !== 1 ? 's' : ''} ago`;
  }
  
  const years = Math.floor(days / 365);
  return `${years} year${years !== 1 ? 's' : ''} ago`;
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
  friendsListContainer.innerHTML = '';
  let row;

  friends.forEach((friend, index) => {
    if (index % 2 === 0) {
      row = document.createElement('div');
      row.className = 'row mb-2';
      friendsListContainer.appendChild(row);
    }

    const col = document.createElement('div');
    col.className = 'col-6 d-flex align-items-center mb-2';

    // Determine if the friend is online or display last activity as relative time
    let statusDisplay;
    if (friend.is_online) {
      // Show online status with a green dot
      statusDisplay = `
        <span class="dot" style="height: 8px; width: 8px; background-color: green; display: inline-block; border-radius: 50%; margin-right: 4px;"></span>
        Online
      `;
    } else {
      // Parse last_activity in GMT and calculate relative time
      const lastActivityGMT = new Date(friend.last_activity);
      const lastActivityRelative = friendsTimeAgo(lastActivityGMT);
      statusDisplay = `Last activity: ${lastActivityRelative}`;
    }

    col.innerHTML = `
      <div class="friend-item d-flex align-items-center">
        <img src="${friend.avatar_url}" alt="${friend.display_name}'s avatar" class="rounded-circle me-3" width="50" height="50">
        <div>
          <h6>${friend.display_name} (${friend.username})</h6>
          <p class="mb-0">Level: ${friend.level}</p>
          <small>${statusDisplay}</small>
        </div>
      </div>
    `;

    row.appendChild(col);
  });
}


  function updatePaginationControls(currentPage, totalPages) {
  const paginationContainer = document.getElementById('paginationControls');

  // Hide pagination if there's only one page
  if (totalPages <= 1) {
    paginationContainer.style.display = 'none';
    return;
  } else {
    paginationContainer.style.display = 'block';
  }

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

  document.getElementById('friendsModal').addEventListener('show.bs.modal', () => {
    fetchFriends(currentPage);
  });
});