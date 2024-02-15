const container = document.getElementById('ticker');

if (container !== null) {
    let scrollInterval;
    container.addEventListener('mouseover', () => {
      scrollInterval = setInterval(() => {
        container.scrollLeft += 2; // Scroll speed
      }, 10); // Interval
    });

    container.addEventListener('mouseout', () => {
      clearInterval(scrollInterval);
    });
} 