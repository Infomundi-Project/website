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

  let page_id = null;
  let commentType = null;

  function hasUnsavedText() {
    // grab the main textarea on the fly
    const mainEl = document.getElementById('commentText');
    const mainText = mainEl && mainEl.value.trim().length > 0;

    const anyReplyText = Array.from(document.querySelectorAll('.reply-text'))
      .some(t => t.value.trim().length > 0);

    return mainText || anyReplyText;
  }

  async function loadComments(reset = false, isScroll = false) {
    if (!window.page_id) return;
    if (loading) return;
    if (isScroll && !hasMore) return;

    loading = true;

    if (reset) {
      page = 1;
      commentsList.innerHTML = '';
      hasMore = true;
    }

    const sortEl = document.getElementById('sortSelect');
    const searchEl = document.getElementById('searchInput');
    if (!sortEl || !searchEl) {
      loading = false;
      return;
    }

    const sort = sortEl.value;
    const search = searchEl.value.trim();

    const res = await fetch(
      `/api/comments/get/${page_id}?page=${page}&sort=${sort}&search=${encodeURIComponent(search)}`
    );
    const data = await res.json();

    // If resetting and no comments came back, show a “no results” message
    if (reset && data.comments.length === 0) {
      commentsList.innerHTML = `
        <div class="text-center text-muted my-5">
          <i class="fa-solid fa-comment-slash fa-xl mb-3"></i>
          <p>No comments found${search ? ` for "<strong>${search}</strong>"` : '.'}</p>
        </div>
      `;
      // no more pages, disable further scrolling
      hasMore = false;
      infomundiCommentsCount.innerHTML = data.total;
      loading = false;
      return;
    }

    // otherwise, render like usual
    updateTimeagoLabels();
    infomundiCommentsCount.innerHTML = data.total;
    data.comments.forEach(comment => renderComment(comment, commentsList));
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
                        class="d-inline-block edited-tag text-muted ms-2 fst-italic small timeago"
                        data-timestamp="${comment.updated_at}Z"
                        title="${new Date(comment.updated_at + 'Z').toLocaleString()}">
                        (edited – ${preciseTimeAgo(comment.updated_at)})
                      </span>` : '';
    div.innerHTML = `
                        <div class="card-body inf-comments-card-body py-1 ps-3 pe-0">
                          <div class="d-flex align-items-start">
                            <a href="/id/${comment.user.id}" class="text-decoration-none text-reset"><img src="${comment.user.avatar_url}" class="rounded me-3 d-none d-md-block d-lg-block" alt="User Avatar" style="width: 3em; height: auto"></a>
                              <div class="w-100">
                                <div class="d-flex justify-content-between">
                                  <div>
                                      <ul class="list-inline mb-1">
                                        <li class="list-inline-item fw-bold notranslate me-1"><a class="text-reset" href="/id/${comment.user.id}">${comment.user.display_name ? comment.user.display_name : comment.user.username}</a></li>
                                    
                                        <li class="list-inline-item text-muted small notranslate me-1" title="Username">@${comment.user.username}</li>

                ${comment.user.role !== 'user' ? `
                                      <li class="list-inline-item"><span class="badge bg-dark border" tabindex="0" data-bs-toggle="tooltip" data-bs-placement="top" title="${comment.user.role}"><i class="fa-solid fa-globe"></i></span>` : ''}</li>
                                      </ul>
              ${level > 0 && parentUser ? `
                                      <span class="text-muted small">Replying to 
                                        @<a href="#comment-${comment.parent_id}" class="reply-link text-decoration-none notranslate fw-bold">${parentUser.username}</a>, 
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
                                    <button class="btn btn-sm border like-btn me-2"${!window.isUserAuthenticated ? ` disabled` : ''}>
                                      <i class="fa-regular fa-thumbs-up me-1"></i><span class="like-count">${comment.likes}</span>
                                    </button>
                                    <button class="btn btn-sm border dislike-btn me-2"${!window.isUserAuthenticated ? ` disabled` : ''}>
                                      <i class="fa-regular fa-thumbs-down me-1"></i><span class="dislike-count">${comment.dislikes}</span>
                                    </button>
                                    <button class="btn btn-sm border reply-btn">
                                      <i class="fa-solid fa-reply"></i>
                                    </button>
                                  </div>
                                  <div class="mt-4 reply-wrapper" style="margin-left: -50px;"></div>
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
      overlay.classList.add('flagged-overlay', 'rounded-end');
      overlay.innerHTML = `
        This comment was flagged by Infomundi's automated systems.
        <button class="btn btn-sm btn-light show-flagged-btn">Show</button>
      `;

      // 5) wire up the Show button to ask for confirmation first
      const btn = overlay.querySelector('.show-flagged-btn');
      btn.addEventListener('click', (e) => {
        e.stopPropagation(); // don’t let the click bubble up if you had other listeners
        const really = window.confirm('Are you sure you want to view this comment?');
        if (really) {
          wrapper.classList.remove('flagged-blur');
          overlay.remove();
        }
        // if they cancel, we do nothing—still blurred
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
      toggleBtn.className = 'btn btn-sm border mt-3';
      toggleBtn.setAttribute('data-bs-toggle', 'collapse');
      toggleBtn.setAttribute('data-bs-target', `#${repliesContainer.id}`);
      toggleBtn.setAttribute('aria-expanded', 'false');
      toggleBtn.setAttribute('aria-controls', repliesContainer.id);
      toggleBtn.innerHTML = `<i class="fa-solid fa-share fa-flip-vertical me-1"></i>Replies<span class="badge text-bg-danger ms-3" id="infomundiCommentsCount">${comment.replies.length}</span>`;

      // 3) Hook into Bootstrap’s events to swap the text
      repliesContainer.addEventListener('show.bs.collapse', () => {
        toggleBtn.classList.replace("mt-3", "mb-2");
        toggleBtn.textContent =
          `Hide replies`;
      });
      repliesContainer.addEventListener('hide.bs.collapse', () => {
        toggleBtn.classList.replace("mb-2", "mt-3");
        toggleBtn.innerHTML =
          `<i class="fa-solid fa-share fa-flip-vertical me-1"></i>Replies<span class="badge text-bg-danger ms-3" id="infomundiCommentsCount">${comment.replies.length}</span>`;
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
    const form = e.currentTarget;
    const textarea = form.querySelector('#commentText');
    const parentId = form.querySelector('#parentId').value || null;
    const submitBtn = form.querySelector('button[type="submit"]');
    const originalHTML = submitBtn.innerHTML;
    const content = textarea.value.trim();
    if (!content) return;

    submitBtn.disabled = true;
    submitBtn.innerHTML = `
    <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
    Posting...
  `;

    try {
      const res = await fetch('/api/comments', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
          content,
          parent_id: parentId,
          page_id,
          type: commentType
        })
      });

      if (res.ok) {
        textarea.value = '';
        form.querySelector('#parentId').value = '';
        await loadComments(true);
        showSuccessToast('Comment posted! 🎉');
      } else {
        console.error('Failed to post comment', await res.text());
        showErrorToast(
          'Failed to post comment — tap to retry.',
          () => handleCommentSubmit(e)
        );
      }
    } catch (err) {
      console.error('Network error:', err);
      showErrorToast(
        'Network error — tap to retry.',
        () => handleCommentSubmit(e)
      );
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerHTML = originalHTML;
    }
  }


  async function updateReaction(id, action) {
    // 1) POST to /like or /dislike
    const res = await fetch(`/api/comments/${id}/${action}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      }
    });
    if (!res.ok) return; // bail on failure

    // 2) Expect both counts back
    const {
      likes,
      dislikes
    } = await res.json();

    // 3) Update the DOM in one place
    const commentDiv = document.getElementById(`comment-${id}`);
    commentDiv.querySelector('.like-btn .like-count').textContent = likes;
    commentDiv.querySelector('.dislike-btn .dislike-count').textContent = dislikes;

    // 4) Give the user a quick flash of feedback
    commentDiv.classList.add('bg-highlight');
    setTimeout(() => commentDiv.classList.remove('bg-highlight'), 1500);
  }

  function likeComment(id) {
    return updateReaction(id, 'like');
  }

  function dislikeComment(id) {
    return updateReaction(id, 'dislike');
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




  document.addEventListener('DOMContentLoaded', () => {
    // 2) Inject the full comment UI around every <infomundi-comments>
    document.querySelectorAll('infomundi-comments').forEach(el => {
      const wrapper = document.createElement('div');
      wrapper.className = 'mt-5';
      el.parentNode.insertBefore(wrapper, el);

      wrapper.innerHTML = `
      <div id="infCommentsToastContainer"
           class="position-fixed bottom-0 end-0 p-3"
           style="z-index: 1050;">
      </div>

      <h3 class="mb-4">
        Comments
        <span class="ms-1 badge text-bg-secondary" id="infomundiCommentsCount">0</span>
      </h3>
      <form id="commentForm" class="mb-4">
        <div class="d-flex align-items-start gap-2">
          <img src="${window.currentUserAvatarUrl}"
               alt="Commenting user's avatar"
               class="rounded me-2 d-none d-md-block d-lg-block"
               style="width: 3em; height: auto">
          <textarea id="commentText"
                    class="form-control flex-grow-1"
                    rows="4"
                    placeholder="What's on your mind?"
                    maxlength="1000"></textarea>
        </div>
        <div class="d-flex justify-content-end mt-2">
          <small id="commentTextCount" class="text-muted me-2">0/1000</small>
          <button type="submit" class="btn btn-primary">
            ${window.isUserAuthenticated ? 'Post' : 'Comment anonymously'}
          </button>
        </div>
        <input type="hidden" id="parentId" name="parentId">
      </form>
      <div id="commentFilters" class="d-flex justify-content-between align-items-center mb-5 flex-wrap">
        <div class="d-flex gap-2 flex-wrap">
          <select id="sortSelect" class="form-select form-select-sm w-auto">
            <option value="best">Best</option>
            <option value="recent">Recent</option>
            <option value="old">Old</option>
          </select>
        </div>
        <input type="text"
               id="searchInput"
               class="form-control form-control-sm w-auto mt-2 mt-sm-0"
               placeholder="Search..." />
      </div>
      <div id="commentsList"></div>
    `;

      // move the custom element into the wrapper
      wrapper.appendChild(el);

      // wire up live count on the main textarea
      const commentText = wrapper.querySelector('#commentText');
      const commentTextCount = wrapper.querySelector(
        '#commentTextCount');
      commentText.addEventListener('input', () => {
        commentTextCount.textContent =
          `${commentText.value.length}/1000`;
      });
      commentText.dispatchEvent(new Event('input'));
    });

    // 3) Now that the DOM exists, grab elements & wire up your existing logic
    const commentForm = document.getElementById('commentForm');
    const commentText = document.getElementById('commentText');
    const parentIdField = document.getElementById('parentId');
    const commentsList = document.getElementById('commentsList');

    commentForm.addEventListener('submit', handleCommentSubmit);

    const debouncedLoadComments = infCommentSearchDebounce(() =>
      loadComments(true), 300);
    document.getElementById('searchInput').addEventListener('input',
      debouncedLoadComments);
    document.getElementById('sortSelect').addEventListener('change', () =>
      loadComments(true));

    window.addEventListener('scroll', () => {
      if (window.innerHeight + window.scrollY >= document.body
        .offsetHeight - 500) {
        loadComments(false, true);
      }
    });

    // kick things off (InfomundiComments.connectedCallback will also invoke loadComments)
    loadComments(true);
  });

  class InfomundiComments extends HTMLElement {
    static get observedAttributes() {
      return ['page_id', 'type'];
    }

    constructor() {
      super();
    }

    connectedCallback() {
      // Initial render on first connection
      this.handlePageIdChange(this.getAttribute('page_id'));
      // also pick up the initial type
      commentType = this.getAttribute('type');
    }

    attributeChangedCallback(name, oldValue, newValue) {
      if (name === 'page_id' && newValue && newValue !== oldValue) {
        this.handlePageIdChange(newValue);
      }
      if (name === 'type' && newValue !== oldValue) {
        commentType = newValue;
        // if you want to reload comments when type changes:
        loadComments(true);
      }
    }

    handlePageIdChange(rawId) {
      if (!rawId) {
        console.error(
          "No page_id specified for <infomundi-comments>");
        return;
      }

      // URL-safe id
      const urlSafeId = encodeURIComponent(rawId);

      // Expose globally for fetch logic
      page_id = urlSafeId;
      window.page_id = urlSafeId;

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

    // 1) enforce maxlength
    textarea.setAttribute('maxlength', '1000');

    // 2) inject a counter element
    const replyCount = document.createElement('small');
    replyCount.className = 'text-muted ms-2 reply-char-count';
    replyCount.textContent = '0/1000';
    textarea.after(replyCount);

    // 3) wire up live updates
    textarea.addEventListener('input', () => {
      const len = textarea.value.length;
      replyCount.textContent = `${len}/1000`;
    });

    // initialize it (in case there’s pre-filled text)
    textarea.dispatchEvent(new Event('input'));

    // focus
    textarea.focus();

    // submit -> POST & reload
    form.addEventListener('submit', async e => {
      e.preventDefault();
      const replyBtn = form.querySelector('button[type="submit"]');
      const original = replyBtn.innerHTML;
      const content = textarea.value.trim();
      if (!content) return;

      // Show spinner
      replyBtn.disabled = true;
      replyBtn.innerHTML = `
    <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
    Replying...
  `;

      try {
        await fetch('/api/comments', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
          },
          body: JSON.stringify({
            content,
            parent_id: parentId,
            page_id,
            type: commentType
          })
        });
        await loadComments(true);
      } catch (err) {
        console.error(err);
      } finally {
        // Restore
        replyBtn.disabled = false;
        replyBtn.innerHTML = original;
      }
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



  /**
   * Generic Bootstrap toast generator.
   * @param {'success'|'danger'} type
   * @param {string} message
   * @param {Function=} retryCallback  optional, called if user taps the “Retry” button
   */
  function showToast(type, message, retryCallback) {
    const container = document.getElementById('infCommentsToastContainer');
    const toastEl = document.createElement('div');
    toastEl.className = `toast align-items-center text-bg-${type} border-0 mb-2`;
    toastEl.setAttribute('role', 'alert');
    toastEl.setAttribute('aria-live', 'assertive');
    toastEl.setAttribute('aria-atomic', 'true');

    // build inner HTML
    toastEl.innerHTML = `
    <div class="d-flex">
      <div class="toast-body" style="cursor: ${retryCallback ? 'pointer' : 'auto'};">
        ${message}
      </div>
      ${retryCallback
        ? `<button type="button" class="btn btn-sm me-2 retry-btn">Retry</button>`
        : ''}
      <button
        type="button"
        class="btn-close btn-close-white me-2 m-auto"
        data-bs-dismiss="toast"
        aria-label="Close"></button>
    </div>
  `;

    // append & show
    container.appendChild(toastEl);
    const toast = new bootstrap.Toast(toastEl, {
      delay: 5000
    });

    // wire retry
    if (retryCallback) {
      toastEl.querySelector('.retry-btn')
        .addEventListener('click', () => {
          retryCallback();
          toast.hide();
        });
    }

    toast.show();
    toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
  }

  function showSuccessToast(msg) {
    showToast('success', msg);
  }

  function showErrorToast(msg, retryCallback) {
    showToast('danger', msg, retryCallback);
  }

  // When the user tries to leave/reload
  window.addEventListener('beforeunload', (e) => {
    if (hasUnsavedText()) {
      // Standard way to trigger a confirmation dialog
      e.preventDefault();
      e.returnValue = '';
      // Some browsers require returnValue set; some look at the returned string
      return '';
    }
  });