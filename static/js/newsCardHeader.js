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
          fetch(`/api/comments?id=${cardId}&category=${newsCategory}`)
            .then(response => response.json())
            .then(data => {
                // Assume 'data' is an array of comment objects
                const offcanvasBody = document.querySelector('#offcanvasWithBothOptions .offcanvas-body');
                
                //const commentsContainer = document.querySelector('#commentsContainer');
                offcanvasBody.innerHTML = `<form action="{{ url_for('api.add_comment') }}" method="post" onsubmit="return validateForm()">
    <div class="form-group">
      <label for="name" class="form-label"><i class="fa-solid fa-user me-1"></i>Username</label>
      {% if user.is_authenticated %}
      <input class="form-control" type="text" value="{{ user.username }}" aria-label="User is logged in" readonly>
      {% else %}
      <input type="text" id="name" name="name" class="form-control" aria-describedby="nameHelp" maxlength="30">
      <div id="nameHelp" class="form-text text-secondary"><i class="fa-solid fa-circle-info me-1"></i>We'll generate one for you if you prefer not to choose a name and leave this field blank.</div>
      {% endif %}
    </div>
    <div class="form-group">
      <label for="comment" class="form-label"><i class="fa-solid fa-message me-1"></i>Comment *</label>
      <textarea id="comment" name="comment" rows="4" class="form-control" maxlength="300" aria-describedby="commentHelp" required></textarea>
      <div id="commentHelp" class="form-text text-secondary"><i class="fa-solid fa-circle-info me-1"></i>Your comment must not exceed 300 characters.</div>
    </div>
    <input type="hidden" id="id" name="id" value="{{ id }}">
    <input type="hidden" id="category" name="category" value="{{ category }}">
    <div class="cf-turnstile" data-sitekey="0x4AAAAAAAN8p0y-GxgH2k2X"></div>
    <button type="submit" class="btn btn-outline-secondary mb-5" id="cooldown-button" disabled>Comment</button>
  </form>`; // Clear existing content

                // Check if data is an array and has at least one comment
                if (Array.isArray(data) && data.length > 0) {
                    data.forEach(comment => {
                        const commentElement = document.createElement('div');
                        commentElement.classList.add('comment');

                        // Comment identification
                        let identification = '';
                        if (comment.is_admin) identification += '[Admin] ';
                        if (comment.random_name) identification += '[Random Name] ';
                        if (!comment.is_logged_in) identification += '[Guest] ';

                        // Comment content
                        commentElement.innerHTML = `
                            <p class="mt-3"><strong>${identification}${comment.name}</strong>: ${comment.text}</p>
                            <a href="${comment.link}" target="_blank">View Comment</a>
                        `;
                        offcanvasBody.appendChild(commentElement);
                    });

                } else {
                    // Display a message or just show the comment form if there are no comments
                    offcanvasBody.innerHTML = `<p>No comments yet. Be the first to comment!</p>
                    <form action="{{ url_for('api.add_comment') }}" method="post" onsubmit="return validateForm()">
    <div class="form-group">
      <label for="name" class="form-label"><i class="fa-solid fa-user me-1"></i>Username</label>
      {% if user.is_authenticated %}
      <input class="form-control" type="text" value="{{ user.username }}" aria-label="User is logged in" readonly>
      {% else %}
      <input type="text" id="name" name="name" class="form-control" aria-describedby="nameHelp" maxlength="30">
      <div id="nameHelp" class="form-text text-secondary"><i class="fa-solid fa-circle-info me-1"></i>We'll generate one for you if you prefer not to choose a name and leave this field blank.</div>
      {% endif %}
    </div>
    <div class="form-group">
      <label for="comment" class="form-label"><i class="fa-solid fa-message me-1"></i>Comment *</label>
      <textarea id="comment" name="comment" rows="4" class="form-control" maxlength="300" aria-describedby="commentHelp" required></textarea>
      <div id="commentHelp" class="form-text text-secondary"><i class="fa-solid fa-circle-info me-1"></i>Your comment must not exceed 300 characters.</div>
    </div>
    <input type="hidden" id="id" name="id" value="{{ id }}">
    <input type="hidden" id="category" name="category" value="{{ category }}">
    <div class="cf-turnstile" data-sitekey="0x4AAAAAAAN8p0y-GxgH2k2X"></div>
    <button type="submit" class="btn btn-outline-secondary mb-5" id="cooldown-button" disabled>Comment</button>
  </form>`;
                }

                document.cookie = "clicked=" + cardId + ";path=/";
            })
            .catch(error => console.error('Error fetching comments:', error));
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
    // Hide title and publisher, show description
    card.querySelector('.card-title').style.display = 'none';
    card.querySelector('.card-text').style.display = 'none';

    const cardBody = card.querySelector('.card-body');
    if (!cardBody.querySelector('.description-text')) {
      cardBody.innerHTML += `<p class="description-text">${data.description}</p>`;
    }
  }

  function updateCardWithPreview(card) {
    // Show title and publisher, hide description
    card.querySelector('.card-title').style.display = 'block';
    card.querySelector('.card-text').style.display = 'block';

    const cardBody = card.querySelector('.card-body');
    const descriptionElement = cardBody.querySelector('.description-text');
    if (descriptionElement) {
      descriptionElement.remove();
    }
  }