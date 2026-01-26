from datetime import datetime, timedelta
from flask_login import UserMixin
from sqlalchemy.dialects.mysql import MEDIUMINT, TIMESTAMP, TINYBLOB, BINARY, CHAR

from .extensions import db
from . import (
    security_util,
    hashing_util,
    totp_util,
    qol_util,
    input_sanitization,
    config,
)

# Configure basic logging for storage mode detection
import logging

target_logger = logging.getLogger(__name__)

# Storage mode detection - check if we're using local storage or S3
USE_LOCAL_STORAGE = False
try:
    if not config.R2_ENDPOINT or not config.R2_ACCESS_KEY or not config.R2_SECRET:
        USE_LOCAL_STORAGE = True
        target_logger.info("Models: Using local storage mode for media URLs")
except AttributeError:
    USE_LOCAL_STORAGE = True
    target_logger.info("Models: R2 config not found, using local storage mode")


def get_storage_url(path: str) -> str:
    """
    Returns appropriate URL based on storage mode.
    In production: returns S3/R2 bucket URL
    In dev: returns local static file path
    """
    if USE_LOCAL_STORAGE:
        return f"/static/local_uploads/{path}"
    else:
        return f"https://bucket.infomundi.net/{path}"


class Publisher(db.Model):
    __tablename__ = "publishers"
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    name = db.Column(db.String(150), nullable=False)
    feed_url = db.Column(db.String(200))
    site_url = db.Column(db.String(200))

    favicon_url = db.Column(db.String(100), nullable=True)

    __table_args__ = (db.Index("uq_site_url", "site_url", unique=True),)


class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    name = db.Column(db.String(15), nullable=False, unique=True)


class Tag(db.Model):
    __tablename__ = "tags"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    story_id = db.Column(
        db.Integer, db.ForeignKey("stories.id", ondelete="CASCADE"), nullable=False
    )
    tag = db.Column(db.String(30), nullable=False)

    __table_args__ = (
        # ensure we don't get duplicate tags on the same story
        db.UniqueConstraint("story_id", "tag", name="uq_story_tag"),
        db.Index("idx_tags_story", "story_id"),
    )

    # back-ref for convenience
    story = db.relationship("Story", back_populates="tags")


class Story(db.Model):
    __tablename__ = "stories"
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)

    title = db.Column(db.String(250), nullable=False)
    description = db.Column(
        db.String(500), nullable=False, default="No description was provided."
    )
    lang = db.Column(
        db.String(2), nullable=False, default="en"
    )  # this could be an individual table
    author = db.Column(db.String(150))  # this could be an individual table
    gpt_summary = db.Column(db.JSON)  # this could be an individual table

    url = db.Column(db.String(512), nullable=False)
    url_hash = db.Column(
        BINARY(16), nullable=False, unique=True
    )  # this is used so we don't add repeated stories to the database (improved index because it's a BINARY)

    pub_date = db.Column(db.DateTime, nullable=False)
    has_image = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    publisher_id = db.Column(db.Integer, db.ForeignKey("publishers.id"), nullable=False)

    # pull in all tags that reference this story
    tags = db.relationship(
        "Tag",
        back_populates="story",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    # Relationships
    reactions = db.relationship("StoryReaction", backref="story", lazy=True)
    stats = db.relationship("StoryStats", backref="story", uselist=False, lazy="joined")
    category = db.relationship("Category", backref="story")
    publisher = db.relationship("Publisher", backref="story")

    country_id = db.Column(
        MEDIUMINT(unsigned=True), db.ForeignKey("countries.id"), nullable=True
    )
    country = db.relationship("Country", backref="story", lazy="joined")

    def get_public_id(self) -> str:
        return hashing_util.binary_to_md5_hex(self.url_hash)

    def get_image_url(self) -> str:
        if not self.has_image:
            return ""

        path = f"stories/{self.category.name}/{self.get_public_id()}.avif"
        return get_storage_url(path)

    @property
    def image_url(self) -> str:
        return self.get_image_url()

    def to_dict(self) -> dict:
        return {
            "story_id": self.get_public_id(),
            "id": self.id,
            "title": self.title,
            "tags": [tag.tag for tag in self.tags],
            "author": self.author,
            "description": self.description or "",
            "views": self.stats.views if self.stats else 0,
            "likes": self.stats.likes if self.stats else 0,
            "dislikes": self.stats.dislikes if self.stats else 0,
            "url": self.url,
            "pub_date": self.pub_date,
            "publisher": {
                "name": input_sanitization.clean_publisher_name(self.publisher.name),
                "url": self.publisher.site_url,
                "favicon_url": self.publisher.favicon_url,
            },
            "image_url": self.get_image_url(),
        }


class StoryReaction(db.Model):
    __tablename__ = "story_reactions"
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)

    story_id = db.Column(
        db.Integer, db.ForeignKey("stories.id", ondelete="CASCADE"), nullable=False
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    action = db.Column(db.String(7), nullable=False)  # 'like', 'dislike', 'report'
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp())

    __table_args__ = (
        db.UniqueConstraint("story_id", "user_id", "action", name="unique_reaction"),
    )


class StoryStats(db.Model):
    __tablename__ = "story_stats"
    story_id = db.Column(
        db.Integer, db.ForeignKey("stories.id", ondelete="CASCADE"), primary_key=True
    )
    dislikes = db.Column(db.Integer, default=0)
    views = db.Column(db.Integer, default=0)
    likes = db.Column(db.Integer, default=0)


class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    public_id = db.Column(BINARY(16), nullable=False, unique=True)

    # User Account Data
    username = db.Column(db.String(25), nullable=False, unique=True)
    email_fingerprint = db.Column(
        BINARY(32), nullable=False, unique=True
    )  # SHA-256 HMAC
    email_encrypted = db.Column(BINARY(120), nullable=False)  # AES-GCM

    role = db.Column(db.String(15), default="user")
    password = db.Column(db.String(150), nullable=False)
    session_version = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    last_login = db.Column(db.DateTime)

    # Profile
    display_name = db.Column(db.String(40))
    profile_description = db.Column(db.String(1500))

    # Calculated later on
    has_avatar = db.Column(db.Boolean, default=False)
    has_banner = db.Column(db.Boolean, default=False)
    has_wallpaper = db.Column(db.Boolean, default=False)

    # Contact info
    website_url = db.Column(db.String(120))
    public_email = db.Column(db.String(120))
    # External links
    twitter_url = db.Column(db.String(80))
    instagram_url = db.Column(db.String(80))
    linkedin_url = db.Column(db.String(80))
    # Level and privacy
    level = db.Column(db.Integer, default=0)
    level_progress = db.Column(db.Integer, default=0)

    # Privacy settings
    profile_visibility = db.Column(
        db.Boolean, default=False
    )  # 0 = public // 1 = login-only // 2 = friends-only // 3 = private
    notification_type = db.Column(
        db.Boolean, default=False
    )  # 0 = all // 1 = important-only // 2 = none

    # Account Registration
    is_enabled = db.Column(db.Boolean, default=False)
    is_thirdparty_auth = db.Column(db.Boolean, default=False)
    register_token = db.Column(BINARY(16))
    register_token_timestamp = db.Column(
        db.DateTime, default=db.func.current_timestamp()
    )

    # Account Recovery
    in_recovery = db.Column(db.Boolean, default=False)
    recovery_token = db.Column(BINARY(16))
    recovery_token_timestamp = db.Column(db.DateTime)

    # Account Deletion
    delete_token = db.Column(BINARY(16))
    delete_token_timestamp = db.Column(db.DateTime)

    # Activity
    is_online = db.Column(db.Boolean, default=False)
    last_activity = db.Column(db.DateTime, default=db.func.current_timestamp())

    # Totp
    is_totp_enabled = db.Column(db.Boolean, default=False)
    totp_secret = db.Column(BINARY(120))  # AES/GCM

    totp_recovery = db.Column(db.String(150))  # Argon2id

    is_mail_twofactor_enabled = db.Column(db.Boolean, default=False)
    mail_twofactor_code = db.Column(db.Integer)
    mail_twofactor_timestamp = db.Column(db.DateTime)

    # messaging pk
    public_key_jwk = db.Column(db.JSON, nullable=True)

    country_id = db.Column(
        MEDIUMINT(unsigned=True), db.ForeignKey("countries.id"), nullable=True
    )
    state_id = db.Column(
        MEDIUMINT(unsigned=True), db.ForeignKey("states.id"), nullable=True
    )
    city_id = db.Column(
        MEDIUMINT(unsigned=True), db.ForeignKey("cities.id"), nullable=True
    )

    country = db.relationship("Country", backref="users", lazy="joined")
    state = db.relationship("State", backref="users", lazy="joined")
    city = db.relationship("City", backref="users", lazy="joined")

    def get_public_id(self):
        return security_util.uuid_bytes_to_string(self.public_id)

    def get_picture(self, category: str) -> str:
        if category not in ("avatar", "banner", "wallpaper"):
            return ""

        if category == "avatar":
            if not self.has_avatar:
                return "/static/img/avatar.webp"
            path = "users"
        elif category == "banner":
            if not self.has_banner:
                return ""
            path = "banners"
        else:
            if not self.has_wallpaper:
                return ""
            path = "wallpapers"

        return get_storage_url(f"{path}/{self.get_public_id()}.webp")

    @property
    def avatar_url(self) -> str:
        return self.get_picture("avatar")

    @property
    def banner_url(self) -> str:
        return self.get_picture("banner")

    @property
    def wallpaper_url(self) -> str:
        return self.get_picture("wallpaper")

    def enable(self):
        self.is_enabled = True
        self.register_token = None
        self.register_token_timestamp = None
        db.session.commit()

    def disable(self):
        self.is_enabled = False
        db.session.commit()

    def set_password(self, password: str):
        self.password = hashing_util.string_to_argon2_hash(password)
        db.session.commit()

    def set_email(self, email: str):
        self.email_encrypted = security_util.encrypt(email)
        self.email_fingerprint = hashing_util.generate_hmac_signature(email, as_bytes=True)
        db.session.commit()

    def check_password(self, password: str) -> bool:
        return hashing_util.argon2_verify_hash(self.password, password)

    def get_id(self):
        return str(self.id)

    def purge_totp(self):
        self.is_totp_enabled = False
        self.totp_secret = None
        self.totp_recovery = None
        db.session.commit()

    def setup_totp(self, totp_secret) -> str:
        totp_recovery_token = security_util.generate_nonce()

        self.totp_recovery = hashing_util.string_to_argon2_hash(totp_recovery_token)
        self.totp_secret = security_util.encrypt(totp_secret)
        self.is_mail_twofactor_enabled = False
        self.is_totp_enabled = True
        db.session.commit()

        return totp_recovery_token

    def check_totp(self, code: str, recovery_token: str = "") -> bool:
        if recovery_token:
            if not hashing_util.argon2_verify_hash(self.totp_recovery, recovery_token):
                return False

            self.purge_totp()
            return True

        return totp_util.verify_totp(security_util.decrypt(self.totp_secret), code)

    def setup_mail_twofactor(self) -> str:
        self.purge_totp()  # Removes totp-based two factor
        self.is_mail_twofactor_enabled = True

        # Changes totp recovery
        totp_recovery = security_util.generate_nonce()
        self.totp_recovery = hashing_util.string_to_argon2_hash(totp_recovery)

        db.session.commit()
        return totp_recovery

    def check_mail_twofactor(self, code: str, recovery_token: str = "") -> bool:
        if recovery_token:
            if not hashing_util.argon2_verify_hash(self.totp_recovery, recovery_token):
                return False

        if str(
            self.mail_twofactor_code
        ) != code or not qol_util.is_date_within_threshold_minutes(
            self.mail_twofactor_timestamp, 15
        ):
            return False

        self.mail_twofactor_code = None
        self.mail_twofactor_timestamp = None
        db.session.commit()
        return True

    def check_is_online(self):
        now = datetime.utcnow()
        online_threshold = timedelta(minutes=3)

        self.is_online = (now - self.last_activity) <= online_threshold
        db.session.commit()

        return self.is_online

    def get_platform_username(self, platform: str):
        if platform == "linkedin":
            url = self.linkedin_url
        elif platform == "instagram":
            url = self.instagram_url
        else:
            url = self.twitter_url

        return input_sanitization.extract_username_from_thirdparty_platform_url(url)[
            1
        ]  # [1] here is the username


class UserStoryView(db.Model):
    __tablename__ = "user_story_views"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    story_id = db.Column(
        db.Integer, db.ForeignKey("stories.id", ondelete="CASCADE"), nullable=False
    )
    viewed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", backref="story_views", lazy="joined")
    story = db.relationship("Story", backref="user_views", lazy="joined")


class UserReport(db.Model):
    __tablename__ = "user_reports"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    reporter_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    reported_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    category = db.Column(
        db.Enum(
            "spam",
            "harassment",
            "hate_speech",
            "inappropriate",
            "other",
            name="report_category_enum",
        ),
        nullable=False,
        default="other",
    )

    reason = db.Column(db.String(500), nullable=True)

    status = db.Column(db.String(20), nullable=False, default="pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    reviewed_at = db.Column(db.DateTime, nullable=True)

    # relationships for easy backrefs
    reporter = db.relationship(
        "User", foreign_keys=[reporter_id], backref="reports_made", lazy="joined"
    )
    reported = db.relationship(
        "User", foreign_keys=[reported_id], backref="reports_received", lazy="joined"
    )
    __table_args__ = (
        # no more duplicate reports in the same category!
        db.UniqueConstraint(
            "reporter_id", "reported_id", "category", name="uq_user_report"
        ),
        db.Index("idx_user_reports_reporter", "reporter_id"),
        db.Index("idx_user_reports_reported", "reported_id"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "category": self.category,
            "reason": self.reason,
            "status": self.status,
            "createdAt": self.created_at.isoformat(),
            "reviewedAt": self.reviewed_at.isoformat() if self.reviewed_at else None,
        }


class UserBlock(db.Model):
    __tablename__ = "user_blocks"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    blocker_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    blocked_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    blocker = db.relationship(
        "User", foreign_keys=[blocker_id], backref=db.backref("blocks_made")
    )

    blocked = db.relationship(
        "User", foreign_keys=[blocked_id], backref=db.backref("blocked_by")
    )

    __table_args__ = (
        # one block per pair
        db.UniqueConstraint("blocker_id", "blocked_id", name="uq_user_block"),
        db.Index("idx_user_blocks_blocker", "blocker_id"),
        db.Index("idx_user_blocks_blocked", "blocked_id"),
    )


class Friendship(db.Model):
    __tablename__ = "friendships"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    created_at = db.Column(TIMESTAMP, default=db.func.current_timestamp())
    # 'pending', 'accepted', 'rejected'
    status = db.Column(db.String(10), nullable=False, default="pending")
    accepted_at = db.Column(TIMESTAMP)

    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    friend_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    __table_args__ = (
        db.UniqueConstraint("user_id", "friend_id", name="unique_friendship"),
    )

    user = db.relationship(
        "User",
        foreign_keys=[user_id],
        backref=db.backref("user_friendships", lazy="dynamic"),
    )
    friend = db.relationship(
        "User",
        foreign_keys=[friend_id],
        backref=db.backref("friend_friendships", lazy="dynamic"),
    )


class SiteStatistics(db.Model):
    __tablename__ = "site_statistics"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    last_updated_message = db.Column(db.String(15), nullable=False)
    total_countries_supported = db.Column(db.Integer, nullable=False)
    total_news = db.Column(db.Integer, nullable=False)
    total_feeds = db.Column(db.Integer, nullable=False)
    total_users = db.Column(db.Integer, nullable=False)
    total_comments = db.Column(db.Integer, nullable=False)
    total_clicks = db.Column(db.Integer, nullable=False)


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Unique page identifier (MD5)
    page_hash = db.Column(TINYBLOB, nullable=False)

    # Commeting user
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )

    # Save story id if it's a story
    story_id = db.Column(
        db.Integer, db.ForeignKey("stories.id", ondelete="SET NULL"), nullable=True
    )

    # Means it's a reply
    parent_id = db.Column(
        db.Integer, db.ForeignKey("comments.id", ondelete="CASCADE"), nullable=True
    )

    content = db.Column(db.String(1000), nullable=False)
    url = db.Column(db.String(100))  # URL where to find the comment
    is_flagged = db.Column(db.Boolean, default=False)
    is_edited = db.Column(db.Boolean, default=False)
    is_deleted = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    deleted_at = db.Column(db.DateTime)

    # Relationships
    replies = db.relationship(
        "Comment",
        backref=db.backref("parent", remote_side=[id]),
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    # one-to-one link to stats
    stats = db.relationship(
        "CommentStats",
        back_populates="comment",
        uselist=False,
        cascade="all, delete-orphan",
    )
    reactions = db.relationship("CommentReaction", backref="comment", lazy="dynamic")
    user = db.relationship("User", backref="comments")


class CommentReaction(db.Model):
    __tablename__ = "comment_reactions"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    comment_id = db.Column(
        db.Integer, db.ForeignKey("comments.id", ondelete="CASCADE"), nullable=False
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    action = db.Column(db.String(7), nullable=False)  # 'like', 'dislike', 'report'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("comment_id", "user_id", name="unique_comment_reaction"),
    )


class CommentStats(db.Model):
    __tablename__ = "comment_stats"

    # one row per comment
    comment_id = db.Column(
        db.Integer, db.ForeignKey("comments.id", ondelete="CASCADE"), primary_key=True
    )
    likes = db.Column(db.Integer, default=0, nullable=False)
    dislikes = db.Column(db.Integer, default=0, nullable=False)

    # backref to access from Comment
    comment = db.relationship("Comment", back_populates="stats", uselist=False)


class Stocks(db.Model):
    __tablename__ = "stocks"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    country_name = db.Column(db.String(40), nullable=False)
    data = db.Column(db.Text, nullable=False)


class Currencies(db.Model):
    __tablename__ = "currencies"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    data = db.Column(db.Text, nullable=False)


class Crypto(db.Model):
    __tablename__ = "crypto"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    data = db.Column(db.Text, nullable=False)


class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Which user will receive this notification
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    user = db.relationship("User", backref=db.backref("notifications", lazy="dynamic"))

    # A simple enum or string to categorize
    type = db.Column(db.String(20), nullable=False)
    # "default", "new_comment", "comment_reply", "comment_reaction", "friend_request", "friend_accepted", "friend_status", "mentions", "security", "profile_edit"

    # Optional foreign keys to domain objects
    comment_id = db.Column(
        db.Integer, db.ForeignKey("comments.id", ondelete="CASCADE"), nullable=True
    )
    friendship_id = db.Column(
        db.Integer, db.ForeignKey("friendships.id", ondelete="CASCADE"), nullable=True
    )

    # Friendly message or metadata
    message = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(512), nullable=True)  # link to view the item

    is_read = db.Column(db.Boolean, default=False, nullable=False)
    read_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.Index("idx_notifications_user_unread", "user_id", "is_read"),
        db.UniqueConstraint(
            "user_id",
            "type",
            "friendship_id",
            "is_read",
            name="uq_notifications_pending_friend",
        ),
    )


class Bookmark(db.Model):
    __tablename__ = "bookmarks"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    story_id = db.Column(
        db.Integer,
        db.ForeignKey("stories.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at = db.Column(
        db.DateTime, default=db.func.current_timestamp(), nullable=False
    )

    __table_args__ = (
        # one bookmark per (user, story)
        db.UniqueConstraint("user_id", "story_id", name="uq_user_story_bookmark"),
    )


class Message(db.Model):
    __tablename__ = "messages"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    content_encrypted = db.Column(db.Text, nullable=False)  # ciphertext (e.g. Base64)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    delivered_at = db.Column(db.DateTime, default=None, nullable=True)
    read_at = db.Column(db.DateTime, default=None, nullable=True)

    parent_id = db.Column(db.Integer, db.ForeignKey("messages.id"), nullable=True)
    replied_to = db.relationship("Message", remote_side=[id], uselist=False)

    # Relationships (for convenience, if needed)
    sender = db.relationship(
        "User", foreign_keys=[sender_id], backref="sent_messages", lazy=True
    )
    receiver = db.relationship(
        "User", foreign_keys=[receiver_id], backref="received_messages", lazy=True
    )


class Region(db.Model):
    __tablename__ = "regions"
    id = db.Column(MEDIUMINT(unsigned=True), autoincrement=True, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    translations = db.Column(db.Text)
    created_at = db.Column(TIMESTAMP, default=None)
    updated_at = db.Column(TIMESTAMP, default=None)
    flag = db.Column(db.Boolean, nullable=False, default=True)
    wikiDataId = db.Column(db.String(255), comment="Rapid API GeoDB Cities")

    subregions = db.relationship("Subregion", backref="parent_region", lazy=True)
    countries = db.relationship(
        "Country",
        foreign_keys="Country.region_id",
        backref="parent_region_rel",
        lazy=True,
    )


class Subregion(db.Model):
    __tablename__ = "subregions"
    id = db.Column(MEDIUMINT(unsigned=True), autoincrement=True, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    translations = db.Column(db.Text)
    region_id = db.Column(
        MEDIUMINT(unsigned=True), db.ForeignKey("regions.id"), nullable=False
    )
    created_at = db.Column(TIMESTAMP, default=None)
    updated_at = db.Column(TIMESTAMP, default=None)
    flag = db.Column(db.Boolean, nullable=False, default=True)
    wikiDataId = db.Column(db.String(255), comment="Rapid API GeoDB Cities")

    countries = db.relationship(
        "Country",
        foreign_keys="Country.subregion_id",
        backref="parent_subregion_rel",
        lazy=True,
    )

    __table_args__ = (db.Index("subregion_continent", "region_id"),)


class Country(db.Model):
    __tablename__ = "countries"
    id = db.Column(MEDIUMINT(unsigned=True), autoincrement=True, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    iso3 = db.Column(db.String(3))
    numeric_code = db.Column(db.String(3))
    iso2 = db.Column(db.String(2))
    phonecode = db.Column(db.String(255))
    capital = db.Column(db.String(255))
    currency = db.Column(db.String(255))
    currency_name = db.Column(db.String(255))
    currency_symbol = db.Column(db.String(255))
    tld = db.Column(db.String(255))
    native = db.Column(db.String(255))
    region = db.Column(db.String(255))  # Legacy text field
    region_id = db.Column(
        MEDIUMINT(unsigned=True), db.ForeignKey("regions.id"), nullable=True
    )
    subregion = db.Column(db.String(255))  # Legacy text field
    subregion_id = db.Column(
        MEDIUMINT(unsigned=True), db.ForeignKey("subregions.id"), nullable=True
    )
    nationality = db.Column(db.String(255))
    timezones = db.Column(db.Text)
    translations = db.Column(db.Text)
    latitude = db.Column(db.Numeric(10, 8))
    longitude = db.Column(db.Numeric(11, 8))
    emoji = db.Column(db.String(191))
    emojiU = db.Column(db.String(191))
    created_at = db.Column(TIMESTAMP, default=None)
    updated_at = db.Column(TIMESTAMP, default=None)
    flag = db.Column(db.Boolean, nullable=False, default=True)
    wikiDataId = db.Column(db.String(255), comment="Rapid API GeoDB Cities")

    # Relationships - use explicit foreign_keys to avoid ambiguity
    # Note: backrefs are defined on Region and Subregion models
    states = db.relationship("State", backref="country", lazy=True)
    cities = db.relationship("City", backref="country", lazy=True)

    __table_args__ = (
        db.Index("country_continent", "region_id"),
        db.Index("country_subregion", "subregion_id"),
    )


class State(db.Model):
    __tablename__ = "states"
    id = db.Column(MEDIUMINT(unsigned=True), autoincrement=True, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    country_id = db.Column(
        MEDIUMINT(unsigned=True), db.ForeignKey("countries.id"), nullable=False
    )
    country_code = db.Column(CHAR(2), nullable=False)
    fips_code = db.Column(db.String(255))
    iso2 = db.Column(db.String(255))
    type = db.Column(db.String(191))
    latitude = db.Column(db.Numeric(10, 8))
    longitude = db.Column(db.Numeric(11, 8))
    created_at = db.Column(TIMESTAMP, default=None)
    updated_at = db.Column(TIMESTAMP, default=None)
    flag = db.Column(db.Boolean, nullable=False, default=True)
    wikiDataId = db.Column(db.String(255), comment="Rapid API GeoDB Cities")

    cities = db.relationship("City", backref="state", lazy=True)

    __table_args__ = (db.Index("country_region", "country_id"),)


class City(db.Model):
    __tablename__ = "cities"
    id = db.Column(MEDIUMINT(unsigned=True), autoincrement=True, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    state_id = db.Column(
        MEDIUMINT(unsigned=True), db.ForeignKey("states.id"), nullable=False
    )
    state_code = db.Column(db.String(255), nullable=False)
    country_id = db.Column(
        MEDIUMINT(unsigned=True), db.ForeignKey("countries.id"), nullable=False
    )
    country_code = db.Column(db.String(2), nullable=False)
    latitude = db.Column(db.Numeric(10, 8), nullable=False)
    longitude = db.Column(db.Numeric(11, 8), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime(2014, 1, 1, 6, 31, 1))
    updated_at = db.Column(
        db.DateTime,
        default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp(),
    )
    flag = db.Column(db.Boolean, nullable=False, default=True)
    wikiDataId = db.Column(db.String(255), comment="Rapid API GeoDB Cities")

    __table_args__ = (
        db.Index("cities_test_ibfk_1", "state_id"),
        db.Index("cities_test_ibfk_2", "country_id"),
    )
