document.addEventListener('DOMContentLoaded', (event) => {
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
        } else if (this.classList.contains('comments-btn')) {
          document.cookie = "clicked=" + cardId + "-" + newsCategory + ";path=/";
          loadComments();
        } else {
          // Preview button clicked
          updateCardWithPreview(card);
        }
      });
    });
  });

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
