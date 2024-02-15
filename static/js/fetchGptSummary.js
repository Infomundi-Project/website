function updateProgressBar(progressValue) {
    const progressBar = document.getElementById('progressBar');
    progressBar.style.width = progressValue + '%';
    progressBar.setAttribute('aria-valuenow', progressValue);

    if (progressValue >= 100) {
        // Hide the progress bar
        //progressBar.parentNode.style.visibility = 'hidden';
        
        progressBar.parentNode.remove();
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
        maximusText.innerHTML = 'Maximus found where you can have more information about the subject...';
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
.then(response => response.json())
.then(data => {
    const apiResponse = document.getElementById('apiResponse');
    updateProgressBar(100);

    // Parse the JSON string inside the 'response' key
    const responseData = JSON.parse(data.response);

    // Clear previous content
    apiResponse.innerHTML = '';

    // Append a badge for Maximus
    //apiResponse.innerHTML += `<span class="badge text-bg-info me-1" data-bs-toggle="tooltip" data-bs-placement="bottom" data-bs-title="Maximus is Infomundi's powerful assistant."><i class="fa-solid fa-wand-magic-sparkles me-1"></i>Powered by Maximus</span>`;

    // Loop through each key in the responseData object
    for (const key in responseData) {
        // Create a new header element
        const header = document.createElement('h3');
        // Convert the key to a readable format and set it as the header text
        header.textContent = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

        // Create a new paragraph element for the content
        const paragraph = document.createElement('p');
        // Insert the text content
        paragraph.innerHTML = responseData[key];

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
    
    maximusText.innerHTML = 'I couldn\'t finish the request, and therefore no further information on this matter could be retrieved.';
});

