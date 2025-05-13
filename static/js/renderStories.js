document.addEventListener("DOMContentLoaded", function() {
  let infomundiStoryModal = new bootstrap.Modal(document
    .getElementById("infomundiStoryModal"), {
      keyboard: false,
    });

  // Modal element selectors
  const modalElement = document.getElementById("infomundiStoryModal");
  const modalTitle = modalElement.querySelector(".modal-header h1");
  const modalImage = modalElement.querySelector(".modal-header img");
  const modalDescription = modalElement.querySelector(
    ".modal-body p");
  const modalPublisherContainer = modalElement.querySelector(
    "#publisherContainer");
  const modalPublisherLogo = modalElement.querySelector(
    "#publisherLogo");
  const modalPublisherName = modalElement.querySelector(
    "#publisherName");

  const modalTagsContainer = modalElement.querySelector(
    ".modal-body .d-flex.align-items-center");
  const modalLikeIcon = modalElement.querySelector(".fa-thumbs-up");
  const modalDislikeIcon = modalElement.querySelector(
    ".fa-thumbs-down");
  const modalLikeCount = modalLikeIcon.querySelector("span");
  const modalDislikeCount = modalDislikeIcon.querySelector("span");
  const modalSatelliteIcon = modalElement.querySelector(
    ".fa-satellite-dish");
  const modalPublishedDate = modalElement.querySelector(
    "#publishedDateStoryModal");
  const modalViewCount = modalElement.querySelector(
    "#viewCountStoryModal");

  // ──────────────────────────────────────────────────────────
  // Bookmark helpers: sync local + server
  // ──────────────────────────────────────────────────────────

  // Initialize the icon based on localStorage
  function initializeBookmarkIcon(storyId, iconEl) {
    const bookmarks = JSON.parse(localStorage.getItem('bookmarkedStories')) || {};
    const isBookmarked = !!bookmarks[storyId];
    iconEl.classList.toggle('fa-solid', isBookmarked);
    iconEl.classList.toggle('fa-regular', !isBookmarked);
    iconEl.dataset.storyId = storyId;
  }

  // Handle a click: call the API, then update localStorage + UI
  function handleBookmarkToggle(storyId, iconEl) {
    const bookmarks = JSON.parse(localStorage.getItem('bookmarkedStories')) || {};
    const currently = !!bookmarks[storyId];
    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');


    if (!currently) {
      // Add bookmark on server
      fetch('/api/bookmark', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
          },
          body: JSON.stringify({
            story_id: storyId
          })
        })
        .then(res => {
          if (!res.ok) throw new Error('Could not bookmark');
          return res.json();
        })
        .then(() => {
          // On success, mirror state locally & flip icon
          bookmarks[storyId] = true;
          localStorage.setItem('bookmarkedStories', JSON.stringify(bookmarks));
          iconEl.classList.replace('fa-regular', 'fa-solid');
        })
        .catch(err => {
          console.error(err);
          alert('Huh, couldn’t bookmark right now.');
        });
    } else {
      // Remove bookmark on server
      fetch(`/api/bookmark/${storyId}`, {
          method: 'DELETE',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
          }
        })
        .then(res => {
          if (!res.ok) throw new Error('Could not remove bookmark');
          return res.json();
        })
        .then(() => {
          // On success, mirror state locally & flip icon back
          delete bookmarks[storyId];
          localStorage.setItem('bookmarkedStories', JSON.stringify(bookmarks));
          iconEl.classList.replace('fa-solid', 'fa-regular');
        })
        .catch(err => {
          console.error(err);
          alert('Huh, couldn’t remove bookmark right now.');
        });
    }
  }



  // Function to initialize like/dislike icons based on localStorage
  function initializeLikeDislikeIcons(storyId, likeIcon,
    dislikeIcon) {
    const savedInteractions = JSON.parse(localStorage.getItem(
      'storyInteractions')) || {};
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
    handleLikeDislike('like', storyId, modalLikeIcon,
      modalDislikeIcon, modalLikeCount,
      modalDislikeCount);
  });

  modalDislikeIcon.addEventListener('click', function() {
    const storyId = this.dataset.storyId;
    handleLikeDislike('dislike', storyId, modalLikeIcon,
      modalDislikeIcon, modalLikeCount,
      modalDislikeCount);
  });

  // Satellite share button functionality
  modalSatelliteIcon.addEventListener('click', function() {
    const storyId = this.dataset.storyId;
    const storyTitle = this.dataset.storyTitle;
    const storyDescription = this.dataset
      .storyDescription || '';
    if (navigator.share) {
      navigator.share({
        title: storyTitle,
        text: storyDescription,
        url: window.location.origin +
          `/comments?id=${storyId}`
      }).then(() => {
        console.log('Thanks for sharing!');
      }).catch(console.error);
    } else {
      alert('Sharing is not supported on this browser.');
    }
  });

    // Grab it once
  const modalBookmarkIcon = document
    .getElementById("infomundiStoryModal")
    .querySelector('.fa-bookmark');

  // Single event listener
  modalBookmarkIcon.addEventListener('click', function (e) {
    e.stopPropagation();
    const storyId = this.dataset.storyId;      // set elsewhere
    handleBookmarkToggle(storyId, this);
  });

  modalElement.addEventListener("hidden.bs.modal", function() {
    modalTitle.textContent = "";
    modalImage.src = "";
    modalDescription.textContent = "";
    modalTagsContainer.innerHTML =
      ""; // Clear the tags container
    modalLikeCount.innerHTML = " 0";
    modalDislikeCount.innerHTML = " 0";
    modalPublishedDate.innerHTML = "";
    modalViewCount.innerHTML = "";
    modalPublisherName.textContent = "";
    modalPublisherLogo.src = "";
    modalPublisherLogo.style.display = "none";
    modalLikeIcon.dataset.storyId = "";
    modalDislikeIcon.dataset.storyId = "";
    modalSatelliteIcon.dataset.storyId = "";
    modalSatelliteIcon.dataset.storyTitle = "";
    modalSatelliteIcon.dataset.storyDescription = "";
  });

  // Attach event listener to dynamically created story cards
  function attachModalEvents() {
    const storyCards = document.querySelectorAll(
      ".card.image-card");

    storyCards.forEach((card) => {
      card.addEventListener("click", function(event) {
        const clickedElement = event
          .target; // Get the clicked element

        // Check if the click is on the image or card body (title + description)
        if (
          clickedElement.classList.contains(
            "card-img-top") || // Image
          clickedElement.closest(
            ".card-body") // Card body (title + description)
        ) {
          event
            .preventDefault(); // Prevent navigation

          // Extract story data from the clicked card
          const storyData = JSON.parse(this
            .dataset.storyData);

          // Update modal content
          modalTitle.textContent = storyData
            .title;
          modalImage.src = storyData
            .image_url;
          // Set the story description and link dynamically
          modalDescription.textContent =
            storyData.description ||
            "No description available.";

          // Update the link to the original story
          const originalStoryLink =
            modalElement.querySelector(
              "#originalStoryLink");
          if (storyData.url) {
            originalStoryLink.href =
              `/comments?id=${storyData.story_id}`;
            originalStoryLink.innerHTML =
              `<i class="fa-solid fa-square-arrow-up-right me-2"></i>View More`;
          } else {
            originalStoryLink.style
              .display =
              "none"; // Hide the link if no URL is available
          }

          // Update tags as links
          modalTagsContainer.innerHTML =
            ""; // Clear previous tags
          if (storyData.tags && Array.isArray(
              storyData.tags)) {
            storyData.tags.forEach((
              tag) => {
              const tagLink =
                document
                .createElement(
                  "span");
              tagLink.className =
                "badge text-bg-primary me-1";
              tagLink
                .textContent =
                tag;
              modalTagsContainer
                .appendChild(
                  tagLink);
            });
          }

          // Update publisher logo and name
          if (storyData.publisher) {
            const {
              name,
              favicon_url
            } = storyData.publisher;

            modalPublisherName.textContent =
              name || "Unknown Publisher";

            modalPublisherName.setAttribute('href', storyData.url);

            if (favicon_url) {
              modalPublisherLogo.src =
                favicon_url;
              modalPublisherLogo.style
                .display =
                "inline"; // Show the logo if available
            } else {
              modalPublisherLogo.style
                .display =
                "none"; // Hide the logo if not available
            }
          } else {
            modalPublisherName.textContent =
              "Unknown Publisher";
            modalPublisherLogo.style
              .display =
              "none"; // Hide the logo if publisher info is not provided
          }

          // Update data attributes for the icons
          modalLikeIcon.dataset.storyId =
            storyData.story_id;
          modalLikeIcon.dataset.liked =
            storyData.is_liked ? "true" :
            "false";
          modalDislikeIcon.dataset.storyId =
            storyData.story_id;
          modalDislikeIcon.dataset.disliked =
            storyData.is_disliked ? "true" :
            "false";

          // Update like/dislike counts
          modalLikeCount.innerHTML =
            `&nbsp;${storyData.likes || 0}`;
          modalDislikeCount.innerHTML =
            `&nbsp;${storyData.dislikes || 0}`;

          // Update icons based on is_liked/is_disliked
          modalLikeIcon.classList.toggle(
            "fa-solid", storyData
            .is_liked);
          modalLikeIcon.classList.toggle(
            "fa-regular", !storyData
            .is_liked);
          modalDislikeIcon.classList.toggle(
            "fa-solid", storyData
            .is_disliked);
          modalDislikeIcon.classList.toggle(
            "fa-regular", !storyData
            .is_disliked);

          // Update satellite icon data attributes
          modalSatelliteIcon.dataset.storyId =
            storyData.story_id;
          modalSatelliteIcon.dataset
            .storyTitle = storyData.title;
          modalSatelliteIcon.dataset
            .storyDescription = storyData
            .description || "";

          // Update published date and view count
          modalPublishedDate.innerHTML =
            `<i class="fa-regular fa-calendar me-2"></i>${timeAgo(storyData.pub_date)}`;
          modalPublishedDate.setAttribute('tabindex', '0');
          modalPublishedDate.dataset.bsToggle = "tooltip";
          modalPublishedDate.dataset.bsPlacement = "top";
          modalPublishedDate.setAttribute('title', storyData.pub_date);

          modalViewCount.innerHTML =
            `<i class="fa-regular fa-eye me-2"></i>${storyData.views}&nbsp;views`;

          // Initialize comments section for the selected story
          const commentsElement = document
            .querySelector(
              'infomundi-comments');
          commentsElement.setAttribute(
            'page_id', storyData
            .story_id);

          // Grab the modal’s thumbtack
          const modalBookmarkIcon = modalElement.querySelector('.fa-bookmark');

          modalBookmarkIcon.dataset.storyId = storyData.id;
          initializeBookmarkIcon(storyData.id, modalBookmarkIcon);

          // Load Maximus content
          fetchAndRenderStorySummary(storyData
            .story_id);

          initializeLikeDislikeIcons(storyData
            .story_id, modalLikeIcon,
            modalDislikeIcon);
          // Show the modal
          infomundiStoryModal.show();
        }
      });
    });
  }

  // Event listener for the Clear Filters button
  document.getElementById('clearFiltersButton').addEventListener(
    'click',
    function() {
      // Reset form fields to their default values
      document.getElementById('query').value = '';
      document.getElementById('modalStartDate').value = '';
      document.getElementById('modalEndDate').value = '';

      // Reset radio buttons to default
      document.querySelector(
          `input[name="category"][value="general"]`)
        .checked = true;
      document.querySelector(
          `input[name="order_by"][value="pub_date"]`)
        .checked = true;
      document.querySelector(
          `input[name="order_dir"][value="desc"]`)
        .checked = true;

      // Reset button texts
      document.getElementById('categoryButtonText')
        .textContent = 'General';
      document.getElementById('orderByButtonText')
        .textContent = 'Publication Date';
      document.getElementById('orderDirButtonText')
        .textContent = 'Descending';
      document.getElementById('periodButtonText')
        .textContent = 'Start Date - End Date';

      // Clear filters from localStorage
      localStorage.removeItem('newsFilters');

      // Reset filters in the application by applying the default state
      applyFilters();
    });

  const filterForm = document.getElementById("filterForm");
  const storiesContainer = document.getElementById(
    "storiesContainer");
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
  }

  // Prevent form submission
  filterForm.addEventListener('submit', function(event) {
    event.preventDefault();
  });

  // Event listeners for filter inputs
  // Category Radio Buttons
  document.querySelectorAll('input[name="category"]').forEach(
    function(el) {
      el.addEventListener('change', function() {
        applyFilters();
      });
    });

  // Order By Radio Buttons
  document.querySelectorAll('input[name="order_by"]').forEach(
    function(el) {
      el.addEventListener('change', function() {
        applyFilters();
      });
    });

  // Order Direction Radio Buttons
  document.querySelectorAll('input[name="order_dir"]').forEach(
    function(el) {
      el.addEventListener('change', function() {
        applyFilters();
      });
    });

  // Date Inputs
  document.getElementById('modalStartDate').addEventListener('change',
    function() {
      applyFilters();
    });

  document.getElementById('modalEndDate').addEventListener('change',
    function() {
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
  document.getElementById('query').addEventListener('input',
    function() {
      debounceApplyFilters();
    });

  window.addEventListener('scroll', () => {
    if ((window.innerHeight + window.scrollY) >= document
      .body.offsetHeight - 2000 && !isLoading &&
      hasMoreStories) {
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

    const tooltipTriggerList = document.querySelectorAll(
      '[data-bs-toggle="tooltip"]');

    if (tooltipTriggerList.length > 0) {
      [...tooltipTriggerList].map(tooltipTriggerEl =>
        new bootstrap.Tooltip(tooltipTriggerEl));
    }

    isLoading = true;
    const category = document.querySelector(
      'input[name="category"]:checked').value;
    const orderBy = document.querySelector(
      'input[name="order_by"]:checked').value;
    const orderDir = document.querySelector(
      'input[name="order_dir"]:checked').value;
    const country = document.getElementById("country").value;
    const startDate = document.getElementById("modalStartDate")
      .value;
    const endDate = document.getElementById("modalEndDate").value;
    const query = document.getElementById("query").value;

    let url =
      `/api/get_stories?country=${country}&category=${category}&order_by=${orderBy}&order_dir=${orderDir}&page=${currentPage}`;

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
          storiesContainer.innerHTML =
            ''; // Clear the container for new filter
        }
        if (data.length > 0) {
          data.forEach((item, index) => {
            const storyCard = createStoryCard(
              item, index);
            storiesContainer.appendChild(
              storyCard);
          });
          attachModalEvents
            (); // Attach modal events to newly created cards
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
    cardDiv.classList.add('card', 'image-card', 'inf-story-card',
      'border', 'border-0');
    cardDiv.id = `${item.story_id}`;

    // Image link
    const imageLink = document.createElement('a');
    imageLink.href = `/comments?id=${item.story_id}`;

    // Image tag
    const imgTag = document.createElement('img');
    imgTag.classList.add('card-img-top', 'rounded');
    imgTag.alt = item.title;
    imgTag.style =
      'width: 100%; aspect-ratio: 16 / 9; object-fit: cover;';
    if (index < 3) {
      imgTag.src = item.image_url;
      imgTag.setAttribute('fetchpriority', 'high');
    } else {
      imgTag.setAttribute('data-src', item.image_url);
      imgTag.classList.add('lazyload');
    }
    imageLink.appendChild(imgTag);

    // Tip logo overlay
    const tipLogoDiv = document.createElement('div');
    tipLogoDiv.classList.add('tip-logo');

    const tipLogoImg = document.createElement('div');
    tipLogoImg.innerHTML = `
        <span data-bs-toggle="tooltip" data-bs-title="Source: ${item.publisher.name}">
          ${item.publisher.favicon_url ? 
            `<img src="${item.publisher.favicon_url}" class="rounded" alt="${item.publisher.name} favicon image" width="30">` : 
            `<i class="fa-solid fa-tower-cell"></i>`
          }
        </a>
    `;
    tipLogoDiv.appendChild(tipLogoImg);

    // Card body
    const cardBody = document.createElement('div');
    cardBody.classList.add('card-body', 'inf-story-card-body', 'px-1');
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
    cardFooter.classList.add('card-footer', 'px-1', 'inf-story-card-footer',
      'bg-transparent', 'border', 'border-0');

    const rowDiv = document.createElement('div');
    rowDiv.classList.add('row', 'd-flex',
      'justify-content-between');

    const colLeft = document.createElement('div');
    colLeft.classList.add('col');

    const dateSpan = document.createElement('span');
    dateSpan.classList.add('text-muted', 'fw-bold', 'small');
    dateSpan.innerHTML =
      `<span class="date-info" id="date-info">${item.pub_date}</span><span class="mx-1">•</span>${item.views}&nbsp;views`;

    colLeft.appendChild(dateSpan);

    const colRight = document.createElement('div');
    colRight.classList.add('col', 'd-flex', 'justify-content-end');

    // Like Icon with Count
    const likeIcon = document.createElement('i');
    likeIcon.classList.add(item.is_liked ? 'fa-solid' :
      'fa-regular', 'fa-thumbs-up');
    likeIcon.style.cursor = 'pointer';
    likeIcon.dataset.storyId = item.story_id;
    likeIcon.dataset.liked = item.is_liked ? 'true' : 'false';

    const likeCount = document.createElement('span');
    likeCount.innerHTML =
      `&nbsp;${item.likes || 0}`; // Display the like count
    likeIcon.appendChild(likeCount);

    // Dislike Icon with Count
    const dislikeIcon = document.createElement('i');
    dislikeIcon.classList.add(item.is_disliked ? 'fa-solid' :
      'fa-regular', 'fa-thumbs-down', 'mx-4');
    dislikeIcon.style.cursor = 'pointer';
    dislikeIcon.dataset.storyId = item.story_id;
    dislikeIcon.dataset.disliked = item.is_disliked ? 'true' :
      'false';

    const dislikeCount = document.createElement('span');
    dislikeCount.innerHTML =
      `&nbsp;${item.dislikes || 0}`; // Display the dislike count
    dislikeIcon.appendChild(dislikeCount);

    // Event listeners for like and dislike icons
    likeIcon.addEventListener('click', function() {
      handleLikeDislike('like', item.story_id, likeIcon,
        dislikeIcon, likeCount, dislikeCount);
    });

    dislikeIcon.addEventListener('click', function() {
      handleLikeDislike('dislike', item.story_id,
        likeIcon, dislikeIcon, likeCount,
        dislikeCount);
    });

    // Bookmark Icon
    const thumbtackIcon = document.createElement('i');
    thumbtackIcon.classList.add('fa-bookmark');
    thumbtackIcon.style.cursor = 'pointer';

    // 1️⃣ Initialize from localStorage
    initializeBookmarkIcon(item.id, thumbtackIcon);

    // 2️⃣ On click, sync with server then local
    thumbtackIcon.addEventListener('click', e => {
      e.stopPropagation(); // don’t open the modal!
      handleBookmarkToggle(item.id, thumbtackIcon);
    });

    // Satellite Share Icon
    const satelliteIcon = document.createElement('i');
    satelliteIcon.classList.add('fa-solid', 'fa-satellite-dish',
      'ms-4', 'satellite-share-button');
    satelliteIcon.style.cursor = 'pointer';

    // Satellite share button functionality
    satelliteIcon.addEventListener('click', () => {
      if (navigator.share) {
        navigator.share({
          title: item.title,
          text: item.description || '',
          url: window.location.origin +
            `/comments?id=${item.story_id}`
        }).then(() => {
          console.log('Thanks for sharing!');
        }).catch(console.error);
      } else {
        // Fallback for browsers that don't support the Web Share API
        alert(
          'Sharing is not supported on this browser.');
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
    initializeLikeDislikeIcons(item.story_id, likeIcon,
      dislikeIcon);

    return colDiv;
  }


  function handleLikeDislike(action, storyId, likeIcon, dislikeIcon,
    likeCount, dislikeCount) {
    // Fetch the saved likes/dislikes data from localStorage
    let savedInteractions = JSON.parse(localStorage.getItem(
      'storyInteractions')) || {};
    let previousState = {
      ...savedInteractions
    }; // Store previous state for rollback

    // Determine the new state
    let newAction = null;
    if (action === 'like') {
      if (savedInteractions[storyId]?.action === 'like') {
        delete savedInteractions[storyId];
      } else {
        savedInteractions[storyId] = {
          action: 'like'
        };
        newAction = 'like';
      }
    } else if (action === 'dislike') {
      if (savedInteractions[storyId]?.action === 'dislike') {
        delete savedInteractions[storyId];
      } else {
        savedInteractions[storyId] = {
          action: 'dislike'
        };
        newAction = 'dislike';
      }
    }

    // Send the request first before updating the UI
    fetch(`/api/story/${action}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          id: storyId
        })
      })
      .then(response => {
        if (!response.ok) {
          return response.json().then(errorData => {
            throw new Error(errorData.message ||
              'Error performing action');
          });
        }
        return response.json();
      })
      .then(data => {
        // Only update localStorage & UI if request succeeds
        localStorage.setItem('storyInteractions', JSON
          .stringify(savedInteractions));

        // Update UI
        const isLiked = savedInteractions[storyId]
          ?.action === 'like';
        const isDisliked = savedInteractions[storyId]
          ?.action === 'dislike';

        likeIcon.classList.toggle('fa-solid', isLiked);
        likeIcon.classList.toggle('fa-regular', !isLiked);
        dislikeIcon.classList.toggle('fa-solid',
          isDisliked);
        dislikeIcon.classList.toggle('fa-regular', !
          isDisliked);

        // Update counts
        likeCount.textContent = ` ${data.likes}`;
        dislikeCount.textContent = ` ${data.dislikes}`;
      })
      .catch(error => {
        alert(error.message);
        savedInteractions = previousState; // Revert state
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
    const differenceInSeconds = Math.floor((currentDate -
      originalDate) / 1000);
    const differenceInHours = Math.floor(differenceInSeconds /
      3600);
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
      const originalDateString = element.textContent
        .trim(); // Extract the date string
      const relativeDateString = timeAgo(
        originalDateString
      ); // Convert to relative format
      element.innerHTML =
        relativeDateString; // Update the element content
    });
  }


  // Function to save filter settings to localStorage
  function saveFiltersToLocalStorage() {
    const category = document.querySelector(
      'input[name="category"]:checked').value;
    const orderBy = document.querySelector(
      'input[name="order_by"]:checked').value;
    const orderDir = document.querySelector(
      'input[name="order_dir"]:checked').value;
    const startDate = document.getElementById("modalStartDate")
      .value;
    const endDate = document.getElementById("modalEndDate").value;
    const query = document.getElementById("query").value;

    localStorage.setItem('newsFilters', JSON.stringify({
      category,
      orderBy,
      orderDir,
      startDate,
      endDate,
      query
    }));
  }


  // Function to load filter settings from localStorage
  function loadSavedFilters() {
    const savedFilters = JSON.parse(localStorage.getItem(
      'newsFilters'));
    if (savedFilters) {
      const {
        category,
        orderBy,
        orderDir,
        startDate,
        endDate,
        query
      } = savedFilters;
      document.querySelector(
          `input[name="category"][value="${category}"]`)
        .checked = true;
      document.querySelector(
          `input[name="order_by"][value="${orderBy}"]`)
        .checked = true;
      document.querySelector(
          `input[name="order_dir"][value="${orderDir}"]`)
        .checked = true;
      document.getElementById("modalStartDate").value = startDate;
      document.getElementById("modalEndDate").value = endDate;
      document.getElementById("query").value = query;

      // Update periodButtonText
      let periodText = 'Start Date - End Date';
      if (startDate && endDate) {
        periodText = `${startDate} to ${endDate}`;
      }
      document.getElementById('periodButtonText').textContent =
        periodText;
    }
  }

  function updateButtonText(inputName, buttonTextId) {
    var selectedLabel = document.querySelector(
      `input[name="${inputName}"]:checked`).nextElementSibling;
    var selectedText = selectedLabel.querySelector('.label-text')
      .textContent.trim();
    document.getElementById(buttonTextId).textContent =
      selectedText;
  }

  // Initialize Button Texts
  updateButtonText('category', 'categoryButtonText');
  updateButtonText('order_by', 'orderByButtonText');
  updateButtonText('order_dir', 'orderDirButtonText');

  // Event Listeners for Category
  document.querySelectorAll('input[name="category"]').forEach(
    function(el) {
      el.addEventListener('change', function() {
        updateButtonText('category',
          'categoryButtonText');
      });
    });

  // Event Listeners for Order By
  document.querySelectorAll('input[name="order_by"]').forEach(
    function(el) {
      el.addEventListener('change', function() {
        updateButtonText('order_by',
          'orderByButtonText');
      });
    });

  // Event Listeners for Order Direction
  document.querySelectorAll('input[name="order_dir"]').forEach(
    function(el) {
      el.addEventListener('change', function() {
        updateButtonText('order_dir',
          'orderDirButtonText');
      });
    });

  // Event listener for the Apply button in Period Modal
  document.getElementById('applyPeriodButton').addEventListener(
    'click',
    function() {
      // Update the periodButton text
      let startDate = document.getElementById(
        'modalStartDate').value;
      let endDate = document.getElementById('modalEndDate')
        .value;
      let periodText = 'Start Date - End Date';
      if (startDate && endDate) {
        periodText = `${startDate} to ${endDate}`;
      }
      document.getElementById('periodButtonText')
        .textContent = periodText;

      // Close the modal
      document.getElementById('periodModal').classList.remove(
        'show');
      document.querySelector('.modal-backdrop').remove();

      // Apply the filters
      applyFilters();
    });

  // Initial fetch to populate stories on page load
  showLoading();
  fetchStories(true);
});