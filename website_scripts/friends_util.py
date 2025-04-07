from .extensions import db
from .models import Friendship


def send_friend_request(user_id, friend_id):
    friendship = Friendship(user_id=user_id, friend_id=friend_id, status='pending')
    db.session.add(friendship)
    db.session.commit()
    
    return True


def accept_friend_request(user_id: str, friend_id: str) -> bool:
    friendship = Friendship.query.filter_by(user_id=friend_id, friend_id=user_id, status='pending').first()
    if not friendship:
        return False

    friendship.status = 'accepted'
    db.session.commit()
    return True


def accept_all_pending_requests(user_id: str) -> bool:
    # Find all pending friend requests where the user is the receiver
    pending_requests = Friendship.query.filter_by(friend_id=user_id, status='pending').all()
    
    # Accept each pending request
    for request in pending_requests:
        request.status = 'accepted'
    
    db.session.commit()


def reject_friend_request(user_id: str, friend_id: str) -> bool:
    friendship = Friendship.query.filter_by(user_id=friend_id, friend_id=user_id, status='pending').first()
    if not friendship:
        return False

    db.session.delete(friendship)
    db.session.commit()
    return True


def reject_all_pending_requests(user_id: str) -> bool:
    # Find all pending friend requests where the user is the receiver
    pending_requests = Friendship.query.filter_by(friend_id=user_id, status='pending').all()
    if not pending_requests:
        return False
    
    # Delete each pending request
    for request in pending_requests:
        db.session.delete(request)
    
    db.session.commit()
    return True


def delete_friend(user_id: str, friend_id: str):
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


def delete_all_friends(user_id: str) -> bool:
    # Delete friendships where the user is the requester
    friendships_sent = Friendship.query.filter_by(user_id=user_id).all()
    for friendship in friendships_sent:
        db.session.delete(friendship)
    
    # Delete friendships where the user is the receiver
    friendships_received = Friendship.query.filter_by(friend_id=user_id).all()
    for friendship in friendships_received:
        db.session.delete(friendship)
    
    db.session.commit()
    return True


def get_pending_friend_requests(user_id: str):
    return Friendship.query.filter_by(friend_id=user_id, status='pending').all()


def get_friends_list(user_id: str) -> list:
    """
        Returns the user's friends in a list.

        First, we are querying the friendships table by the user_id, which means that the user is whom sent the 
    request. The way this is stored in the database is that the user's friend in this case is the user that accepted the request,
    so we get the friend data with [x.friend for ...].

        The opposite happens as well, as we only get the people that got a friend request from the user and 
    accept it, and we still have to get the people whom sent the reuqest to the user and they accepted it. That's why we
    query the friendships table by the friend_id passing the user_id, and get the friend data with [x.user for ...].

    Arguments
        user_id (str): The user id.

    Returns
        list: A list containing data regarding the user's friends.
    """
    sent_friends = [x.friend for x in Friendship.query.filter_by(user_id=user_id, status='accepted').all()]
    
    # The opposite happens here.
    received_friends = [x.user for x in Friendship.query.filter_by(friend_id=user_id, status='accepted').all()]

    return sent_friends + received_friends


def get_friendship_status(current_user_id: str, profile_user_id: str) -> tuple:
    """
    Determines the friendship status between the current user and the profile user.
    
    Parameters:
        current_user_id (str): The user ID of the current user.
        profile_user_id (str): The user ID of the profile user.

    Returns:
        tuple: A tuple containing the friendship status and a boolean indicating
               whether the current user has sent a pending friend request.
    """
    # Initialize the pending friend request flag
    pending_friend_request_sent_by_current_user = False

    # Check if there is any friendship relation (sent or received) between the current user and the profile user
    friendship = Friendship.query.filter(
        db.or_(
            db.and_(Friendship.user_id == current_user_id, Friendship.friend_id == profile_user_id),
            db.and_(Friendship.user_id == profile_user_id, Friendship.friend_id == current_user_id)
        )
    ).first()

    if friendship and friendship.status == 'pending':
        # Check if the pending request was sent by the current user
        pending_friend_request_sent_by_current_user = friendship.user_id == current_user_id
    
    return (friendship.status if friendship else 'not_friends', pending_friend_request_sent_by_current_user)
