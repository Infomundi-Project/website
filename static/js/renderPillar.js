let middleSectionCount = 1;

function addMiddleSection() {
  // Select both pillar containers
  const pillars = document.querySelectorAll('.pillar-container');
  
  pillars.forEach((pillar, index) => {
    const pillarMiddle = document.createElement('img');
    pillarMiddle.src = 'https://infomundi.net/static/img/illustrations/pillar-middle2.webp';
    pillarMiddle.alt = 'Middle of the Pillar';
    pillarMiddle.classList.add('pillar-middle');

    // Apply flipped class to every other section for alternating effect
    if (middleSectionCount % 2 !== 0) {
      pillarMiddle.classList.add('flipped');
    }

    // Insert the new middle image before the base of the pillar
    pillar.insertBefore(pillarMiddle, pillar.querySelector('.pillar-bottom'));
  });

  middleSectionCount++; // Increment counter after adding to both pillars
}

function initializePillar(initialCount = 100) {
  for (let i = 0; i < initialCount; i++) {
    addMiddleSection();
  }
}

// Event listener for infinite scroll
window.addEventListener('scroll', () => {
  const bottomOffset = 300;
  const scrollableHeight = document.documentElement.scrollHeight - window.innerHeight;
  const currentScroll = window.scrollY;

  if (scrollableHeight - currentScroll <= bottomOffset) {
    addMiddleSection();
  }
});

// Initialize the pillar on page load with an initial count of middle sections
window.addEventListener('DOMContentLoaded', () => initializePillar(100));
