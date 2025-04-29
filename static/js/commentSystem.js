  function preciseTimeAgo(dateString) {
    const date = new Date(dateString + 'Z'); // Assumes UTC
    const now = new Date();
    const seconds = Math.floor((now - date) / 1000);
    const intervals = [{
      label: 'year',
      seconds: 31536000
    }, {
      label: 'month',
      seconds: 2592000
    }, {
      label: 'week',
      seconds: 604800
    }, {
      label: 'day',
      seconds: 86400
    }, {
      label: 'hour',
      seconds: 3600
    }, {
      label: 'minute',
      seconds: 60
    }, {
      label: 'second',
      seconds: 1
    }];
    for (const interval of intervals) {
      const count = Math.floor(seconds / interval.seconds);
      if (count >= 1) {
        return `${count} ${interval.label}${count > 1 ? 's' : ''} ago`;
      }
    }
    return 'just now';
  }

  const commentForm = document.getElementById('commentForm');
  const commentText = document.getElementById('commentText');
  const parentIdField = document.getElementById('parentId');
  const commentsList = document.getElementById('commentsList');
  const csrfToken = document.querySelector('meta[name="csrf-token"]')
    .getAttribute('content');

  let page = 1;
  let loading = false;
  let hasMore = true;

  let page_id = null;

  async function loadComments(reset = false, isScroll = false) {
    if (!window.page_id) return; // ← nothing to do until we have an ID
    if (loading) return;
    if (isScroll && !hasMore)
      return; // Only block if infinite scroll says no more

    loading = true;

    if (reset) {
      page = 1;
      commentsList.innerHTML = '';
      hasMore = true;
    }

    const sort = document.getElementById('sortSelect').value;
    const search = document.getElementById('searchInput').value;
    const infomundiCommentsCount = document.getElementById(
      'infomundiCommentsCount');

    const res = await fetch(
      `/api/comments/get/${page_id}?page=${page}&sort=${sort}&search=${search}`
    );
    const data = await res.json();

    // **refresh all “timeago” labels right away**
    updateTimeagoLabels();

    infomundiCommentsCount.innerHTML = data.total;

    data.comments.forEach(comment => renderComment(comment,
      commentsList));
    hasMore = data.has_more;
    page++;
    loading = false;
  }

  function renderComment(comment, container, level = 0, parentUser = null) {
    const div = document.createElement('div');
    div.className =
      'card bg-transparent border-0 border-start border-primary border-5 mb-3';
    div.dataset.id = comment.id;
    div.id = `comment-${comment.id}`;

    const repliesContainerId = `replies-${comment.id}`;
    const editedTag = comment.is_edited ? `
                        <span
                        class="d-inline-block text-muted ms-2 fst-italic small timeago"
                        data-timestamp="${comment.updated_at}Z"
                        title="${new Date(comment.updated_at + 'Z').toLocaleString()}">
                        (edited – ${preciseTimeAgo(comment.updated_at)})
                      </span>` : '';
    div.innerHTML = `
                        <div class="card-body inf-comments-card-body py-1 ps-3 pe-0">
                          <div class="d-flex align-items-start">
                            <a href="https://infomundi.net/id/${comment.user.id}" class="text-decoration-none text-reset"><img src="${comment.user.avatar_url}" class="rounded me-3 d-none d-md-block d-lg-block" alt="User Avatar" style="width: 3em; height: auto"></a>
                              <div class="w-100">
                                <div class="d-flex justify-content-between">
                                  <div>
                                    <a href="https://infomundi.net/id/${comment.user.id}" class="text-decoration-none text-reset fw-bold small notranslate">${comment.user.username}</a>
              ${comment.user.role !== 'user' ? `
                                    <span class="badge bg-primary" tabindex="0" data-bs-toggle="tooltip" data-bs-placement="top" title="${comment.user.role}"><i class="fa-solid fa-globe"></i></span>` : ''}
                                    <br>
              ${level > 0 && parentUser ? `
                                      <span class="text-muted small">Replying to 
                                        @<a href="#comment-${comment.parent_id}" class="reply-link text-decoration-none fw-bold">${parentUser.username}</a>, 
                                      </span>` : ''}
                                      <span
                                        class="d-inline-block text-muted small timeago"
                                        data-timestamp="${comment.created_at}Z"
                                        title="${new Date(comment.created_at + 'Z').toLocaleString()}">
                                        ${preciseTimeAgo(comment.created_at)}
                                      </span>
              ${editedTag}
            
                                    </div>
                                    <div class="dropdown">
                                      <button class="btn btn-sm btn-light-subtle" type="button" data-bs-toggle="dropdown">
                                        <i class="fa-solid fa-ellipsis-vertical mx-1"></i>
                                      </button>
                                      <ul class="dropdown-menu dropdown-menu-end">
                                        <li>
                                          <a class="dropdown-item edit-btn ${!window.isUserAuthenticated ? `disabled` : ''}" ${!window.isUserAuthenticated ? ` aria-disabled="true"` : ''} href="#">Edit</a>
                                        </li>
                                        <li>
                                          <a class="dropdown-item delete-btn text-danger ${!window.isUserAuthenticated ? `disabled` : ''}" ${!window.isUserAuthenticated ? ` aria-disabled="true"` : ''}" href="#">Delete</a>
                                        </li>
                                      </ul>
                                    </div>
                                  </div>

                                  <p class="my-3 text-wrap" id="comment-content-${comment.id}" style="word-wrap: break-word; overflow-wrap: break-word; white-space: pre-wrap; word-break: break-word;">${comment.content}</p>

                                  <div class="d-flex align-items-center mt-3">
                                    <button class="btn btn-sm btn-outline-primary like-btn me-2"${!window.isUserAuthenticated ? ` disabled` : ''}>
                                      <i class="fa-solid fa-thumbs-up me-1"></i><span class="badge bg-primary">${comment.likes}</span>
                                    </button>
                                    <button class="btn btn-sm btn-outline-danger dislike-btn me-2"${!window.isUserAuthenticated ? ` disabled` : ''}>
                                      <i class="fa-solid fa-thumbs-down me-1"></i><span class="badge bg-danger">${comment.dislikes}</span>
                                    </button>
                                    <button class="btn btn-sm btn-outline-secondary reply-btn">
                                      <i class="fa-solid fa-reply"></i>
                                    </button>
                                  </div>
                                  <div id="${repliesContainerId}" class="mt-4" style="margin-left: -50px;"></div>
                                  <div class="reply-form-container mt-3"></div>
                                </div>
                              </div>
                            </div>
  `;


    if (comment.is_flagged) {
      // 1) mark the card
      div.classList.add('flagged');

      // 2) find the body
      const body = div.querySelector('.inf-comments-card-body');

      // 3) wrap all existing children in a blur-able container
      const wrapper = document.createElement('div');
      wrapper.className = 'comment-content-wrapper flagged-blur';
      while (body.firstChild) {
        wrapper.appendChild(body.firstChild);
      }
      body.appendChild(wrapper);

      // 4) build the overlay
      const overlay = document.createElement('div');
      overlay.className = 'flagged-overlay';
      overlay.innerHTML = `
        This comment was flagged by our automated systems.
        <button class="btn btn-sm btn-light">Show</button>
      `;

      // 5) on click, unblur & remove overlay
      overlay.addEventListener('click', () => {
        wrapper.classList.remove('flagged-blur');
        overlay.remove();
      });

      // 6) append overlay *after* the wrapper
      body.appendChild(overlay);
    }




    // Attach actions
    const likeBtn = div.querySelector('.like-btn');
    const dislikeBtn = div.querySelector('.dislike-btn');
    const replyBtn = div.querySelector('.reply-btn');
    const editBtn = div.querySelector('.edit-btn');
    const deleteBtn = div.querySelector('.delete-btn');
    likeBtn.addEventListener('click', () => likeComment(comment.id));
    dislikeBtn.addEventListener('click', () => dislikeComment(comment.id));


    replyBtn.addEventListener('click', (e) => {
      e.preventDefault();
      // 'div' is the card for this comment
      showReplyForm(div, comment.id);
    });


    editBtn.addEventListener('click', (e) => {
      e.preventDefault();
      editComment(comment.id);
    });
    deleteBtn.addEventListener('click', (e) => {
      e.preventDefault();
      deleteComment(comment.id);
    });
    container.appendChild(div);


    // === BEGIN: collapse/expand logic ===
    if (comment.replies && comment.replies.length) {
      // 1) Create a <div> to hold all the child replies, and give it .collapse
      const repliesContainer = document.createElement('div');
      repliesContainer.id = `replies-${comment.id}`;
      repliesContainer.className = 'collapse';
      div.querySelector('.inf-comments-card-body').appendChild(
        repliesContainer);

      // 2) Create the toggle button
      const toggleBtn = document.createElement('button');
      toggleBtn.type = 'button';
      toggleBtn.className = 'btn btn-sm btn-link p-0 mb-2';
      toggleBtn.setAttribute('data-bs-toggle', 'collapse');
      toggleBtn.setAttribute('data-bs-target', `#${repliesContainer.id}`);
      toggleBtn.setAttribute('aria-expanded', 'false');
      toggleBtn.setAttribute('aria-controls', repliesContainer.id);
      toggleBtn.textContent = `Show replies (${comment.replies.length})`;

      // 3) Hook into Bootstrap’s events to swap the text
      repliesContainer.addEventListener('show.bs.collapse', () => {
        toggleBtn.textContent =
          `Hide replies (${comment.replies.length})`;
      });
      repliesContainer.addEventListener('hide.bs.collapse', () => {
        toggleBtn.textContent =
          `Show replies (${comment.replies.length})`;
      });

      // 4) Insert the toggle button *right before* the replies container
      repliesContainer.before(toggleBtn);

      // 5) Finally, render each reply *into* that container, nesting level+1:
      comment.replies.forEach(child => {
        renderComment(child, repliesContainer, level + 1, comment
          .user);
      });
    }
    // === END: collapse/expand logic ===

    initializeTooltips();
  }
  async function handleCommentSubmit(e) {
    e.preventDefault();
    const content = commentText.value.trim();
    const parent_id = parentIdField.value || null;
    if (!content) return;
    const res = await fetch('/api/comments', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      },
      body: JSON.stringify({
        content,
        parent_id,
        page_id
      })
    });
    if (res.ok) {
      commentText.value = '';
      parentIdField.value = '';
      await loadComments(true);
    }
  }
  commentForm.addEventListener('submit', handleCommentSubmit);
  async function likeComment(id) {
    // 1) Hit the API
    const res = await fetch(`/api/comments/${id}/like`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      }
    });
    if (!res.ok) return;
    const {
      likes
    } = await res.json(); // have your API return the new like count

    // 2) Find the button’s badge and update it
    const commentDiv = document.getElementById(`comment-${id}`);
    const badge = commentDiv.querySelector('.like-btn .badge');
    badge.textContent = likes;

    // 3) (Optional) briefly highlight it so they see feedback immediately
    commentDiv.classList.add('bg-highlight');
    setTimeout(() => commentDiv.classList.remove('bg-highlight'), 1500);
  }

  async function dislikeComment(id) {
    // 1) Call the API
    const res = await fetch(`/api/comments/${id}/dislike`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      }
    });
    if (!res.ok) return; // bail if something’s wrong
    const {
      dislikes
    } = await res.json(); // expect { dislikes: <newCount> }

    // 2) Update the badge in-place
    const commentDiv = document.getElementById(`comment-${id}`);
    const badge = commentDiv.querySelector('.dislike-btn .badge');
    badge.textContent = dislikes;

    // 3) Give a quick highlight for feedback
    commentDiv.classList.add('bg-highlight');
    setTimeout(() => commentDiv.classList.remove('bg-highlight'), 1500);
  }



  function editComment(id) {
    const contentDiv = document.getElementById(`comment-content-${id}`);
    const originalText = contentDiv.innerText.trim();

    // 1) Replace the <p> with a <textarea> + buttons
    const textarea = document.createElement('textarea');
    textarea.className = 'form-control mb-2';
    textarea.value = originalText;
    const saveBtn = document.createElement('button');
    saveBtn.className = 'btn btn-sm btn-success me-2';
    saveBtn.textContent = 'Save';
    const cancelBtn = document.createElement('button');
    cancelBtn.className = 'btn btn-sm btn-secondary';
    cancelBtn.textContent = 'Cancel';

    contentDiv.replaceWith(textarea);
    textarea.after(saveBtn, cancelBtn);

    // 2) Wire up “Save”
    saveBtn.onclick = async () => {
      const updatedText = textarea.value.trim();
      if (!updatedText) return;

      const res = await fetch(`/api/comments/${id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
          content: updatedText
        })
      });
      if (!res.ok) return; // error handling as desired
      const data = await res
        .json(); // expect { content, updated_at }

      // 3) Rebuild the paragraph with new content
      const newP = document.createElement('p');
      newP.id = `comment-content-${id}`;
      newP.className = contentDiv
        .className; // carry over your styling
      newP.style = contentDiv.getAttribute('style');
      newP.textContent = data.content;

      // 4) Swap textarea out for the new <p>
      textarea.replaceWith(newP);
      saveBtn.remove();
      cancelBtn.remove();

      // 5) Update the “(edited … ago)” tag or insert it if missing
      const body = document.querySelector(
        `#comment-${id} .inf-comments-card-body .d-flex > div`
      );
      let editedTag = body.querySelector('.edited-tag');
      if (!editedTag) {
        editedTag = document.createElement('span');
        editedTag.className =
          'd-inline-block text-muted ms-2 fst-italic small edited-tag';
        body.appendChild(editedTag);
      }
      editedTag.setAttribute('title', new Date(data.updated_at +
        'Z').toLocaleString());
      editedTag.textContent =
        `(edited – ${preciseTimeAgo(data.updated_at)})`;

      // 6) Give a quick visual cue
      const commentDiv = document.getElementById(`comment-${id}`);
      commentDiv.classList.add('highlight-border');
      setTimeout(() => commentDiv.classList.remove(
        'highlight-border'), 2000);
    };

    // 7) Wire up “Cancel” to restore original
    cancelBtn.onclick = () => {
      textarea.replaceWith(contentDiv);
      saveBtn.remove();
      cancelBtn.remove();
    };
  }

  async function deleteComment(id) {
    if (confirm("Are you sure you want to delete this comment?")) {
      await fetch(`/api/comments/${id}`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        }
      });
      loadComments(true);
    }
  }

  function infCommentSearchDebounce(func, delay) {
    let timeoutId;
    return (...args) => {
      clearTimeout(timeoutId);
      timeoutId = setTimeout(() => func.apply(this, args), delay);
    };
  }

  const debouncedLoadComments = infCommentSearchDebounce(() => loadComments(
    true), 300); // 300ms delay
  document.getElementById('searchInput').addEventListener('input',
    debouncedLoadComments);


  const sortSelect = document.getElementById('sortSelect');
  if (sortSelect) {
    sortSelect.addEventListener('change', () => loadComments(true));
  }

  window.addEventListener('scroll', () => {
    if (window.innerHeight + window.scrollY >= document.body
      .offsetHeight - 500) {
      loadComments(false, true);
    }
  });


  class InfomundiComments extends HTMLElement {
    static get observedAttributes() {
      return ['page_id'];
    }

    constructor() {
      super();
    }

    connectedCallback() {
      // Initial render on first connection
      this.handlePageIdChange(this.getAttribute('page_id'));
    }

    attributeChangedCallback(name, oldValue, newValue) {
      if (name === 'page_id' && newValue && newValue !== oldValue) {
        this.handlePageIdChange(newValue);
      }
    }

    handlePageIdChange(rawId) {
      if (!rawId) {
        console.error(
          "No page_id specified for <infomundi-comments>");
        return;
      }

      // URL-safe Base64 encode
      const base64Id = btoa(rawId)
        .replace(/\+/g, '-')
        .replace(/\//g, '_')
        .replace(/=+$/, '');

      // Expose globally for fetch logic
      page_id = base64Id;
      window.page_id = base64Id;

      // Reset infinite-scroll state and clear UI
      page = 1;
      hasMore = true;
      commentsList.innerHTML = '';

      // Fetch comments for the new page_id
      loadComments(true);
    }
  }

  customElements.define('infomundi-comments', InfomundiComments);


  function flattenReplies(replies = []) {
    return replies.reduce((all, reply) => {
      all.push(reply);
      if (reply.replies && reply.replies.length) {
        // recurse into grandchildren
        all.push(...flattenReplies(reply.replies));
      }
      return all;
    }, []);
  }


  document.addEventListener('click', (e) => {
    if (e.target.classList.contains('reply-link')) {
      e.preventDefault();
      const targetId = e.target.getAttribute('href').substring(
        1); // remove #
      const target = document.getElementById(targetId);
      if (target) {
        target.scrollIntoView({
          behavior: 'smooth',
          block: 'center'
        });

        target.classList.remove('border-primary', 'border');
        target.classList.add('border-info',
          'border'); // visual effect

        setTimeout(() => {
          target.classList.add('border-primary',
            'border');
          target.classList.remove('border-info',
            'border');
        }, 2500); // remove effect after 2.5s
      }
    }
  });

  function showReplyForm(commentDiv, parentId) {
    // remove any existing reply forms
    document.querySelectorAll('.reply-form-container').forEach(c => c
      .innerHTML = '');

    const container = commentDiv.querySelector('.reply-form-container');
    container.innerHTML = `
      <form class="reply-form">
        <div class="mb-2">
          <textarea class="form-control reply-text" rows="3"
                    placeholder="Write a reply..."></textarea>
        </div>
        <button type="submit" class="btn btn-sm btn-primary me-2">Reply</button>
        <button type="button" class="btn btn-sm btn-secondary cancel-reply">Cancel</button>
      </form>
    `;

    const form = container.querySelector('form');
    const textarea = form.querySelector('.reply-text');
    const cancel = form.querySelector('.cancel-reply');

    // focus
    textarea.focus();

    // submit -> POST & reload
    form.addEventListener('submit', async e => {
      e.preventDefault();
      const content = textarea.value.trim();
      if (!content) return;
      await fetch('/api/comments', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
          content,
          parent_id: parentId,
          page_id
        })
      });
      await loadComments(true);
    });

    // cancel -> just clear
    cancel.addEventListener('click', () => container.innerHTML = '');
  }

  function updateTimeagoLabels() {
    document.querySelectorAll('.timeago').forEach(el => {
      const ts = el.getAttribute('data-timestamp');
      // strip trailing Z for our utility, if needed
      const base = ts.endsWith('Z') ? ts.slice(0, -1) : ts;
      el.textContent = preciseTimeAgo(base);
    });
  }

  // Update every 60 seconds
  setInterval(updateTimeagoLabels, 60 * 1000);