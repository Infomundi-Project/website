from flask_login import UserMixin
from passlib.hash import argon2

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
