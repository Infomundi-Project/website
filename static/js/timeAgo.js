// Function to calculate relative time
function timeAgo(dateString) {
    const originalDate = new Date(dateString.replace(/-/g, '/')); // Ensure cross-browser compatibility
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
        return `${differenceInDays} days ago`;
    }
}

// DOMContentLoaded event listener to update the dates on page load
document.addEventListener('DOMContentLoaded', function() {
    const dateElements = document.querySelectorAll('.date-info'); // Assuming your date spans have this class

    dateElements.forEach(function(element) {
        const originalDateString = element.textContent.trim(); // Extract the date string
        const relativeDateString = timeAgo(originalDateString); // Convert to relative format
        element.textContent = relativeDateString; // Update the element content
    });
});
