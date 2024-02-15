$(document).ready(function() {
    loadComments(); // Initial load of comments

    // Event handler for changing the sort order
    $('#sort-comments').change(function() {
        loadComments();
    });

    // Event handler for submitting a new comment
    $('#cooldown-button').click(function() {
        submitComment();
    });

    // Delegated event handlers for dynamic elements (like, dislike, reply, report, etc.)
    $('#comments-section').on('click', '.like-btn', function() {
        handleLikeDislikeReport($(this).data('commentId'), 'like');
    });

    $('#comments-section').on('click', '.dislike-btn', function() {
        handleLikeDislikeReport($(this).data('commentId'), 'dislike');
    });

    $('#comments-section').on('click', '.reply-btn', function() {
        showReplyBox($(this).data('commentId'));
    });

    $('#comments-section').on('click', '.report-btn', function() {
        handleLikeDislikeReport($(this).data('commentId'), 'report');
    });

    $('#comments-section').on('click', '.submit-reply', function() {
        submitReply($(this).data('parentId'));
    });

    $('#comments-section').on('click', '.view-more-replies', function() {
        loadReplies($(this).data('commentId'));
    });
});


function loadComments() {
    var sortBy = $('#sort-comments').val();
    $.ajax({
        url: '/api/comments',
        type: 'GET',
        data: { sort: sortBy },
        success: function(data) {
            $('#total-comments').text(`${data.total}`);
            renderComments(data.comments);
        }
    });
}


function renderComments(comments, parentId = null) {
    // Ensure comments is always an array
    comments = Array.isArray(comments) ? comments : [];

    if (!parentId) {
        $('#comments-list').empty();
    }

    comments.forEach(function(comment) {
        var roleTag = '';
        if (comment.userRole) {
            var badgeClass = 'bg-secondary'; // Default badge class
            if (comment.userRole === 'admin') {
                badgeClass = 'bg-danger';
                roleTag = `<span class="badge ${badgeClass} ms-2">${comment.userRole}</span>`;
            } else if (comment.userRole === 'moderator') {
                badgeClass = 'bg-success';
            } else if (comment.userRole === 'subscriber') {
                badgeClass = 'bg-info';
            }
        }

        var commentHtml = `
            <div class="list-group-item ${parentId ? 'ms-3' : ''}" id="comment-${comment.id}">
                <div class="d-flex w-100 justify-content-between">
                    <div class="d-flex align-items-center">
                        <img src="${comment.userAvatar}" alt="${comment.userName}'s Avatar" class="rounded-circle me-2" style="width: 38px; height: 38px;">
                        <h5 class="mb-1">${comment.userName}${roleTag}</h5>
                    </div>
                    <small>${timeSince(new Date(comment.timestamp))}</small>
                </div>
                <p class="mb-1" style="word-wrap: break-word;">${comment.text}</p>
                <div>
                    <button class="btn btn-outline-primary btn-sm like-btn" data-comment-id="${comment.id}"><i class="fa-solid fa-circle-up me-1"></i>${comment.likes}</button>
                    <button class="btn btn-outline-secondary btn-sm dislike-btn ms-1" data-comment-id="${comment.id}"><i class="fa-solid fa-circle-down me-1"></i>${comment.dislikes}</button>
                    <button class="btn btn-outline-info btn-sm reply-btn ms-1" data-comment-id="${comment.id}"><i class="fa-solid fa-reply"></i></button>
                    <button class="btn btn-outline-danger btn-sm report-btn ms-3" data-comment-id="${comment.id}"><i class="fa-solid fa-flag"></i></button>
                </div>
            </div>
        `;

        if (parentId) {
            $(`#comment-${parentId} .replies`).append(commentHtml);
        } else {
            $('#comments-list').append(commentHtml);
        }

        if (comment.replies && comment.replies.length > 0) {
            if (!$(`#comment-${comment.id} .replies`).length) {
                $(`#comment-${comment.id}`).append('<div class="replies list-group mt-2"></div>');
            }
            renderComments(comment.replies, comment.id);
        }
    });
}


function submitComment() {
    var commentText = $('#new-comment').val().trim(); // Use .trim() to remove whitespace from both ends of the string

    // Check if the commentText is not empty
    if (commentText) {
        // Proceed with the AJAX call since there is some text in the comment input
        $.ajax({
            url: '/api/comments',
            type: 'POST',
            data: JSON.stringify({ text: commentText }),
            contentType: 'application/json; charset=utf-8',
            success: function() {
                $('#new-comment').val(''); // Clear the input field on successful submission
                loadComments(); // Reload comments to include the new one
                start_countdown('cooldown-button', 7); // Calls countdown again
            }
        });
    } else {
        alert('Please enter a comment before submitting.');
    }
}


function handleLikeDislikeReport(commentId, action) {
    $.ajax({
        url: `/api/comments/${commentId}/${action}`,
        type: 'POST',
        success: function(response) {
            if (action === 'report') {
                alert(response.message);
            }
            loadComments(); // Reload to update likes/dislikes
        },
        error: function(response) {
            alert(response.message);
        }
    });
}


function showReplyBox(commentId) {
    // Remove any existing reply boxes first to ensure only one reply box is open at a time
    $('.reply-box').remove();

    // Create the reply box HTML using Bootstrap classes
    var replyBoxHtml = `
        <div class="reply-box mt-2">
            <form class="d-flex flex-column">
                <textarea class="form-control mb-2 reply-text" placeholder="Write a reply..."></textarea>
                <div class="d-flex justify-content-end">
                    <button type="button" class="btn btn-secondary me-2 cancel-reply">Cancel</button>
                    <button type="button" class="btn btn-primary submit-reply" id="submit-reply" data-parent-id="${commentId}">Reply</button>
                </div>
            </form>
        </div>
    `;

    // Append the reply box to the specific comment
    $(`#comment-${commentId}`).append(replyBoxHtml);

    // Optionally, add an event listener for the Cancel button to remove the reply box when clicked
    $('.cancel-reply').click(function() {
        $(this).closest('.reply-box').remove();
    });
}


function submitReply(parentId) {
    var replyText = $(`#comment-${parentId} .reply-text`).val().trim();
    
    if (replyText) {
        $.ajax({
            url: '/api/comments',
            type: 'POST',
            data: JSON.stringify({ text: replyText, parentId: parentId }),
            contentType: 'application/json; charset=utf-8',
            success: function() {
                loadComments(); // Reload comments to include the new reply
                start_countdown('submit-reply', 5);
            },
            error: function(response) {
                alert(response.message);
            }
        });
    } else {
        alert('Please enter a reply before submitting.');
    }
}


function loadReplies(commentId) {
    $.ajax({
        url: `/api/comments/${commentId}/replies`,
        type: 'GET',
        success: function(data) {
            renderComments(data.replies, commentId);
        }
    });
}

function timeSince(date) {
    var seconds = Math.floor((new Date() - date) / 1000);
    var interval = seconds / 31536000;

    if (interval > 1) {
        return Math.floor(interval) + " years ago";
    }
    interval = seconds / 2592000;
    if (interval > 1) {
        return Math.floor(interval) + " months ago";
    }
    interval = seconds / 86400;
    if (interval > 1) {
        return Math.floor(interval) + " days ago";
    }
    interval = seconds / 3600;
    if (interval > 1) {
        return Math.floor(interval) + " hours ago";
    }
    interval = seconds / 60;
    if (interval > 1) {
        return Math.floor(interval) + " minutes ago";
    }
    return Math.floor(seconds) + " seconds ago";
}
