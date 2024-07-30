from .extensions import db
from .models import Friendship, User


def send_friend_request(user_id, friend_id):
    friendship = Friendship(user_id=user_id, friend_id=friend_id, status='pending')
    db.session.add(friendship)
    db.session.commit()
    
    return True


def accept_friend_request(user_id: str, friend_id: str, all_requests: bool=False) -> bool:
    if all_requests:
        friendship = Friendship.query.filter_by(user_id=friend_id, friend_id=user_id, status='pending').all()
        

    friendship = Friendship.query.filter_by(user_id=friend_id, friend_id=user_id, status='pending').first()
    if friendship:
        friendship.status = 'accepted'
        db.session.commit()
        return True

    return False


def reject_friend_request(user_id, friend_id):
    friendship = Friendship.query.filter_by(user_id=friend_id, friend_id=user_id, status='pending').first()
    if friendship:
        db.session.delete(friendship)
        #friendship.status = 'rejected'
        db.session.commit()
        return True

    return False


def get_pending_friend_requests(user_id):
    return Friendship.query.filter_by(friend_id=user_id, status='pending').all()


def get_friends_list(user_id):
    friends = Friendship.query.filter_by(user_id=user_id, status='accepted').all()
    if not friends:
        friends = Friendship.query.filter_by(friend_id=user_id, status='accepted').all()
    
    return friends


def delete_friend(user_id, friend_id):
    friendship = Friendship.query.filter(
        db.or_(
            db.and_(Friendship.user_id == user_id, Friendship.friend_id == friend_id),
            db.and_(Friendship.user_id == friend_id, Friendship.friend_id == user_id)
        )
    ).first()
    if friendship:
        db.session.delete(friendship)
        db.session.commit()
        return True
    return False