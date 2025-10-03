// Use a class selector instead of ID
const containers = document.getElementsByClassName('hwrap');

// Check if there are any selected elements
if (containers.length > 0) {
    // Loop through all elements with the 'ticker' class
    Array.from(containers).forEach((container) => {
        let scrollInterval;
        container.addEventListener('mouseover', () => {
          scrollInterval = setInterval(() => {
            container.scrollLeft += 2; // Scroll speed
          }, 10); // Interval
        });

        container.addEventListener('mouseout', () => {
          clearInterval(scrollInterval);
        });
    });
}

const home_containers = document.getElementsByClassName('hwrap-home');

// Check if there are any selected elements
if (home_containers.length > 0) {
    // Loop through all elements with the 'ticker' class
    Array.from(home_containers).forEach((container) => {
        let scrollInterval;
        container.addEventListener('mouseover', () => {
          scrollInterval = setInterval(() => {
            container.scrollLeft += 2; // Scroll speed
          }, 10); // Interval
        });

        container.addEventListener('mouseout', () => {
          clearInterval(scrollInterval);
        });
    });
}
