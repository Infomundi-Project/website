// Lock to prevent multiple requests
let maximusIsFetchingSummary = false;
let maximusAbortController = null; // For cancelling requests

// Cooldown mechanism for refresh
let maximusLastFetchTime = 0;
const MAXIMUS_COOLDOWN_MS = 30000; // 30 seconds cooldown
let maximusCooldownInterval = null;

const maximusBlurredText = document.getElementById("maximusSummaryBlurredText");
const maximusProgressBar = document.getElementById("maximusSummaryProgressBar");
const loremIpsum =
  `Lorem ipsum dolor sit amet, consectetur adipiscing elit. Maecenas fermentum lorem consequat diam tempor malesuada. Nunc id odio lorem. Duis quis cursus nisi. Curabitur cursus eget augue a rutrum. Maecenas vestibulum nunc id eros ultrices, id sollicitudin diam lacinia. Proin eget eros ultrices, vestibulum est et, vestibulum nisi. Vivamus erat odio, convallis nec efficitur dapibus, imperdiet sit amet libero. Donec sed molestie urna. Praesent pretium metus id augue tristique, eget elementum mi convallis. Nullam ex dui, scelerisque eget dui in, rutrum maximus diam. Donec elementum efficitur est, in imperdiet diam scelerisque eu. Mauris maximus risus mi, at pellentesque tellus congue ut. Morbi libero nulla, dapibus eget ex aliquam, rhoncus tincidunt leo. Cras tempor purus at mauris tempus posuere. Donec ultricies tellus risus, vel aliquam nulla tristique et. Morbi vehicula augue ut iaculis sodales.

Nullam auctor, enim nec luctus iaculis, urna orci posuere diam, eget aliquam sem magna et ex. Ut feugiat, mauris quis suscipit vulputate, ante quam porta dolor, ac eleifend neque risus non tellus. Vestibulum sit amet velit nibh. Etiam quis tortor id turpis condimentum tempor ut eu metus. Pellentesque in fermentum massa. Donec elit magna, dictum ut tellus ac, blandit fringilla magna. Sed pulvinar non mauris eget aliquet. Vivamus lectus nibh, porta sed leo in, lobortis sollicitudin erat. Nullam eu lorem vehicula, sodales massa vitae, tempus velit. Morbi at consequat ligula. Interdum et malesuada fames ac ante ipsum primis in faucibus. Vestibulum scelerisque libero in odio vulputate lacinia.`;

let maximusCurrentIndex = 0;
let maximusTotalCharacters = loremIpsum.replace(/\s+/g, "").length;
let maximusAnimationTimeout = null; // For cancelling animation

// Configuration
const TYPING_SPEED_MS = 30; // Readable typing speed
const PROGRESS_UPDATE_THROTTLE = 10; // Update progress every N characters

function resetAndPlayPlaceholder() {
  // Cancel any existing animation
  if (maximusAnimationTimeout) {
    clearTimeout(maximusAnimationTimeout);
  }

  maximusBlurredText.textContent = "";
  maximusCurrentIndex = 0;
  maximusProgressBar.style.width = "0%";
  maximusProgressBar.setAttribute("aria-valuenow", "0");

  // Update accessibility
  if (maximusProgressBar) {
    maximusProgressBar.setAttribute("aria-label", "Loading summary");
    maximusProgressBar.setAttribute("aria-busy", "true");
  }

  function typeText() {
    if (maximusCurrentIndex < loremIpsum.length) {
      const currentChar = loremIpsum[maximusCurrentIndex];
      if (currentChar.trim()) {
        maximusBlurredText.textContent += currentChar;

        // Throttle progress bar updates for better performance
        const charCount = maximusBlurredText.textContent.replace(/\s+/g, "").length;
        if (charCount % PROGRESS_UPDATE_THROTTLE === 0 || maximusCurrentIndex === loremIpsum.length - 1) {
          const progress = Math.min((charCount / maximusTotalCharacters) * 100, 100);
          maximusProgressBar.style.width = `${progress}%`;
          maximusProgressBar.setAttribute("aria-valuenow", progress.toFixed(0));
        }
      }
      maximusCurrentIndex++;
      maximusAnimationTimeout = setTimeout(typeText, TYPING_SPEED_MS);
    } else {
      // Animation complete
      if (maximusProgressBar) {
        maximusProgressBar.setAttribute("aria-busy", "false");
      }
    }
  }

  typeText();
}

function stopPlaceholderAnimation() {
  if (maximusAnimationTimeout) {
    clearTimeout(maximusAnimationTimeout);
    maximusAnimationTimeout = null;
  }
  if (maximusProgressBar) {
    maximusProgressBar.setAttribute("aria-busy", "false");
  }
}

function cancelSummaryRequest() {
  if (maximusAbortController) {
    maximusAbortController.abort();
    maximusAbortController = null;
  }
  stopPlaceholderAnimation();
  maximusIsFetchingSummary = false;
}

// Check if cooldown is active
function isOnCooldown() {
  const now = Date.now();
  const timeSinceLastFetch = now - maximusLastFetchTime;
  return timeSinceLastFetch < MAXIMUS_COOLDOWN_MS;
}

// Get remaining cooldown time in seconds
function getRemainingCooldown() {
  const now = Date.now();
  const timeSinceLastFetch = now - maximusLastFetchTime;
  const remaining = MAXIMUS_COOLDOWN_MS - timeSinceLastFetch;
  return Math.ceil(remaining / 1000);
}

// Update refresh button state
function updateRefreshButton() {
  const refreshButton = document.getElementById('maximusRefreshButton');
  if (!refreshButton) return;

  if (isOnCooldown()) {
    const remaining = getRemainingCooldown();
    refreshButton.disabled = true;
    refreshButton.textContent = `Refresh (${remaining}s)`;
    refreshButton.setAttribute('aria-label', `Refresh summary (available in ${remaining} seconds)`);
  } else {
    refreshButton.disabled = false;
    refreshButton.textContent = 'Refresh Summary';
    refreshButton.setAttribute('aria-label', 'Refresh summary');
  }
}

// Start cooldown timer
function startCooldownTimer() {
  // Clear any existing interval
  if (maximusCooldownInterval) {
    clearInterval(maximusCooldownInterval);
  }

  // Update button immediately
  updateRefreshButton();

  // Update button every second during cooldown
  maximusCooldownInterval = setInterval(() => {
    if (isOnCooldown()) {
      updateRefreshButton();
    } else {
      updateRefreshButton();
      clearInterval(maximusCooldownInterval);
      maximusCooldownInterval = null;
    }
  }, 1000);
}

// Request new summary with cooldown check
function requestNewSummary(storyId) {
  if (isOnCooldown()) {
    const remaining = getRemainingCooldown();
    announceToScreenReader(`Please wait ${remaining} seconds before requesting a new summary`);
    return;
  }

  if (maximusIsFetchingSummary) {
    announceToScreenReader('Summary is already being fetched');
    return;
  }

  // Update last fetch time
  maximusLastFetchTime = Date.now();
  startCooldownTimer();

  // Fetch the new summary with refresh flag
  fetchAndRenderStorySummary(storyId, true);
}

function fetchAndRenderStorySummary(storyId, isRefresh = false) {
  if (maximusIsFetchingSummary) return; // Prevent duplicate requests
  maximusIsFetchingSummary = true; // Set lock

  // Record fetch time for cooldown tracking
  maximusLastFetchTime = Date.now();
  startCooldownTimer();

  // Create new abort controller for this request
  maximusAbortController = new AbortController();

  const contentPlaceholder = document.querySelector(
    ".maximus-summary-content-placeholder");
  const maximusApiResponse = document.querySelector(
    ".maximus-summary-api-response");

  // Reset: Show the placeholder and clear the response container
  if (contentPlaceholder) {
    contentPlaceholder.style.display = "flex";
    // Add aria-live region for accessibility
    contentPlaceholder.setAttribute("aria-live", "polite");
    contentPlaceholder.setAttribute("aria-busy", "true");
  }

  if (maximusApiResponse) {
    maximusApiResponse.innerHTML = "";
    maximusApiResponse.setAttribute("aria-live", "polite");
  }

  resetAndPlayPlaceholder(); // Play loading animation

  // Add refresh parameter if this is a refresh request
  const url = isRefresh
    ? `/api/story/summarize/${storyId}?refresh=true`
    : `/api/story/summarize/${storyId}`;

  fetch(url, {
    signal: maximusAbortController.signal
  })
    .then((response) => {
      if (!response.ok) {
        // If the response isn't OK, parse the JSON and throw the error
        return response.json().then((errorData) => {
          throw new Error(errorData.response ||
            "Failed to fetch story summary.");
        });
      }
      return response.json();
    })
    .then((data) => {
      stopPlaceholderAnimation(); // Stop animation when data arrives

      const responseData = data.response;

      if (!responseData) {
        showEmptySummary(maximusApiResponse, contentPlaceholder);
        return;
      }

      const {
        addressed_topics,
        context_around,
        questioning_the_subject,
        methods_for_inquiry
      } = responseData;

      if (!addressed_topics && !context_around && !questioning_the_subject &&
        !methods_for_inquiry) {
        showEmptySummary(maximusApiResponse, contentPlaceholder);
        return;
      }

      // Construct content dynamically
      let contentHTML = "";

      // Add "Addressed Topics"
      if (addressed_topics?.length) {
        contentHTML += `
                  <h4>Addressed Topics</h4>
                  <ul>${addressed_topics.map((topic) => `<li>${escapeHtml(topic)}</li>`).join("")}</ul>
                  <hr class="my-3">
              `;
      }

      // Add "Context Around"
      if (context_around?.length) {
        contentHTML += `
                  <h4>Context Around</h4>
                  <ul>${context_around.map((context) => `<li>${escapeHtml(context)}</li>`).join("")}</ul>
                  <hr class="my-3">
              `;
      }

      // Add "Methods for Inquiry"
      if (methods_for_inquiry?.length) {
        contentHTML += `
                  <h4>Methods for Investigation</h4>
                  <ul>${methods_for_inquiry.map((method) => `<li>${escapeHtml(method)}</li>`).join("")}</ul>
                  <hr class="my-3">
              `;
      }

      // Move "Questioning the Subject" into chat as suggestion chips
      if (Array.isArray(questioning_the_subject) && questioning_the_subject.length) {
        if (window.setMaximusChatSuggestions) {
          window.setMaximusChatSuggestions(questioning_the_subject);
        } else {
          // If chat script hasn't loaded/initialized yet, stash it on the container for pickup
          maximusApiResponse.dataset.suggestedQuestions = JSON.stringify(questioning_the_subject);
        }
      }

      // Update Maximus API Response with fade-in effect
      maximusApiResponse.innerHTML = contentHTML;
      maximusApiResponse.style.opacity = "0";

      // Smooth transition
      setTimeout(() => {
        if (maximusApiResponse) {
          maximusApiResponse.style.transition = "opacity 0.3s ease-in";
          maximusApiResponse.style.opacity = "1";
        }
      }, 50);

      // Hide the placeholder and show the API content
      if (contentPlaceholder) {
        contentPlaceholder.style.display = "none";
        contentPlaceholder.setAttribute("aria-busy", "false");
      }

      // Announce completion to screen readers
      announceToScreenReader("Summary loaded successfully");
    })
    .catch((error) => {
      stopPlaceholderAnimation();

      // Check if request was cancelled
      if (error.name === 'AbortError') {
        console.log('Summary request was cancelled');
        return;
      }

      console.error(error);

      // Display error with retry button
      const errorMessage = error.message || "Failed to fetch story summary.";

      if (maximusApiResponse) {
        // Create error container
        const errorContainer = document.createElement('div');
        errorContainer.className = 'maximus-error-container';

        // Create error message
        const errorPara = document.createElement('p');
        errorPara.className = 'text-danger';
        errorPara.textContent = errorMessage;

        // Create retry button
        const retryButton = document.createElement('button');
        retryButton.className = 'btn btn-sm btn-primary mt-2';
        retryButton.textContent = 'Retry';
        retryButton.setAttribute('aria-label', 'Retry loading summary');
        retryButton.addEventListener('click', () => {
          fetchAndRenderStorySummary(storyId);
        });

        // Assemble and insert
        errorContainer.appendChild(errorPara);
        errorContainer.appendChild(retryButton);
        maximusApiResponse.innerHTML = '';
        maximusApiResponse.appendChild(errorContainer);
      }

      if (contentPlaceholder) {
        contentPlaceholder.style.display = "none";
        contentPlaceholder.setAttribute("aria-busy", "false");
      }

      // Announce error to screen readers
      announceToScreenReader(`Error: ${errorMessage}`);
    })
    .finally(() => {
      maximusIsFetchingSummary = false; // Release lock
      maximusAbortController = null;
    });
}

// Helper function to escape HTML and prevent XSS
function escapeHtml(unsafe) {
  if (!unsafe) return '';
  return unsafe
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// Helper function to show empty summary message
function showEmptySummary(apiResponse, placeholder) {
  if (apiResponse) {
    apiResponse.innerHTML = "<p class='text-muted'>No summary available for this story.</p>";
  }
  if (placeholder) {
    placeholder.style.display = "none";
    placeholder.setAttribute("aria-busy", "false");
  }
}

// Helper function for screen reader announcements
function announceToScreenReader(message) {
  const liveRegion = document.getElementById("maximus-sr-announce") || createLiveRegion();
  liveRegion.textContent = message;
  // Clear after announcement
  setTimeout(() => {
    liveRegion.textContent = "";
  }, 1000);
}

function createLiveRegion() {
  const region = document.createElement("div");
  region.id = "maximus-sr-announce";
  region.setAttribute("role", "status");
  region.setAttribute("aria-live", "polite");
  region.setAttribute("aria-atomic", "true");
  region.className = "sr-only";
  document.body.appendChild(region);
  return region;
}

// Initialize refresh button with story ID
function initializeRefreshButton(storyId) {
  const refreshButton = document.getElementById('maximusRefreshButton');
  if (!refreshButton) return;

  // Remove any existing event listeners by cloning the button
  const newButton = refreshButton.cloneNode(true);
  refreshButton.parentNode.replaceChild(newButton, refreshButton);

  // Add new event listener
  newButton.addEventListener('click', () => {
    requestNewSummary(storyId);
  });

  // Update button state
  updateRefreshButton();
}

// Expose functions globally
window.requestNewSummary = requestNewSummary;
window.cancelSummaryRequest = cancelSummaryRequest;
window.initializeRefreshButton = initializeRefreshButton;