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
  const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
  
  let page = 1;
  let loading = false;
  let hasMore = true;
  async function loadComments(reset = false, isScroll = false) {
    if (loading) return;
    if (isScroll && !hasMore) return; // Only block if infinite scroll says no more

    loading = true;

    if (reset) {
      page = 1;
      commentsList.innerHTML = '';
      hasMore = true;
    }

    const sort = document.getElementById('sortSelect').value;
    const search = document.getElementById('searchInput').value;
    const infomundiCommentsCount = document.getElementById('infomundiCommentsCount');

    const res = await fetch(`/api/comments/get/${page_id}?page=${page}&sort=${sort}&search=${search}`);
    const data = await res.json();

    infomundiCommentsCount.innerHTML = data.total;

    data.comments.forEach(comment => renderComment(comment, commentsList));
    hasMore = data.has_more;
    page++;
    loading = false;
  }


  function renderComment(comment, container, level = 0, parentUser = null) {
    const div = document.createElement('div');
    div.className = 'card mb-3 shadow-sm' + (level ? ' border-0 border-start shadow-none ps-3' : '');
    div.dataset.id = comment.id;
    const repliesContainerId = `replies-${comment.id}`;
    const editedTag = comment.is_edited ? `
                        <span class="d-inline-block text-muted ms-2 fst-italic" tabindex="0" data-bs-toggle="tooltip" data-bs-placement="top" title="${new Date(comment.updated_at + 'Z').toLocaleString()}">(edited - ${preciseTimeAgo(comment.updated_at)})</span>` : '';
    div.innerHTML = `
    
                        <div class="card-body">
                          <div class="d-flex align-items-start">
                            <img src="${comment.user.avatar_url}" class="rounded me-3" alt="User Avatar" width="48" height="48">
                              <div class="w-100">
                                <div class="d-flex justify-content-between">
                                  <div>
                                    ${comment.user ? `<a href="https://infomundi.net/id/${comment.user.id}" class="text-decoration-none text-reset">` : ''}<strong>${comment.user.username || 'Anonymous'}</strong>${comment.user ? `</a>` : ''}
              ${comment.user.role !== 'user' ? `
                                    <span class="badge bg-primary ms-2">${comment.user.role}</span>` : ''}
                                    <br>
              ${level > 0 && parentUser ? `
                                      <small class="text-muted">Replying to 
                                        <strong>${parentUser ? `<a href="https://infomundi.net/id/${parentUser.id}" class="text-decoration-none text-reset">` : ''}@${parentUser.username}${parentUser ? `</a>` : ''}</strong>, 
                                      </small>` : ''}
                                      <small class="d-inline-block text-muted" tabindex="0" data-bs-toggle="tooltip" data-bs-placement="right" title="${new Date(comment.created_at + 'Z').toLocaleString()}">${preciseTimeAgo(comment.created_at)}</small>
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
                                  <p class="my-3 text-wrap" id="comment-content-${comment.id}" style="word-wrap: break-word; overflow-wrap: break-word; white-space: pre-wrap; word-break: break-word;">
            ${comment.content}
          </p>
                                  <div class="d-flex align-items-center mt-3">
                                    <button class="btn btn-sm btn-outline-primary like-btn me-2"${!window.isUserAuthenticated ? ` disabled` : ''}>
                                      <i class="fa-solid fa-thumbs-up"></i>
                                      <span class="badge bg-primary">${comment.likes}</span>
                                    </button>
                                    <button class="btn btn-sm btn-outline-danger dislike-btn me-2"${!window.isUserAuthenticated ? ` disabled` : ''}>
                                      <i class="fa-solid fa-thumbs-down"></i>
                                      <span class="badge bg-danger">${comment.dislikes}</span>
                                    </button>
                                    <button class="btn btn-sm btn-outline-secondary reply-btn">
                                      <i class="fa-solid fa-reply"></i> Reply
            
                                    </button>
                                  </div>
                                  <div id="${repliesContainerId}" class="mt-4"></div>
                                  <div class="reply-form-container mt-3"></div>
                                </div>
                              </div>
                            </div>
  `;
    // Attach actions
    const likeBtn = div.querySelector('.like-btn');
    const dislikeBtn = div.querySelector('.dislike-btn');
    const replyBtn = div.querySelector('.reply-btn');
    const editBtn = div.querySelector('.edit-btn');
    const deleteBtn = div.querySelector('.delete-btn');
    likeBtn.addEventListener('click', () => likeComment(comment.id));
    dislikeBtn.addEventListener('click', () => dislikeComment(comment.id));
    replyBtn.addEventListener('click', () => replyTo(comment.id));
    editBtn.addEventListener('click', (e) => {
      e.preventDefault();
      editComment(comment.id);
    });
    deleteBtn.addEventListener('click', (e) => {
      e.preventDefault();
      deleteComment(comment.id);
    });
    container.appendChild(div);
    // Render replies recursively
    if (comment.replies && comment.replies.length) {
      const repliesContainer = div.querySelector(`#${repliesContainerId}`);
      comment.replies.forEach(reply => renderComment(reply, repliesContainer, level + 1, comment.user));
    }
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
    await fetch(`/api/comments/${id}/like`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      }
    });
    loadComments(true);
  }
  async function dislikeComment(id) {
    await fetch(`/api/comments/${id}/dislike`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      }
    });
    loadComments(true);
  }

  function replyTo(id) {
    parentIdField.value = id;
    commentText.focus();
  }

  function editComment(id) {
    const contentDiv = document.getElementById(`comment-content-${id}`);
    const originalText = contentDiv.innerText.trim();
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
    saveBtn.onclick = async () => {
      const updatedText = textarea.value.trim();
      if (!updatedText) return;
      await fetch(`/api/comments/${id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
          content: updatedText
        })
      });
      loadComments(true);
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

  const debouncedLoadComments = infCommentSearchDebounce(() => loadComments(true), 300); // 300ms delay
  document.getElementById('searchInput').addEventListener('input', debouncedLoadComments);


  const sortSelect = document.getElementById('sortSelect');
  if (sortSelect) {
    sortSelect.addEventListener('change', () => loadComments(true));
  }

  window.addEventListener('scroll', () => {
    if (window.innerHeight + window.scrollY >= document.body.offsetHeight - 500) {
      loadComments(false, true);
    }
  });


  class InfomundiComments extends HTMLElement {
    constructor() {
      super();
    }

    connectedCallback() {
      const rawId = this.getAttribute('page_id');
      if (!rawId) {
        console.error("No page_id specified for <infomundi-comments>");
        return;
      }

      // URL-safe Base64 encode
      const base64Id = btoa(rawId)
        .replace(/\+/g, '-')
        .replace(/\//g, '_')
        .replace(/=+$/, '');

      this.renderCommentSection(base64Id);
    }

    renderCommentSection(page_id) {
      // Expose globally
      window.page_id = page_id;

      loadComments(true);
    }
  }

  customElements.define('infomundi-comments', InfomundiComments);