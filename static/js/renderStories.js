document.addEventListener("DOMContentLoaded", function() {
  let infomundiStoryModal = new bootstrap.Modal(document.getElementById("infomundiStoryModal"), {
    keyboard: false,
  });

  // Modal element selectors
  const modalElement = document.getElementById("infomundiStoryModal");
  const modalTitle = modalElement.querySelector(".modal-header h1");
  const modalImage = modalElement.querySelector(".modal-header img");
  const modalDescription = modalElement.querySelector(".modal-body p");
  const modalPublishedBy = modalElement.querySelector(".modal-body .col-md-4 div:nth-child(1) span:last-child");
  const modalTagsContainer = modalElement.querySelector(".modal-body .d-flex.align-items-center");
  const modalLikeIcon = modalElement.querySelector(".fa-thumbs-up");
  const modalDislikeIcon = modalElement.querySelector(".fa-thumbs-down");
  const modalLikeCount = modalLikeIcon.querySelector("span");
  const modalDislikeCount = modalDislikeIcon.querySelector("span");
  const modalSatelliteIcon = modalElement.querySelector(".fa-satellite-dish");
  const modalPublishedDate = modalElement.querySelector("#publishedDateStoryModal");
  const modalViewCount = modalElement.querySelector("#viewCountStoryModal");

  // Function to initialize like/dislike icons based on localStorage
  function initializeLikeDislikeIcons(storyId, likeIcon, dislikeIcon) {
      const savedInteractions = JSON.parse(localStorage.getItem('storyInteractions')) || {};
      const userAction = savedInteractions[storyId]?.action;

      const isLiked = userAction === 'like';
      const isDisliked = userAction === 'dislike';

      likeIcon.classList.toggle('fa-solid', isLiked);
      likeIcon.classList.toggle('fa-regular', !isLiked);
      dislikeIcon.classList.toggle('fa-solid', isDisliked);
      dislikeIcon.classList.toggle('fa-regular', !isDisliked);
  }

  // Define event listeners for modal icons
  modalLikeIcon.addEventListener('click', function() {
    const storyId = this.dataset.storyId;
    handleLikeDislike('like', storyId, modalLikeIcon, modalDislikeIcon, modalLikeCount, modalDislikeCount);
  });

  modalDislikeIcon.addEventListener('click', function() {
    const storyId = this.dataset.storyId;
    handleLikeDislike('dislike', storyId, modalLikeIcon, modalDislikeIcon, modalLikeCount, modalDislikeCount);
  });

  // Satellite share button functionality
  modalSatelliteIcon.addEventListener('click', function() {
    const storyId = this.dataset.storyId;
    const storyTitle = this.dataset.storyTitle;
    const storyDescription = this.dataset.storyDescription || '';
    if (navigator.share) {
      navigator.share({
        title: storyTitle,
        text: storyDescription,
        url: window.location.origin + `/comments?id=${storyId}`
      }).then(() => {
        console.log('Thanks for sharing!');
      }).catch(console.error);
    } else {
      alert('Sharing is not supported on this browser.');
    }
  });

  modalElement.addEventListener("hidden.bs.modal", function () {
    modalTitle.textContent = "";
    modalImage.src = "";
    modalDescription.textContent = "";
    modalPublishedBy.textContent = "";
    modalTagsContainer.innerHTML = ""; // Clear the tags container
    modalLikeCount.innerHTML = "&nbsp;0";
    modalDislikeCount.innerHTML = "&nbsp;0";
    modalPublishedDate.innerHTML = "";
    modalViewCount.innerHTML = "";
    modalLikeIcon.dataset.storyId = "";
    modalDislikeIcon.dataset.storyId = "";
    modalSatelliteIcon.dataset.storyId = "";
    modalSatelliteIcon.dataset.storyTitle = "";
    modalSatelliteIcon.dataset.storyDescription = "";
  });

  // Attach event listener to dynamically created story cards
  function attachModalEvents() {
    const storyCards = document.querySelectorAll(".card.image-card");

    storyCards.forEach((card) => {
      card.addEventListener("click", function(event) {
        const clickedElement = event.target; // Get the clicked element

        // Check if the click is on the image or card body (title + description)
        if (
          clickedElement.classList.contains("card-img-top") || // Image
          clickedElement.closest(".card-body") // Card body (title + description)
        ) {
          event.preventDefault(); // Prevent navigation

          // Extract story data from the clicked card
          const storyData = JSON.parse(this.dataset.storyData);

          // Update modal content
          modalTitle.textContent = storyData.title;
          modalImage.src = storyData.media_content_url;
          modalDescription.textContent = storyData.description || "";

          // Update tags as links
          modalTagsContainer.innerHTML = ""; // Clear previous tags
          if (storyData.tags && Array.isArray(storyData.tags)) {
            storyData.tags.forEach((tag) => {
              const tagLink = document.createElement("a");
              tagLink.href = `${window.location.origin}?search=${encodeURIComponent(tag)}`;
              tagLink.className = "badge text-bg-primary mx-1";
              tagLink.textContent = tag;
              modalTagsContainer.appendChild(tagLink);
            });
          }

          // Update data attributes for the icons
          modalLikeIcon.dataset.storyId = storyData.story_id;
          modalLikeIcon.dataset.liked = storyData.is_liked ? "true" : "false";
          modalDislikeIcon.dataset.storyId = storyData.story_id;
          modalDislikeIcon.dataset.disliked = storyData.is_disliked ? "true" : "false";

          // Update like/dislike counts
          modalLikeCount.innerHTML = `&nbsp;${storyData.likes || 0}`;
          modalDislikeCount.innerHTML = `&nbsp;${storyData.dislikes || 0}`;

          // Update icons based on is_liked/is_disliked
          modalLikeIcon.classList.toggle("fa-solid", storyData.is_liked);
          modalLikeIcon.classList.toggle("fa-regular", !storyData.is_liked);
          modalDislikeIcon.classList.toggle("fa-solid", storyData.is_disliked);
          modalDislikeIcon.classList.toggle("fa-regular", !storyData.is_disliked);

          // Update satellite icon data attributes
          modalSatelliteIcon.dataset.storyId = storyData.story_id;
          modalSatelliteIcon.dataset.storyTitle = storyData.title;
          modalSatelliteIcon.dataset.storyDescription = storyData.description || "";

          // Update published date and view count
          modalPublishedDate.innerHTML = `<i class="fa-regular fa-calendar"></i>&nbsp;${storyData.pub_date}&nbsp;(${timeAgo(storyData.pub_date)})`;
          modalViewCount.innerHTML = `<i class="fa-regular fa-eye"></i>&nbsp;${storyData.clicks}&nbsp;views`;

          initializeLikeDislikeIcons(storyData.story_id, modalLikeIcon, modalDislikeIcon);
          // Show the modal
          infomundiStoryModal.show();
        }
      });
    });
  }

  let middleSectionCount = 1;

  function addMiddleSection() {
    // Left Pillar
    const leftPillar = document.querySelector('.pillar-container-left');
    if (leftPillar) {
        const leftPillarMiddle = document.createElement('img');
        leftPillarMiddle.src = 'https://infomundi.net/static/img/illustrations/pillar-middle2.webp';
        leftPillarMiddle.alt = 'Middle of the Pillar';
        leftPillarMiddle.classList.add('pillar-middle', 'adjusted-up');

        // Apply flipped class to every other section in the left pillar for alternating effect
        if (middleSectionCount % 2 !== 0) {
            leftPillarMiddle.classList.add('mirrored');
        }

        const leftPillarBottom = leftPillar.querySelector('.pillar-bottom');
        if (leftPillarBottom) {
            leftPillar.insertBefore(leftPillarMiddle, leftPillarBottom);
        } else {
            leftPillar.appendChild(leftPillarMiddle); // Fallback if .pillar-bottom doesn't exist
        }
    }

    // Right Pillar (Mirrored)
    const rightPillar = document.querySelector('.pillar-container-right');
    if (rightPillar) {
        const rightPillarMiddle = document.createElement('img');
        rightPillarMiddle.src = 'https://infomundi.net/static/img/illustrations/pillar-middle2.webp';
        rightPillarMiddle.alt = 'Middle of the Pillar';
        rightPillarMiddle.classList.add('pillar-middle', 'horizontally-mirrored'); // Add mirrored class

        // Apply flipped class to every other section in the right pillar for alternating effect
        if (middleSectionCount % 2 !== 0) {
            rightPillarMiddle.classList.add('mirrored');
        }

        const rightPillarBottom = rightPillar.querySelector('.pillar-bottom');
        if (rightPillarBottom) {
            rightPillar.insertBefore(rightPillarMiddle, rightPillarBottom);
        } else {
            rightPillar.appendChild(rightPillarMiddle); // Fallback if .pillar-bottom doesn't exist
        }
    }

    middleSectionCount++; // Increment counter after adding to both pillars
  }


  function initializePillar(initialCount = 70) {
    for (let i = 0; i < initialCount; i++) {
      addMiddleSection();
    }
  }

  initializePillar();

  // Event listener for the Clear Filters button
  document.getElementById('clearFiltersButton').addEventListener('click', function() {
    // Reset form fields to their default values
    document.getElementById('query').value = '';
    document.getElementById('modalStartDate').value = '';
    document.getElementById('modalEndDate').value = '';
    
    // Reset radio buttons to default
    document.querySelector(`input[name="category"][value="general"]`).checked = true;
    document.querySelector(`input[name="order_by"][value="pub_date"]`).checked = true;
    document.querySelector(`input[name="order_dir"][value="desc"]`).checked = true;
    
    // Reset button texts
    document.getElementById('categoryButtonText').textContent = 'General';
    document.getElementById('orderByButtonText').textContent = 'Publication Date';
    document.getElementById('orderDirButtonText').textContent = 'Descending';
    document.getElementById('periodButtonText').textContent = 'Start Date - End Date';

    // Clear filters from localStorage
    localStorage.removeItem('newsFilters');

    // Reset filters in the application by applying the default state
    applyFilters();
  });

  const filterForm = document.getElementById("filterForm");
  const storiesContainer = document.getElementById("storiesContainer");
  const endPageSpinner = document.getElementById("endPageSpinner");

  const urlParams = new URLSearchParams(window.location.search);
  const country = urlParams.get('country');
  
  if (country) {
    document.getElementById('country').value = country;
  }

  let currentPage = 1;
  let isLoading = false;
  let hasMoreStories = true;

  // Load saved filters from localStorage
  loadSavedFilters();

  // Function to apply filters
  function applyFilters() {
    saveFiltersToLocalStorage();
    showLoading();
    currentPage = 1;
    hasMoreStories = true;
    fetchStories(true);
    linkSafety();
  }

  // Prevent form submission
  filterForm.addEventListener('submit', function(event) {
    event.preventDefault();
  });

  // Event listeners for filter inputs
  // Category Radio Buttons
  document.querySelectorAll('input[name="category"]').forEach(function(el) {
    el.addEventListener('change', function() {
      applyFilters();
    });
  });

  // Order By Radio Buttons
  document.querySelectorAll('input[name="order_by"]').forEach(function(el) {
    el.addEventListener('change', function() {
      applyFilters();
    });
  });

  // Order Direction Radio Buttons
  document.querySelectorAll('input[name="order_dir"]').forEach(function(el) {
    el.addEventListener('change', function() {
      applyFilters();
    });
  });

  // Date Inputs
  document.getElementById('modalStartDate').addEventListener('change', function() {
    applyFilters();
  });

  document.getElementById('modalEndDate').addEventListener('change', function() {
    applyFilters();
  });

  // Debounce Function
  function debounce(func, wait) {
    let timeout;
    return function(...args) {
      const context = this;
      clearTimeout(timeout);
      timeout = setTimeout(function() {
        func.apply(context, args);
      }, wait);
    };
  }

  // Debounced Apply Filters for Search Input
  const debounceApplyFilters = debounce(applyFilters, 500);
  document.getElementById('query').addEventListener('input', function() {
    debounceApplyFilters();
  });

  window.addEventListener('scroll', () => {
    if ((window.innerHeight + window.scrollY) >= document.body.offsetHeight - 2000 && !isLoading && hasMoreStories) {
      fetchStories(false);
      initializePillar();
    }
  });

  function showLoading() {
    endPageSpinner.style.display = 'inline-block';
  }

  function hideLoading() {
    endPageSpinner.style.display = 'none';
  }

  function fetchStories(reset) {
    if (isLoading) return;

    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');

    if (tooltipTriggerList.length > 0) {
      [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
    }

    isLoading = true;
    const category = document.querySelector('input[name="category"]:checked').value;
    const orderBy = document.querySelector('input[name="order_by"]:checked').value;
    const orderDir = document.querySelector('input[name="order_dir"]:checked').value;
    const country = document.getElementById("country").value;
    const startDate = document.getElementById("modalStartDate").value;
    const endDate = document.getElementById("modalEndDate").value;
    const query = document.getElementById("query").value;

    let url = `/api/get_stories?country=${country}&category=${category}&order_by=${orderBy}&order_dir=${orderDir}&page=${currentPage}`;

    if (startDate && endDate) {
      url += `&start_date=${startDate}&end_date=${endDate}`;
    }

    if (query) {
      url += `&query=${query}`;
    }

    fetch(url)
      .then(response => response.json())
      .then(data => {
        if (reset) {
          storiesContainer.innerHTML = ''; // Clear the container for new filter
        }
        if (data.length > 0) {
          data.forEach((item, index) => {
            const storyCard = createStoryCard(item, index);
            storiesContainer.appendChild(storyCard);
          });
          attachModalEvents(); // Attach modal events to newly created cards
          // Initialize lazy loading after new content is loaded
          if (window.lazyload) {
            lazyload();
          }
          // Update time ago for newly added content
          updateTimeAgo();
          currentPage += 1;
        } else {
          hasMoreStories = false;
        }
        hideLoading();
        isLoading = false;
      })
      .catch(error => {
        console.error('Error fetching stories:', error);
        hideLoading();
        isLoading = false;
      });
  }

  function createStoryCard(item, index) {
    const colDiv = document.createElement('div');
    colDiv.classList.add('col-lg-6', 'col-xl-4', 'my-5');

    const cardDiv = document.createElement('div');
    cardDiv.classList.add('card', 'image-card', 'border', 'border-0');
    cardDiv.id = `${item.story_id}-${item.category_id}`;

    // Image link
    const imageLink = document.createElement('a');
    imageLink.href = `/comments?id=${item.story_id}`;

    // Image tag
    const imgTag = document.createElement('img');
    imgTag.classList.add('card-img-top', 'rounded');
    imgTag.alt = item.title;
    imgTag.style = 'width: 100%; aspect-ratio: 16 / 9; object-fit: cover;';
    if (index < 3) {
        imgTag.src = item.media_content_url;
        imgTag.setAttribute('fetchpriority', 'high');
    } else {
        imgTag.setAttribute('data-src', item.media_content_url);
        imgTag.classList.add('lazyload');
    }
    imageLink.appendChild(imgTag);

    // Tip logo overlay
    const tipLogoDiv = document.createElement('div');
    tipLogoDiv.classList.add('tip-logo');

    const tipLogoImg = document.createElement('div');
    tipLogoImg.innerHTML = `
        <a href="${item.publisher.link}" class="text-decoration-none" target="_blank" data-bs-toggle="tooltip" data-bs-title="${item.publisher.name}">
          ${item.publisher.favicon ? 
            `<img src="${item.publisher.favicon}" class="rounded" alt="${item.publisher.name} favicon image" width="30">` : 
            `<i class="fa-solid fa-rss"></i>`
          }
        </a>
    `;
    tipLogoDiv.appendChild(tipLogoImg);

    // Card body
    const cardBody = document.createElement('div');
    cardBody.classList.add('card-body');
    cardBody.innerHTML = `
        <a href="/comments?id=${item.story_id}" class="text-decoration-none text-reset">
          <p class="card-title fw-bold fs-6 line-clamp-3">
            ${item.title}
          </p>
          <small><p class="card-text text-muted line-clamp-4">
            ${item.description || ''}
          </p></small>
        </a>
    `;

    // Card footer
    const cardFooter = document.createElement('div');
    cardFooter.classList.add('card-footer', 'bg-transparent', 'border', 'border-0');

    const rowDiv = document.createElement('div');
    rowDiv.classList.add('row', 'd-flex', 'justify-content-between');

    const colLeft = document.createElement('div');
    colLeft.classList.add('col');

    const dateSpan = document.createElement('span');
    dateSpan.classList.add('text-muted', 'fw-bold', 'small');
    dateSpan.innerHTML = `<span class="date-info" id="date-info">${item.pub_date}</span><span class="mx-1">&#x2022;</span>${item.clicks} views`;

    colLeft.appendChild(dateSpan);

    const colRight = document.createElement('div');
    colRight.classList.add('col', 'd-flex', 'justify-content-end');

    // Like Icon with Count
    const likeIcon = document.createElement('i');
    likeIcon.classList.add(item.is_liked ? 'fa-solid' : 'fa-regular', 'fa-thumbs-up');
    likeIcon.style.cursor = 'pointer';
    likeIcon.dataset.storyId = item.story_id;
    likeIcon.dataset.liked = item.is_liked ? 'true' : 'false';

    const likeCount = document.createElement('span');
    likeCount.textContent = ` ${item.likes || 0}`; // Display the like count
    likeIcon.appendChild(likeCount);

    // Dislike Icon with Count
    const dislikeIcon = document.createElement('i');
    dislikeIcon.classList.add(item.is_disliked ? 'fa-solid' : 'fa-regular', 'fa-thumbs-down', 'mx-4');
    dislikeIcon.style.cursor = 'pointer';
    dislikeIcon.dataset.storyId = item.story_id;
    dislikeIcon.dataset.disliked = item.is_disliked ? 'true' : 'false';

    const dislikeCount = document.createElement('span');
    dislikeCount.textContent = ` ${item.dislikes || 0}`; // Display the dislike count
    dislikeIcon.appendChild(dislikeCount);

    // Event listeners for like and dislike icons
    likeIcon.addEventListener('click', function() {
      handleLikeDislike('like', item.story_id, likeIcon, dislikeIcon, likeCount, dislikeCount);
    });

    dislikeIcon.addEventListener('click', function() {
      handleLikeDislike('dislike', item.story_id, likeIcon, dislikeIcon, likeCount, dislikeCount);
    });

    // Bookmark Icon
    const thumbtackIcon = document.createElement('i');
    thumbtackIcon.classList.add('fa-regular', 'fa-bookmark');
    thumbtackIcon.style.cursor = 'pointer';

    // Satellite Share Icon
    const satelliteIcon = document.createElement('i');
    satelliteIcon.classList.add('fa-solid', 'fa-satellite-dish', 'ms-4', 'satellite-share-button');
    satelliteIcon.style.cursor = 'pointer';

    // Satellite share button functionality
    satelliteIcon.addEventListener('click', () => {
        if (navigator.share) {
            navigator.share({
                title: item.title,
                text: item.description || '',
                url: window.location.origin + `/comments?id=${item.story_id}`
            }).then(() => {
                console.log('Thanks for sharing!');
            }).catch(console.error);
        } else {
            // Fallback for browsers that don't support the Web Share API
            alert('Sharing is not supported on this browser.');
        }
    });

    // Append icons to the right column
    colRight.appendChild(likeIcon);
    colRight.appendChild(dislikeIcon);
    colRight.appendChild(thumbtackIcon);
    colRight.appendChild(satelliteIcon);

    // Assemble the footer
    rowDiv.appendChild(colLeft);
    rowDiv.appendChild(colRight);
    cardFooter.appendChild(rowDiv);

    // Assembling the card
    cardDiv.appendChild(imageLink);
    cardDiv.appendChild(tipLogoDiv);
    cardDiv.appendChild(cardBody);
    cardDiv.appendChild(cardFooter);

    colDiv.appendChild(cardDiv);

    cardDiv.dataset.storyData = JSON.stringify(item);

    // Initialize like/dislike states
    initializeLikeDislikeIcons(item.story_id, likeIcon, dislikeIcon);

    return colDiv;
  }


  // Function to handle like and dislike actions
  function handleLikeDislike(action, storyId, likeIcon, dislikeIcon, likeCount, dislikeCount) {
    // Fetch the saved likes/dislikes data from localStorage
    let savedInteractions = JSON.parse(localStorage.getItem('storyInteractions')) || {};

    // Determine the new state for localStorage
    let newAction = null;
    if (action === 'like') {
        if (savedInteractions[storyId]?.action === 'like') {
            // Toggle off like
            delete savedInteractions[storyId];
        } else {
            // Set to like
            savedInteractions[storyId] = { action: 'like' };
            newAction = 'like';
        }
    } else if (action === 'dislike') {
        if (savedInteractions[storyId]?.action === 'dislike') {
            // Toggle off dislike
            delete savedInteractions[storyId];
        } else {
            // Set to dislike
            savedInteractions[storyId] = { action: 'dislike' };
            newAction = 'dislike';
        }
    }

    // Save the updated interactions to localStorage
    localStorage.setItem('storyInteractions', JSON.stringify(savedInteractions));

    // Update the UI optimistically
    const isLiked = savedInteractions[storyId]?.action === 'like';
    const isDisliked = savedInteractions[storyId]?.action === 'dislike';

    likeIcon.classList.toggle('fa-solid', isLiked);
    likeIcon.classList.toggle('fa-regular', !isLiked);
    dislikeIcon.classList.toggle('fa-solid', isDisliked);
    dislikeIcon.classList.toggle('fa-regular', !isDisliked);

    // Update counts optimistically
    let likes = parseInt(likeCount.textContent.trim()) || 0;
    let dislikes = parseInt(dislikeCount.textContent.trim()) || 0;

    if (newAction === 'like') {
        likes++;
        if (isDisliked) dislikes--; // Remove previous dislike
    } else if (newAction === 'dislike') {
        dislikes++;
        if (isLiked) likes--; // Remove previous like
    }

    likeCount.textContent = ` ${Math.max(likes, 0)}`;
    dislikeCount.textContent = ` ${Math.max(dislikes, 0)}`;

    // Inform the server about the action
    const url = `/api/story/${action}`;

    fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ id: storyId })
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(errorData => {
                throw new Error(errorData.message || 'Error performing action');
            });
        }
        return response.json();
    })
    .then(data => {
        // Update counts based on server response
        likeCount.textContent = ` ${data.likes}`;
        dislikeCount.textContent = ` ${data.dislikes}`;
    })
    .catch(error => {
        // Rollback the optimistic UI update if the server request fails
        alert(error.message);

        // Revert to the previous state from localStorage
        const previousState = JSON.parse(localStorage.getItem('storyInteractions')) || {};
        const wasLiked = previousState[storyId]?.action === 'like';
        const wasDisliked = previousState[storyId]?.action === 'dislike';

        likeIcon.classList.toggle('fa-solid', wasLiked);
        likeIcon.classList.toggle('fa-regular', !wasLiked);
        dislikeIcon.classList.toggle('fa-solid', wasDisliked);
        dislikeIcon.classList.toggle('fa-regular', !wasDisliked);

        // Revert counts
        likeCount.textContent = ` ${likes}`;
        dislikeCount.textContent = ` ${dislikes}`;
    });
  }

  // Function to calculate relative time
  function timeAgo(dateString) {
    const originalDate = new Date(dateString);
    if (isNaN(originalDate.getTime())) {
      //console.error('Invalid date:', dateString);
      return dateString;
    }
    const currentDate = new Date();
    const differenceInSeconds = Math.floor((currentDate - originalDate) / 1000);
    const differenceInHours = Math.floor(differenceInSeconds / 3600);
    const differenceInDays = Math.floor(differenceInHours / 24);

    // Adjusting logic to only return "today", "yesterday", or "X days ago"
    if (differenceInDays === 0) {
        return 'Today';
    } else if (differenceInDays === 1) {
        return 'Yesterday';
    } else {
        return `${differenceInDays}&nbsp;days&nbsp;ago`;
    }
  }

  // Function to update time ago for all date-info elements
  function updateTimeAgo() {
    const dateElements = document.querySelectorAll('.date-info');
    dateElements.forEach(function(element) {
      const originalDateString = element.textContent.trim(); // Extract the date string
      const relativeDateString = timeAgo(originalDateString); // Convert to relative format
      element.innerHTML = relativeDateString; // Update the element content
    });
  }


  // Function to save filter settings to localStorage
  function saveFiltersToLocalStorage() {
    const category = document.querySelector('input[name="category"]:checked').value;
    const orderBy = document.querySelector('input[name="order_by"]:checked').value;
    const orderDir = document.querySelector('input[name="order_dir"]:checked').value;
    const startDate = document.getElementById("modalStartDate").value;
    const endDate = document.getElementById("modalEndDate").value;
    const query = document.getElementById("query").value;

    localStorage.setItem('newsFilters', JSON.stringify({ category, orderBy, orderDir, startDate, endDate, query }));
  }


  // Function to load filter settings from localStorage
  function loadSavedFilters() {
    const savedFilters = JSON.parse(localStorage.getItem('newsFilters'));
    if (savedFilters) {
      const { category, orderBy, orderDir, startDate, endDate, query } = savedFilters;
      document.querySelector(`input[name="category"][value="${category}"]`).checked = true;
      document.querySelector(`input[name="order_by"][value="${orderBy}"]`).checked = true;
      document.querySelector(`input[name="order_dir"][value="${orderDir}"]`).checked = true;
      document.getElementById("modalStartDate").value = startDate;
      document.getElementById("modalEndDate").value = endDate;
      document.getElementById("query").value = query;

      // Update periodButtonText
      let periodText = 'Start Date - End Date';
      if (startDate && endDate) {
        periodText = `${startDate} to ${endDate}`;
      }
      document.getElementById('periodButtonText').textContent = periodText;
    }
  }

  function updateButtonText(inputName, buttonTextId) {
      var selectedLabel = document.querySelector(`input[name="${inputName}"]:checked`).nextElementSibling;
      var selectedText = selectedLabel.querySelector('.label-text').textContent.trim();
      document.getElementById(buttonTextId).textContent = selectedText;
    }
  
    // Initialize Button Texts
    updateButtonText('category', 'categoryButtonText');
    updateButtonText('order_by', 'orderByButtonText');
    updateButtonText('order_dir', 'orderDirButtonText');
  
    // Event Listeners for Category
    document.querySelectorAll('input[name="category"]').forEach(function(el) {
      el.addEventListener('change', function() {
        updateButtonText('category', 'categoryButtonText');
      });
    });
  
    // Event Listeners for Order By
    document.querySelectorAll('input[name="order_by"]').forEach(function(el) {
      el.addEventListener('change', function() {
        updateButtonText('order_by', 'orderByButtonText');
      });
    });
  
    // Event Listeners for Order Direction
    document.querySelectorAll('input[name="order_dir"]').forEach(function(el) {
      el.addEventListener('change', function() {
        updateButtonText('order_dir', 'orderDirButtonText');
      });
    });
  
    // Event listener for the Apply button in Period Modal
  document.getElementById('applyPeriodButton').addEventListener('click', function() {
    // Update the periodButton text
    let startDate = document.getElementById('modalStartDate').value;
    let endDate = document.getElementById('modalEndDate').value;
    let periodText = 'Start Date - End Date';
    if (startDate && endDate) {
      periodText = `${startDate} to ${endDate}`;
    }
    document.getElementById('periodButtonText').textContent = periodText;
    
    // Close the modal
    document.getElementById('periodModal').classList.remove('show');
    document.querySelector('.modal-backdrop').remove();
    
    // Apply the filters
    applyFilters();
  });

  // Initial fetch to populate stories on page load
  showLoading();
  fetchStories(true);
});