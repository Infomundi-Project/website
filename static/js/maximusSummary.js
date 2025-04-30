// Lock to prevent multiple requests
let maximusIsFetchingSummary = false;

const maximusBlurredText = document.getElementById("maximusSummaryBlurredText");
const maximusProgressBar = document.getElementById("maximusSummaryProgressBar");
const loremIpsum =
  `Lorem ipsum dolor sit amet, consectetur adipiscing elit. Maecenas fermentum lorem consequat diam tempor malesuada. Nunc id odio lorem. Duis quis cursus nisi. Curabitur cursus eget augue a rutrum. Maecenas vestibulum nunc id eros ultrices, id sollicitudin diam lacinia. Proin eget eros ultrices, vestibulum est et, vestibulum nisi. Vivamus erat odio, convallis nec efficitur dapibus, imperdiet sit amet libero. Donec sed molestie urna. Praesent pretium metus id augue tristique, eget elementum mi convallis. Nullam ex dui, scelerisque eget dui in, rutrum maximus diam. Donec elementum efficitur est, in imperdiet diam scelerisque eu. Mauris maximus risus mi, at pellentesque tellus congue ut. Morbi libero nulla, dapibus eget ex aliquam, rhoncus tincidunt leo. Cras tempor purus at mauris tempus posuere. Donec ultricies tellus risus, vel aliquam nulla tristique et. Morbi vehicula augue ut iaculis sodales.

Nullam auctor, enim nec luctus iaculis, urna orci posuere diam, eget aliquam sem magna et ex. Ut feugiat, mauris quis suscipit vulputate, ante quam porta dolor, ac eleifend neque risus non tellus. Vestibulum sit amet velit nibh. Etiam quis tortor id turpis condimentum tempor ut eu metus. Pellentesque in fermentum massa. Donec elit magna, dictum ut tellus ac, blandit fringilla magna. Sed pulvinar non mauris eget aliquet. Vivamus lectus nibh, porta sed leo in, lobortis sollicitudin erat. Nullam eu lorem vehicula, sodales massa vitae, tempus velit. Morbi at consequat ligula. Interdum et malesuada fames ac ante ipsum primis in faucibus. Vestibulum scelerisque libero in odio vulputate lacinia.`;

let maximusCurrentIndex = 0;
let maximusTotalCharacters = loremIpsum.replace(/\s+/g, "")
.length; // Exclude spaces

function resetAndPlayPlaceholder() {
  maximusBlurredText.textContent = ""; // Clear any existing text
  maximusCurrentIndex = 0;
  maximusProgressBar.style.width = "0%";
  maximusProgressBar.setAttribute("aria-valuenow", "0");

  function typeText() {
    if (maximusCurrentIndex < loremIpsum.length) {
      const currentChar = loremIpsum[maximusCurrentIndex];
      if (currentChar.trim()) {
        maximusBlurredText.textContent += currentChar;
        const progress = Math.min(
          (maximusBlurredText.textContent.replace(/\s+/g, "").length /
            maximusTotalCharacters) *
          100,
          100
        );
        maximusProgressBar.style.width = `${progress}%`;
        maximusProgressBar.setAttribute("aria-valuenow", progress.toFixed(0));
      }
      maximusCurrentIndex++;
      setTimeout(typeText, 0.07); // Time in ms
    }
  }

  typeText();
}

function fetchAndRenderStorySummary(storyId) {
  if (maximusIsFetchingSummary) return; // Prevent duplicate requests
  maximusIsFetchingSummary = true; // Set lock

  const contentPlaceholder = document.querySelector(
    ".maximus-summary-content-placeholder");
  const maximusApiResponse = document.querySelector(
    ".maximus-summary-api-response");

  // Reset: Show the placeholder and clear the response container
  contentPlaceholder.style.display = "flex";
  maximusApiResponse.innerHTML = "";

  resetAndPlayPlaceholder(); // Play loading animation

  fetch(`/api/story/summarize/${storyId}`)
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
      const responseData = data.response;

      if (!responseData) {
        maximusApiResponse.innerHTML =
          "<p>No summary available for this story.</p>";
        contentPlaceholder.style.display = "none"; // Hide placeholder
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
        maximusApiResponse.innerHTML =
          "<p>No summary available for this story.</p>";
        contentPlaceholder.style.display = "none"; // Hide placeholder
        return;
      }

      // Construct content dynamically
      let contentHTML = "";

      // Add "Addressed Topics"
      if (addressed_topics?.length) {
        contentHTML += `
                  <h4>Addressed Topics</h4>
                  <ul>${addressed_topics.map((topic) => `<li>${topic}</li>`).join("")}</ul>
                  <hr class="my-3">
              `;
      }

      // Add "Context Around"
      if (context_around?.length) {
        contentHTML += `
                  <h4>Context Around</h4>
                  <ul>${context_around.map((context) => `<li>${context}</li>`).join("")}</ul>
                  <hr class="my-3">
              `;
      }

      // Add "Methods for Inquiry"
      if (methods_for_inquiry?.length) {
        contentHTML += `
                  <h4>Methods for Investigation</h4>
                  <ul>${methods_for_inquiry.map((method) => `<li>${method}</li>`).join("")}</ul>
                  <hr class="my-3">
              `;
      }

      // Add "Questioning the Subject"
      if (questioning_the_subject?.length) {
        contentHTML += `
                  <h4>Questioning the Subject</h4>
                  <ul>${questioning_the_subject.map((question) => `<li>${question}</li>`).join("")}</ul>
              `;
      }

      // Update Maximus API Response
      maximusApiResponse.innerHTML = contentHTML;

      // Hide the placeholder and show the API content
      contentPlaceholder.style.display = "none";
    })
    .catch((error) => {
      console.error(error);

      // Display the error message from the API response
      maximusApiResponse.innerHTML = `<p>${error.message}</p>`;
      contentPlaceholder.style.display = "none"; // Hide placeholder
    })
    .finally(() => {
      maximusIsFetchingSummary = false; // Release lock
    });
}