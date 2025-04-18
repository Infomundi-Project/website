from .models import Comment
from .security_util import uuid_bytes_to_string


def serialize_comment_tree(comment):
    return {
        'id': comment.id,
        'user': {
            'id': uuid_bytes_to_string(comment.user.public_id),
            'username': comment.user.display_name if comment.user.display_name else comment.user.username,
            'avatar_url': comment.user.avatar_url,
            'role': comment.user.role
        },
        'content': '[deleted]' if comment.is_deleted else comment.content,
        'is_edited': comment.is_edited,
        'updated_at': comment.updated_at,
        'created_at': comment.created_at.isoformat(),
        'replies': [serialize_comment_tree(reply) for reply in comment.replies.order_by(Comment.created_at.asc())],
        'likes': comment.reactions.filter_by(action='like').count(),
        'dislikes': comment.reactions.filter_by(action='dislike').count()
    }
