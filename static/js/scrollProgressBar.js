// Create the progress bar element and append it to the body
let progressBar = document.createElement('div');
progressBar.id = 'scrollProgressBar';
document.body.appendChild(progressBar);

// Function to update the progress bar width
function updateProgressBar() {
  const windowHeight = document.documentElement.scrollHeight - document
    .documentElement.clientHeight;
  const currentScroll = window.scrollY;
  const scrolled = (currentScroll / windowHeight) * 100;
  progressBar.style.width = scrolled + '%';
}

// Event listener for scroll events
window.addEventListener('scroll', updateProgressBar);

// Initial update in case of reloads at a scrolled position
updateProgressBar();