function updateProgressBar(progressValue) {
    const progressBar = document.getElementById('progressBar');
    if (progressBar) {
        progressBar.style.width = progressValue + '%';
        progressBar.setAttribute('aria-valuenow', progressValue);
    }
    
    if (progressValue >= 100) {
        // Hide the progress bar
        progressBar.parentNode.style.visibility = 'hidden';
        
        //progressBar.parentNode.remove();
    }
}

// Initialize progress bar to 0%
updateProgressBar(0);

const maximusText = document.getElementById('maximusText');
const maximusCooking = document.getElementById('maximusCooking');
const maximusInitialText = document.getElementById('maximusInitialText');
const maximusFinalMessage = document.getElementById('maximusFinalMessageTrue');

// Simulate gradual progress
let progress = 0;
const simulateProgress = () => {
    if (progress >= 25){
        maximusText.innerHTML = 'Maximus is getting some context behind this news...';
    } 
    if (progress >= 50){
        maximusText.innerHTML = 'Maximus is searching where you can get more information on the matter...';
    }
    if (progress >= 80){
        maximusText.innerHTML = 'Maximus is ready to display all the information he got!';
    }
    if (progress < 95) { 
        progress += 5;
        updateProgressBar(progress);
        setTimeout(simulateProgress, 800); // Timing
    }
};
simulateProgress();

fetch('/api/summarize_story', {
    method: 'GET',
})
.then(response => response.json()) // Parse JSON from the response
.then(data => {
    // First parse the 'response' property to convert it from a JSON string to an object
    const actualData = JSON.parse(data.response);

    const apiResponse = document.getElementById('apiResponse');
    updateProgressBar(100);

    // Clear previous content
    apiResponse.innerHTML = '';

    // Now that actualData is a proper object, loop through its keys
    for (const key in actualData) {
        // Create a new header element
        const header = document.createElement('h3');
        // Convert the key to a readable format and set it as the header text
        header.textContent = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

        // Create a new paragraph element for the content
        const paragraph = document.createElement('p');
        // Insert the text content
        paragraph.innerHTML = actualData[key];

        // Append the header and paragraph to the API response container
        apiResponse.appendChild(header);
        apiResponse.appendChild(paragraph);
    }

    // Clear the 'cooking' message
    maximusCooking.innerHTML = '';
    maximusInitialText.innerHTML = '';

    maximusFinalMessage.className = "mt-5";
})
.catch((error) => {
    const apiResponse = document.getElementById('apiResponse');
    updateProgressBar(100);
    maximusInitialText.innerHTML = '';
    maximusCooking.innerHTML = '';
    
    // Display the error
    apiResponse.innerHTML = `An error occurred, and therefore no further information could be retrieved.<br>${error.toString()}`;
});
