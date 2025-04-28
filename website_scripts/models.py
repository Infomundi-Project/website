from datetime import datetime, timedelta
from flask_login import UserMixin

from .extensions import db
from . import security_util, hashing_util


class Publisher(db.Model):
    __tablename__ = 'publishers'
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    
    url = db.Column(db.String(200), nullable=False)

    name = db.Column(db.String(120), nullable=False)
    favicon_url = db.Column(db.String(100), nullable=True)


class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    name = db.Column(db.String(15), nullable=False, unique=True)
    

class Tag(db.Model):
    __tablename__ = 'tags'
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    tag = db.Column(db.String(30), nullable=False, unique=True)


class Story(db.Model):
    __tablename__ = 'stories'
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)

    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.String(500), nullable=False, default='No description has been provided.')
    gpt_summary = db.Column(db.JSON)

    url = db.Column(db.String(512), nullable=False)
    url_hash = db.Column(db.LargeBinary(16), nullable=False, unique=True)

    pub_date = db.Column(db.DateTime, nullable=False)
    image_url = db.Column(db.String(100))
    has_image = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    publisher_id = db.Column(db.Integer, db.ForeignKey('publishers.id'), nullable=False)

    # Relationships
    reactions = db.relationship('StoryReaction', backref='story', lazy=True)
    stats = db.relationship('StoryStats', backref='story', uselist=False, lazy='joined')
    category = db.relationship('Category', backref='story')
    publisher = db.relationship('Publisher', backref='story')


class StoryReaction(db.Model):
    __tablename__ = 'story_reactions'
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    
    story_id = db.Column(db.Integer, db.ForeignKey('stories.id', ondelete='CASCADE'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'))

    action = db.Column(db.String(10))  # 'like' or 'dislike'
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp())

    __table_args__ = (db.UniqueConstraint('story_id', 'user_id', 'action', name='unique_reaction'),)


class StoryStats(db.Model):
    __tablename__ = 'story_stats'
    story_id = db.Column(db.Integer, db.ForeignKey('stories.id', ondelete='CASCADE'), primary_key=True)

    dislikes = db.Column(db.Integer, default=0)
    views = db.Column(db.Integer, default=0)
    likes = db.Column(db.Integer, default=0)


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    public_id = db.Column(db.LargeBinary(16), nullable=False, unique=True)
    
    # User Account Data
    username = db.Column(db.String(25), nullable=False, unique=True)
    email_fingerprint = db.Column(db.LargeBinary(32), nullable=False, unique=True)  # SHA-256 + HMAC
    email_encrypted = db.Column(db.LargeBinary(120), nullable=False)  # AES-GCM

    role = db.Column(db.String(15), default='user')
    password = db.Column(db.String(150), nullable=False)
    session_version = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    last_login = db.Column(db.DateTime)

    # Profile
    display_name = db.Column(db.String(40))
    profile_description = db.Column(db.String(1500))
    avatar_url = db.Column(db.String(80), default='https://infomundi.net/static/img/avatar.webp')
    profile_banner_url = db.Column(db.String(80))
    profile_wallpaper_url = db.Column(db.String(80))
    level = db.Column(db.Integer, default=0)
    level_progress = db.Column(db.Integer, default=0)

    # Account Registration
    is_enabled = db.Column(db.Boolean, default=False)
    register_token = db.Column(db.LargeBinary(16))
    register_token_timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())

    # Account Recovery
    in_recovery = db.Column(db.Boolean, default=False)
    recovery_token = db.Column(db.LargeBinary(16))
    recovery_token_timestamp = db.Column(db.DateTime)

    # Account Deletion
    delete_token = db.Column(db.LargeBinary(16))
    delete_token_timestamp = db.Column(db.DateTime)

    # Activity
    is_online = db.Column(db.Boolean, default=False)
    last_activity = db.Column(db.DateTime)

    # Totp
    is_totp_enabled = db.Column(db.Boolean, default=False)
    totp_secret = db.Column(db.String(120))  # AES/GCM

    totp_recovery = db.Column(db.String(150))  # Argon2id
    
    is_mail_twofactor_enabled = db.Column(db.Boolean, default=False)
    mail_twofactor_code = db.Column(db.Integer)
    mail_twofactor_timestamp = db.Column(db.DateTime)


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


    def check_password(self, password: str) -> bool:
        return hashing_util.argon2_verify_hash(self.password, password)


    def get_id(self):
        return str(self.id)


    def get_public_id(self):
        return security_util.uuid_bytes_to_string(self.public_id)


    def purge_totp(self):
        self.totp_secret = None
        self.totp_recovery = None
        db.session.commit()


    def check_is_online(self):
        now = datetime.utcnow()
        online_threshold = timedelta(minutes=3)
        
        self.is_online = (now - self.last_activity) <= online_threshold
        db.session.commit()

        return self.is_online
    

class Friendship(db.Model):
    __tablename__ = 'friendships'
    id = db.Column(db.Integer, primary_key=True)
    
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    # Statuses are 'pending', 'accepted', 'rejected'.
    status = db.Column(db.String(10), nullable=False, default='pending')
    accepted_at = db.Column(db.DateTime)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    friend_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    __table_args__ = (db.UniqueConstraint('user_id', 'friend_id', name='unique_friendship'),)

    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('user_friendships', lazy='dynamic'))
    friend = db.relationship('User', foreign_keys=[friend_id], backref=db.backref('friend_friendships', lazy='dynamic'))


class SiteStatistics(db.Model):
    __tablename__ = 'site_statistics'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    last_updated_message = db.Column(db.String(15), nullable=False)
    total_countries_supported = db.Column(db.Integer, nullable=False)
    total_news = db.Column(db.Integer, nullable=False)
    total_feeds = db.Column(db.Integer, nullable=False)
    total_users = db.Column(db.Integer, nullable=False)
    total_comments = db.Column(db.Integer, nullable=False)
    total_clicks = db.Column(db.Integer, nullable=False)


class Comment(db.Model):
    __tablename__ = 'comments'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Unique page identifier (MD5)
    page_hash = db.Column(db.LargeBinary(16), nullable=False)

    # Commeting user
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    # Save story id if it's a story
    story_id = db.Column(db.Integer, db.ForeignKey('stories.id', ondelete='SET NULL'), nullable=True)

    # Means it's a reply
    parent_id = db.Column(db.Integer, db.ForeignKey('comments.id', ondelete='CASCADE'), nullable=True)

    content = db.Column(db.String(1000), nullable=False)
    is_flagged = db.Column(db.Boolean, default=False)
    is_edited = db.Column(db.Boolean, default=False)
    is_deleted = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    replies = db.relationship('Comment', backref=db.backref('parent', remote_side=[id]), lazy='dynamic', cascade='all, delete-orphan')
    reactions = db.relationship('CommentReaction', backref='comment', lazy='dynamic')
    user = db.relationship('User', backref='comments')


class CommentReaction(db.Model):
    __tablename__ = 'comment_reactions'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    comment_id = db.Column(db.Integer, db.ForeignKey('comments.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)

    action = db.Column(db.String(10), nullable=False)  # 'like' or 'dislike'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('comment_id', 'user_id', name='unique_comment_reaction'),)


class Stocks(db.Model):
    __tablename__ = 'stocks'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    country_name = db.Column(db.String(40), nullable=False)
    data = db.Column(db.JSON, nullable=False)


class Currencies(db.Model):
    __tablename__ = 'currencies'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    data = db.Column(db.JSON, nullable=False)


class Crypto(db.Model):
    __tablename__ = 'crypto'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    data = db.Column(db.JSON, nullable=False)


class Region(db.Model):
    __tablename__ = 'regions'
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    translations = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=None)
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())
    flag = db.Column(db.Boolean, default=True)
    wikiDataId = db.Column(db.String(255), comment='Rapid API GeoDB Cities')

    subregions = db.relationship('Subregion', backref='parent_region', lazy=True)
    countries = db.relationship('Country', backref='region', lazy=True)


class Subregion(db.Model):
    __tablename__ = 'subregions'
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    translations = db.Column(db.Text)
    region_id = db.Column(db.Integer, db.ForeignKey('regions.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=None)
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())
    flag = db.Column(db.Boolean, default=True)
    wikiDataId = db.Column(db.String(255), comment='Rapid API GeoDB Cities')

    countries = db.relationship('Country', backref='subregion', lazy=True)


class Country(db.Model):
    __tablename__ = 'countries'
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
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
    region_id = db.Column(db.Integer, db.ForeignKey('regions.id'), nullable=True)
    subregion_id = db.Column(db.Integer, db.ForeignKey('subregions.id'), nullable=True)
    nationality = db.Column(db.String(255))
    timezones = db.Column(db.Text)
    translations = db.Column(db.Text)
    latitude = db.Column(db.Numeric(10, 8))
    longitude = db.Column(db.Numeric(11, 8))
    emoji = db.Column(db.String(191))
    emojiU = db.Column(db.String(191))
    created_at = db.Column(db.DateTime, default=None)
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())
    flag = db.Column(db.Boolean, default=True)
    wikiDataId = db.Column(db.String(255), comment='Rapid API GeoDB Cities')

    states = db.relationship('State', backref='country', lazy=True)
    cities = db.relationship('City', backref='country', lazy=True)


class State(db.Model):
    __tablename__ = 'states'
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    country_id = db.Column(db.Integer, db.ForeignKey('countries.id'), nullable=False)
    country_code = db.Column(db.String(2), nullable=False)
    fips_code = db.Column(db.String(255))
    iso2 = db.Column(db.String(255))
    type = db.Column(db.String(191))
    latitude = db.Column(db.Numeric(10, 8))
    longitude = db.Column(db.Numeric(11, 8))
    created_at = db.Column(db.DateTime, default=None)
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())
    flag = db.Column(db.Boolean, default=True)
    wikiDataId = db.Column(db.String(255), comment='Rapid API GeoDB Cities')

    cities = db.relationship('City', backref='state', lazy=True)


class City(db.Model):
    __tablename__ = 'cities'
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    state_id = db.Column(db.Integer, db.ForeignKey('states.id'), nullable=False)
    state_code = db.Column(db.String(255), nullable=False)
    country_id = db.Column(db.Integer, db.ForeignKey('countries.id'), nullable=False)
    country_code = db.Column(db.String(2), nullable=False)
    latitude = db.Column(db.Numeric(10, 8), nullable=False)
    longitude = db.Column(db.Numeric(11, 8), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime(2014, 1, 1, 6, 31, 1))
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())
    flag = db.Column(db.Boolean, default=True)
    wikiDataId = db.Column(db.String(255), comment='Rapid API GeoDB Cities')
