def get_replies(comment):
    replies_list = []
    for reply in comment.replies:
        reply_dict = {
            'id': reply.comment_id,
            'text': reply.text,
            'userName': reply.user.username,
            'userRole': reply.user.role,
            'userAvatar': reply.user.avatar_url,
            'timestamp': reply.timestamp,
            'likes': reply.likes,
            'dislikes': reply.dislikes,
            'replies': get_replies(reply)  # Recursive call to get replies of the reply
        }
        replies_list.append(reply_dict)
    return replies_list


def sort_comments(comments: list, sort_by:str='newest'):
    """
    Sort comments based on the specified criterion.

    :param comments: List of comment dictionaries.
    :param sort_by: Sorting criterion ('newest', 'oldest', 'top').
    :return: Sorted list of comments.
    """

    if not comments:
        return comments

    if sort_by == 'oldest':
        # Sort by timestamp in ascending order for oldest first
        return sorted(comments, key=lambda x: x['timestamp'])

    elif sort_by == 'newest':
        # Sort by timestamp in descending order for newest first
        return sorted(comments, key=lambda x: x['timestamp'], reverse=True)

    elif sort_by == 'top':
        # Sort by likes in descending order for top comments
        return sorted(comments, key=lambda x: x['likes'], reverse=True)

    else:
        return comments