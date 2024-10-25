// renderStories.js

document.addEventListener("DOMContentLoaded", function() {
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
    if ((window.innerHeight + window.scrollY) >= document.body.offsetHeight - 3000 && !isLoading && hasMoreStories) {
      fetchStories(false);
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
          // Initialize lazy loading after new content is loaded
          if (window.lazyload) {
            lazyload();
          }
          // Reinitialize event listeners for the newly added content
          initializeEventListeners();
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
    colDiv.classList.add('col-md-6', 'col-lg-4', 'my-5');

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
    cardFooter.innerHTML = `
      <div class="row d-flex justify-content-between">
        <div class="col">
          <small class="text-muted fw-bold">${item.pub_date}<span class="mx-1">&#x2022;</span>${item.clicks} views</small>
        </div>
        <div class="col d-flex justify-content-end">
          <i class="fa-regular fa-thumbs-up"></i>
          <i class="fa-regular fa-thumbs-down mx-4"></i>
          <i class="fa-solid fa-thumbtack"></i>
          <i class="fa-solid fa-satellite-dish ms-4 satellite-share-button"></i>
        </div>
      </div>
    `;

    // Assembling the card
    cardDiv.appendChild(imageLink);
    cardDiv.appendChild(tipLogoDiv);
    cardDiv.appendChild(cardBody);
    cardDiv.appendChild(cardFooter);

    colDiv.appendChild(cardDiv);

    // Satellite share button functionality
    const satelliteButton = cardFooter.querySelector('.satellite-share-button');
    satelliteButton.addEventListener('click', () => {
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

    return colDiv;
  }

  // Initialize event listeners for card buttons
  function initializeEventListeners() {
    document.querySelectorAll('.inf-card-header-link').forEach(button => {
      button.addEventListener('click', function(e) {
        e.preventDefault();
        const card = this.closest('.card');
        const cardId = card.id.split('-')[0];
        const newsCategory = card.id.split('-')[1];

        toggleActiveClass(this);

        if (this.classList.contains('description-btn')) {
          // Description button clicked
          fetchDescription(cardId, newsCategory, card);
        } else {
          // Preview button clicked
          updateCardWithPreview(card);
        }
      });
    });
  }

  function toggleActiveClass(clickedButton) {
    const navLinks = clickedButton.closest('.inf-card-header').querySelectorAll('.nav-link');
    navLinks.forEach(link => link.classList.remove('active'));
    clickedButton.classList.add('active');
  }

  function fetchDescription(cardId, newsCategory, card) {
    fetch(`/api/get-description?id=${cardId}`)
      .then(response => response.json())
      .then(data => {
        updateCardWithDescription(data, card);
      })
      .catch(error => console.error('Error:', error));
  }

  function updateCardWithDescription(data, card) {
    const cardTitle = card.querySelector('.card-title');
    const cardText = card.querySelector('.card-text'); // Ensure this selector matches your actual elements
    if (cardTitle) {
        cardTitle.style.display = 'none';
    }
    if (cardText) { // Check if cardText exists before trying to manipulate it
        cardText.style.display = 'none';
    }
    const cardBody = card.querySelector('.card-body');
    if (cardBody && !cardBody.querySelector('.description-text')) {
        cardBody.innerHTML += `<p class="description-text">${data.description}</p>`;
    }
  }

  function updateCardWithPreview(card) {
    const cardTitle = card.querySelector('.card-title');
    const cardText = card.querySelector('.card-text'); // Ensure this selector matches your actual elements
    if (cardTitle) {
        cardTitle.style.display = 'block';
    }
    if (cardText) { // Check if cardText exists before trying to manipulate it
        cardText.style.display = 'block';
    }
    const cardBody = card.querySelector('.card-body');
    if (cardBody) {
        const descriptionElement = cardBody.querySelector('.description-text');
        if (descriptionElement) {
            descriptionElement.remove();
        }
    }
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
        return `<span class="me-1">${differenceInDays}</span> days ago`;
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


  // Initial fetch to populate stories on page load
  showLoading();
  fetchStories(true);
});
