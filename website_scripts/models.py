from flask_login import UserMixin
from passlib.hash import argon2
from datetime import datetime

from .extensions import db


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    user_id = db.Column(db.String(10), primary_key=True)
    username = db.Column(db.String(30), nullable=False, unique=True)
    password = db.Column(db.String(50), nullable=False)
    role = db.Column(db.String(15), nullable=True)
    email = db.Column(db.String(50), unique=True, nullable=False)
    avatar_url = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    def set_password(self, password):
        self.password = argon2.hash(password)

    def check_password(self, password):
        return argon2.verify(password, self.password)

    def get_id(self):
        return str(self.user_id)


class Comment(db.Model):
    __tablename__ = 'comments'
    comment_id = db.Column(db.String(10), primary_key=True)
    user_id = db.Column(db.String(10), db.ForeignKey('users.user_id'))
    news_id = db.Column(db.String(35))
    parent_comment_id = db.Column(db.String(10), db.ForeignKey('comments.comment_id'), nullable=True)
    text = db.Column(db.Text, nullable=False)
    is_root_comment = db.Column(db.Boolean, nullable=False)
    likes = db.Column(db.Integer, default=0)
    dislikes = db.Column(db.Integer, default=0)
    reports = db.Column(db.Integer, default=0)
    timestamp = db.Column(db.String(30), nullable=False)

    # Relationships
    user = db.relationship('User', backref='comments')
    replies = db.relationship('Comment', backref=db.backref('parent', remote_side=[comment_id]), lazy='dynamic')


class CommentReaction(db.Model):
    __tablename__ = 'comment_reactions'
    reaction_id = db.Column(db.String(12), primary_key=True)
    comment_id = db.Column(db.String(10), db.ForeignKey('comments.comment_id'))
    user_id = db.Column(db.String(10), db.ForeignKey('users.user_id'))
    action = db.Column(db.Enum('like', 'dislike', 'report'))
    timestamp = db.Column(db.String(30), nullable=False)

    # Unique constraint to prevent multiple reactions from the same user to the same comment
    __table_args__ = (db.UniqueConstraint('comment_id', 'user_id', 'action', name='unique_reaction'),)


# Stories-related Models


class Publisher(db.Model):
    __tablename__ = 'publishers'
    publisher_id = db.Column(db.String(40), primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    link = db.Column(db.String(512), nullable=False)
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
    story_id = db.Column(db.String(40), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    gpt_summary = db.Column(db.JSON)
    clicks = db.Column(db.Integer, default=0)
    link = db.Column(db.String(512), nullable=False)
    pub_date = db.Column(db.String(30), nullable=False)
    category_id = db.Column(db.String(20), db.ForeignKey('categories.category_id'), nullable=False)
    publisher_id = db.Column(db.String(40), db.ForeignKey('publishers.publisher_id'), nullable=False)
    media_content_url = db.Column(db.String(255))

    # Relationships
    reactions = db.relationship('StoryReaction', backref='story', lazy=True)


class StoryReaction(db.Model):
    __tablename__ = 'story_reactions'
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    story_id = db.Column(db.String(40), db.ForeignKey('stories.story_id'))
    user_id = db.Column(db.String(10))  # This should reference the 'users' table if it exists
    action = db.Column(db.String(10))  # 'like' or 'dislike'
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp())

    __table_args__ = (db.UniqueConstraint('story_id', 'user_id', 'action', name='unique_reaction'),)