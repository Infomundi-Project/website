document.addEventListener("DOMContentLoaded", function() {
  const filterForm = document.getElementById("filterForm");
  const storiesContainer = document.getElementById("storiesContainer");
  const filterButton = document.getElementById("filterButton");
  const filterButtonText = document.getElementById("filterButtonText");
  const filterSpinner = document.getElementById("filterSpinner");

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

  filterForm.addEventListener("submit", function(event) {
    event.preventDefault();
    saveFiltersToLocalStorage(); // Save filters before fetching stories
    showLoading();
    currentPage = 1;
    hasMoreStories = true;
    fetchStories(true);
  });

  window.addEventListener('scroll', () => {
    if ((window.innerHeight + window.scrollY) >= document.body.offsetHeight - 2500 && !isLoading && hasMoreStories) {
      fetchStories(false);
    }
  });

  function showLoading() {
    filterButton.disabled = true;
    filterButtonText.style.display = 'none';
    filterSpinner.style.display = 'inline-block';
  }

  function hideLoading() {
    filterButton.disabled = false;
    filterButtonText.style.display = 'inline';
    filterSpinner.style.display = 'none';
  }

  function fetchStories(reset) {
    if (isLoading) return;

    isLoading = true;
    const category = document.querySelector('input[name="category"]:checked').value;
    const orderBy = document.querySelector('input[name="order_by"]:checked').value;
    const orderDir = document.querySelector('input[name="order_dir"]:checked').value;
    const country = document.getElementById("country").value;

    const url = `/api/get_stories?country=${country}&category=${category}&order_by=${orderBy}&order_dir=${orderDir}&page=${currentPage}`;

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
    colDiv.classList.add('col-md-6', 'col-xxl-4');

    const cardDiv = document.createElement('div');
    cardDiv.classList.add('card', 'mt-4', 'border-opacity-10');
    cardDiv.style.minHeight = '65vh';
    cardDiv.style.height = 'auto';
    cardDiv.id = `${item.story_id}-${item.category_id}`;

    const cardHeader = document.createElement('div');
    cardHeader.classList.add('card-header');
    cardHeader.innerHTML = `
      <ul class="nav nav-pills nav-fill card-header-pills inf-card-header">
        <li class="nav-item">
          <a class="nav-link active inf-card-header-link" href="#">Preview</a>
        </li>
        ${item.description && item.description.length > 10 ? 
          `<li class="nav-item">
            <a class="nav-link description-btn inf-card-header-link" href="#">Description</a>
          </li>` : ''
        }
      </ul>
    `;

    const cardBody = document.createElement('div');
    cardBody.classList.add('card-body');
    cardBody.innerHTML = `
      <a href="/comments?id=${item.story_id}" class="text-reset text-decoration-none">
        <h6 class="card-title">${item.title}</h6>
      </a>
    `;

    const imageLink = document.createElement('a');
    imageLink.href = `/comments?id=${item.story_id}`;
    
    const imgTag = document.createElement('img');
    imgTag.alt = 'News image';
    imgTag.width = 500;
    imgTag.height = 333;
    imgTag.style = 'aspect-ratio: 16 / 9;width: 100%;object-fit: cover;';
    if (index < 3) {
      imgTag.src = item.media_content_url;
      imgTag.setAttribute('fetchpriority', 'high');
    } else {
      imgTag.setAttribute('data-src', item.media_content_url);
      imgTag.classList.add('lazyload');
    }
    imageLink.appendChild(imgTag);

    const cardFooter = document.createElement('div');
    cardFooter.classList.add('card-footer', 'text-body-secondary');
    cardFooter.innerHTML = `
      <small>
        <a href="${item.publisher.link}" class="text-decoration-none" target="_blank">
          ${item.publisher.favicon ? 
            `<img src="${item.publisher.favicon}" class="rounded me-1" alt="${item.publisher.name} favicon image" width="24" height="24">` : 
            `<i class="fa-solid fa-rss me-1"></i>`
          }${item.publisher.name}
        </a>
        <span class="ms-1 me-2">&#x2022;</span><span><i class="fa-solid fa-calendar-days me-1"></i></span><span class="date-info">${item.pub_date}</span>
      </small>
    `;

    cardDiv.appendChild(cardHeader);
    cardDiv.appendChild(imageLink);
    cardDiv.appendChild(cardBody);

    if (item.tags || item.total_comments || item.clicks) {
      const listGroup = document.createElement('ul');
      listGroup.classList.add('list-group', 'list-group-flush', 'mt-3');

      const listItem = document.createElement('li');
      listItem.classList.add('list-group-item');

      if (item.tags) {
        item.tags.forEach(tag => {
          const badge = document.createElement('a');
          badge.href = `https://infomundi.net/news?country=${item.country_code}&query=${tag}&section=${item.news_filter}`;
          badge.innerHTML = `<span class="badge text-bg-secondary">${tag}</span>`;
          listItem.appendChild(badge);
        });
      }

      if (item.clicks) {
        listItem.innerHTML += `<span class="badge text-bg-info"><i class="fa-solid fa-eye"></i> ${item.clicks}</span>`;
      }

      if (item.total_comments) {
        listItem.innerHTML += `<span class="badge text-bg-dark"><i class="fa fa-comment"></i> ${item.total_comments}</span>`;
      }

      listGroup.appendChild(listItem);
      cardDiv.appendChild(listGroup);
    }

    cardDiv.appendChild(cardFooter);
    colDiv.appendChild(cardDiv);

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
    fetch(`/api/get-description?id=${cardId}&category=${newsCategory}`)
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

    localStorage.setItem('newsFilters', JSON.stringify({ category, orderBy, orderDir }));
  }

  // Function to load filter settings from localStorage
  function loadSavedFilters() {
    const savedFilters = JSON.parse(localStorage.getItem('newsFilters'));
    if (savedFilters) {
      const { category, orderBy, orderDir } = savedFilters;
      document.querySelector(`input[name="category"][value="${category}"]`).checked = true;
      document.querySelector(`input[name="order_by"][value="${orderBy}"]`).checked = true;
      document.querySelector(`input[name="order_dir"][value="${orderDir}"]`).checked = true;
    }
  }

  // Initial fetch to populate stories on page load
  fetchStories(true);
});
