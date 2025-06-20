from . import (
    extensions,
    models,
    security_util,
    hashing_util,
    config,
    llm_util,
    input_sanitization,
)


def get_anonymous_user() -> object:
    anonymous_user = models.User.query.filter_by(username="anonymous").first()
    if not anonymous_user:
        anonymous_user = models.User(
            username="anonymous",
            public_id=security_util.generate_uuid_bytes(),
            email_fingerprint=hashing_util.generate_hmac_signature(
                "anonymous@anonymous.com", as_bytes=True
            ),
            email_encrypted=security_util.encrypt("anonymous@anonymous.com"),
            password=hashing_util.string_to_argon2_hash(config.SECRET_KEY),
            is_enabled=True,
            role="official",
        )
        extensions.db.session.commit()
        extensions.db.session.add(anonymous_user)

    return anonymous_user


def create_user_in_database(username: str = "", email: str = "", password: str = ""):
    user = models.User(
        username=username if username else "",
        public_id=security_util.generate_uuid_bytes(),
        email_fingerprint=hashing_util.generate_hmac_signature(
            "anonymous@anonymous.com", as_bytes=True
        ),
        email_encrypted=security_util.encrypt("anonymous@anonymous.com"),
        password=hashing_util.string_to_argon2_hash(config.SECRET_KEY),
        is_enabled=True,
        role="official",
    )
    extensions.db.session.commit()
    extensions.db.session.add(user)


def serialize_comment_tree(comment) -> dict:
    return {
        "id": comment.id,
        "user": {
            "id": security_util.uuid_bytes_to_string(comment.user.public_id),
            "username": comment.user.username,
            "display_name": comment.user.display_name or None,
            "avatar_url": comment.user.avatar_url,
            "role": comment.user.role,
        },
        "content": "[deleted]" if comment.is_deleted else comment.content,
        "is_flagged": comment.is_flagged,
        "is_edited": comment.is_edited,
        "updated_at": comment.updated_at.isoformat(),
        "created_at": comment.created_at.isoformat(),
        "parent_id": comment.parent_id,
        "replies": [
            serialize_comment_tree(reply)
            for reply in comment.replies.order_by(models.Comment.created_at.asc())
        ],
        "likes": comment.reactions.filter_by(action="like").count(),
        "dislikes": comment.reactions.filter_by(action="dislike").count(),
    }


def is_content_inappropriate(content: str) -> bool:
    content_moderation = llm_util.is_inappropriate(
        text=content, simple_return=False
    ).categories
    moderation_categories = ("self_harm", "sexual_minors")
    return any(
        getattr(content_moderation, category, False)
        for category in moderation_categories
    ) or input_sanitization.has_external_links(content)
