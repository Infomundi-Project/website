import uuid
from sqlalchemy.ext.hybrid import hybrid_property
from datetime import datetime, timedelta
from flask_login import UserMixin

from .extensions import db
from .hashing_util import string_to_argon2_hash, argon2_verify_hash


class Publisher(db.Model):
    __tablename__ = 'publishers'
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    
    url = db.Column(db.String(200), nullable=False)

    name = db.Column(db.String(120), nullable=False)
    favicon_url = db.Column(db.String(100), nullable=True)
    
    stories = db.relationship('Story', backref='publisher', lazy=True)


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
    description = db.Column(db.String(500))
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
    stats = db.relationship('StoryStats', backref='story', lazy=True)


class StoryReaction(db.Model):
    __tablename__ = 'story_reactions'
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    
    story_id = db.Column(db.Integer, db.ForeignKey('stories.id'))
    user_id = db.Column(db.LargeBinary(16), db.ForeignKey('users.id'))

    action = db.Column(db.String(10))  # 'like' or 'dislike'
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp())

    __table_args__ = (db.UniqueConstraint('story_id', 'user_id', 'action', name='unique_reaction'),)


class StoryStats(db.Model):
    __tablename__ = 'story_stats'
    story_id = db.Column(db.Integer, db.ForeignKey('stories.id', ondelete='CASCADE'), primary_key=True)

    dislikes = db.Column(db.Integer, default=0)
    clicks = db.Column(db.Integer, default=0)
    likes = db.Column(db.Integer, default=0)


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    public_id = db.Column(db.LargeBinary(16), unique=True, default=lambda: uuid.uuid4().bytes)
    
    # Really important stuff
    username = db.Column(db.String(25), nullable=False, unique=True)
    hashed_email = db.Column(db.LargeBinary(32), nullable=False, unique=True) # SHA-256 hash

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

    # Account registration
    is_active = db.Column(db.Boolean, default=False)
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
    totp_secret = db.Column(db.String(120))
    totp_recovery = db.Column(db.String(120))
    mail_twofactor = db.Column(db.Integer)
    mail_twofactor_timestamp = db.Column(db.DateTime)

    # Encryption
    derived_key_salt = db.Column(db.String(120))

    @hybrid_property
    def public_id(self):
        return str(uuid.UUID(bytes=self.public_id))

    def set_password(self, password: str):
        self.password = string_to_argon2_hash(password)


    def check_password(self, password: str) -> bool:
        """Checks to see if the cleartext password matches the user's password hash

        Arguments
            self: We'll get user's password hash out of this (as stored in the database)
            password (str): Cleartext password we want to compare
        
        Returns
            bool: True if password is valid, otherwise False.
        """
        return argon2_verify_hash(self.password, password)


    def get_id(self):
        return str(self.id)


    def purge_totp(self):
        self.totp_secret = None
        self.totp_recovery = None


    def purge_key(self):
        self.derived_key_salt = None


    def check_is_online(self):
        now = datetime.utcnow()
        online_threshold = timedelta(minutes=3)
        
        self.is_online = (now - self.last_activity) <= online_threshold
        db.session.commit()

        return self.is_online
    

class CommonPasswords(db.Model):
    __tablename__ = 'common_passwords'
    
    id = db.Column(db.Integer, primary_key=True)
    password = db.Column(db.String(30), nullable=False)


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


class GlobalSalts(db.Model):
    __tablename__ = 'global_salts'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    salt = db.Column(db.String(64), nullable=False)


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
