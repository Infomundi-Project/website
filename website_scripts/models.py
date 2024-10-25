from flask_login import UserMixin
from datetime import datetime

from .extensions import db
from .hashing_util import argon2_hash_text, argon2_verify_hash


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    # Really important stuff
    username = db.Column(db.String(25), nullable=False, unique=True)
    email = db.Column(db.String(128), nullable=False, unique=True) # SHA-512 hashed email
    user_id = db.Column(db.String(20), primary_key=True)
    role = db.Column(db.String(15), default='user')
    password = db.Column(db.String(150), nullable=False)
    session_version = db.Column(db.Integer, default=0)

    # Timestamps
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    last_login = db.Column(db.DateTime)

    # Profile Customization
    display_name = db.Column(db.String(40))
    avatar_url = db.Column(db.String(80))
    profile_description = db.Column(db.String(1500))
    profile_banner_url = db.Column(db.String(80))
    profile_wallpaper_url = db.Column(db.String(80))
    level = db.Column(db.Integer, default=0)
    level_progress = db.Column(db.Integer, default=0)

    # Account Recovery
    in_recovery = db.Column(db.Boolean, default=False)
    recovery_token = db.Column(db.String(40))
    recovery_token_timestamp = db.Column(db.DateTime)

    # Account Deletion
    delete_token = db.Column(db.String(40))
    delete_token_timestamp = db.Column(db.DateTime)

    # Is Online?
    is_online = db.Column(db.Boolean, default=False)
    last_activity = db.Column(db.DateTime)

    # Totp
    totp_secret = db.Column(db.String(120))
    totp_recovery = db.Column(db.String(120))

    # Email 2fa token
    mail_twofactor = db.Column(db.String(6))
    mail_twofactor_timestamp = db.Column(db.DateTime)

    # Derived key
    derived_key_salt = db.Column(db.String(120))

    # IP History
    ip_history = db.relationship('UserIPHistory', back_populates='user', cascade='all, delete-orphan')

    # This is only used in certain circumnstances
    cleartext_email = db.Column(db.String(80))


    def set_password(self, password):
        self.password = argon2_hash_text(password)


    def check_password(self, password: str) -> bool:
        """Checks to see if the cleartext password matches the user's password hash

        Arguments
            self: We'll get user's password hash out of this (as stored in the database)
            password (str): Cleartext password we want to compare
        
        Returns
            bool: True if password is valid, otherwise False.
        """
        return argon2_verify_hash(self.password, password)


    def set_email(self, email):
        self.email = argon2_hash_text(email)


    def get_id(self):
        return str(self.user_id)


    def purge_totp(self):
        self.totp_secret = None
        self.totp_recovery = None


    def purge_key(self):
        self.derived_key_salt = None


    def add_ip_history(self, ip_address, user_agent):
        """Add an entry to the IP history for this user."""
        new_ip_history = UserIPHistory(user_id=self.user_id, ip_address=ip_address, user_agent=user_agent)
        db.session.add(new_ip_history)
        db.session.commit()
    


class CommonPasswords(db.Model):
    __tablename__ = 'common_passwords'
    
    id = db.Column(db.Integer, primary_key=True)
    password = db.Column(db.String(30), nullable=False)


class UserIPHistory(db.Model):
    __tablename__ = 'user_ip_history'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(20), db.ForeignKey('users.user_id'), nullable=False)
    ip_address = db.Column(db.String(45), nullable=False)
    access_time = db.Column(db.DateTime, default=db.func.current_timestamp())
    user_agent = db.Column(db.String(255))

    user = db.relationship('User', back_populates='ip_history')


class RegisterToken(db.Model):
    __tablename__ = 'register_tokens'
    user_id = db.Column(db.String(20), primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    username = db.Column(db.String(25), nullable=False, unique=True)
    password = db.Column(db.String(150), nullable=False)

    token = db.Column(db.String(40), nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())


class Publisher(db.Model):
    __tablename__ = 'publishers'
    publisher_id = db.Column(db.String(40), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    link = db.Column(db.String(120), nullable=False)
    favicon = db.Column(db.String(100), nullable=True)
    stories = db.relationship('Story', backref='publisher', lazy=True)


class Category(db.Model):
    __tablename__ = 'categories'
    category_id = db.Column(db.String(15), primary_key=True)
    tags = db.relationship('Tag', secondary='category_tags', back_populates='categories')


class Tag(db.Model):
    __tablename__ = 'tags'
    tag_id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    tag = db.Column(db.String(30), nullable=False, unique=True)
    categories = db.relationship('Category', secondary='category_tags', back_populates='tags')


class CategoryTag(db.Model):
    __tablename__ = 'category_tags'
    category_id = db.Column(db.String(15), db.ForeignKey('categories.category_id'), primary_key=True)
    tag_id = db.Column(db.Integer, db.ForeignKey('tags.tag_id'), primary_key=True)


class Story(db.Model):
    __tablename__ = 'stories'
    story_id = db.Column(db.String(40), primary_key=True) # should be 32
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(500))
    gpt_summary = db.Column(db.JSON)
    clicks = db.Column(db.Integer, default=0)
    link = db.Column(db.String(512), nullable=False)
    pub_date = db.Column(db.String(30), nullable=False)
    category_id = db.Column(db.String(20), db.ForeignKey('categories.category_id'), nullable=False)
    publisher_id = db.Column(db.String(40), db.ForeignKey('publishers.publisher_id'), nullable=False)
    media_content_url = db.Column(db.String(100))
    has_media_content = db.Column(db.Boolean, default=False)

    # Relationships
    reactions = db.relationship('StoryReaction', backref='story', lazy=True)


class StoryReaction(db.Model):
    __tablename__ = 'story_reactions'
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    story_id = db.Column(db.String(40), db.ForeignKey('stories.story_id'))
    user_id = db.Column(db.String(10), db.ForeignKey('users.user_id'))
    action = db.Column(db.String(10))  # 'like' or 'dislike'
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp())

    __table_args__ = (db.UniqueConstraint('story_id', 'user_id', 'action', name='unique_reaction'),)


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


class Friendship(db.Model):
    __tablename__ = 'friendships'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(20), db.ForeignKey('users.user_id'), nullable=False)
    friend_id = db.Column(db.String(20), db.ForeignKey('users.user_id'), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    status = db.Column(db.String(10), nullable=False, default='pending')  # Status: 'pending', 'accepted', 'rejected'

    __table_args__ = (db.UniqueConstraint('user_id', 'friend_id', name='unique_friendship'),)

    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('user_friendships', lazy='dynamic'))
    friend = db.relationship('User', foreign_keys=[friend_id], backref=db.backref('friend_friendships', lazy='dynamic'))


class SiteStatistics(db.Model):
    __tablename__ = 'site_statistics'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    total_countries_supported = db.Column(db.Integer, nullable=False)
    current_time = db.Column(db.DateTime, nullable=False)
    now = db.Column(db.DateTime, nullable=False)
    total_news = db.Column(db.String(15), nullable=False)
    total_feeds = db.Column(db.Integer, nullable=False)
    total_users = db.Column(db.Integer, nullable=False)
    total_comments = db.Column(db.Integer, nullable=False)
    last_updated_message = db.Column(db.String(15), nullable=False)
    total_clicks = db.Column(db.BigInteger, nullable=False)


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
