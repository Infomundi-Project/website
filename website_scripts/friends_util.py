from sqlalchemy.exc import IntegrityError
from sqlalchemy import and_, or_
from datetime import datetime

from . import extensions, models


def send_friend_request(user_id: int, friend_id: int) -> int:
    """Sends a friendship request and returns the friendship id from the database."""
    # Check for an existing friendship record (pending or accepted), in either direction
    existing = models.Friendship.query.filter(
        or_(
            and_(
                models.Friendship.user_id == user_id,
                models.Friendship.friend_id == friend_id,
            ),
            and_(
                models.Friendship.user_id == friend_id,
                models.Friendship.friend_id == user_id,
            ),
        )
    ).first()

    if existing:
        if existing.status == "pending":
            # You’ve already got a pending request
            return existing.id
        if existing.status == "accepted":
            # You’re already friends!
            return existing.id

    # 3. Otherwise, create a new pending request
    friendship = models.Friendship(
        user_id=user_id, friend_id=friend_id, status="pending"
    )
    extensions.db.session.add(friendship)
    try:
        extensions.db.session.commit()
    except IntegrityError:
        extensions.db.session.rollback()
        # This could happen under concurrency as we have a unique constraint.
        existing = models.Friendship.query.filter_by(
            user_id=user_id, friend_id=friend_id
        ).first()
        return existing.id

    return friendship.id


def accept_friend_request(user_id: int, friend_id: int) -> bool:
    friendship = models.Friendship.query.filter_by(
        user_id=friend_id, friend_id=user_id, status="pending"
    ).first()
    if not friendship:
        return False

    friendship.status = "accepted"
    friendship.accepted_at = datetime.now()
    extensions.db.session.commit()
    return True


def accept_all_pending_requests(user_id: int) -> bool:
    pending_requests = models.Friendship.query.filter_by(
        friend_id=user_id, status="pending"
    ).all()

    for request in pending_requests:
        request.status = "accepted"

    extensions.db.session.commit()
    return True


def reject_friend_request(user_id: int, friend_id: int) -> bool:
    friendship = models.Friendship.query.filter_by(
        user_id=friend_id, friend_id=user_id, status="pending"
    ).first()
    if not friendship:
        return False

    extensions.db.session.delete(friendship)
    extensions.db.session.commit()
    return True


def reject_all_pending_requests(user_id: int) -> bool:
    # Find all pending friend requests where the user is the receiver
    pending_requests = models.Friendship.query.filter_by(
        friend_id=user_id, status="pending"
    ).all()

    for request in pending_requests:
        extensions.db.session.delete(request)

    extensions.db.session.commit()
    return True


def delete_friend(user_id: int, friend_id: int):
    friendship = models.Friendship.query.filter(
        extensions.db.or_(
            extensions.db.and_(
                models.Friendship.user_id == user_id,
                models.Friendship.friend_id == friend_id,
            ),
            extensions.db.and_(
                models.Friendship.user_id == friend_id,
                models.Friendship.friend_id == user_id,
            ),
        )
    ).first()
    if friendship:
        extensions.db.session.delete(friendship)
        extensions.db.session.commit()
        return True
    return False


def delete_all_friends(user_id: int) -> bool:
    # Delete friendships where the user is the requester
    friendships_sent = models.Friendship.query.filter_by(user_id=user_id).all()
    for friendship in friendships_sent:
        extensions.db.session.delete(friendship)

    # Delete friendships where the user is the receiver
    friendships_received = models.Friendship.query.filter_by(friend_id=user_id).all()
    for friendship in friendships_received:
        extensions.db.session.delete(friendship)

    extensions.db.session.commit()
    return True


def get_pending_friend_requests(user_id: int):
    return models.Friendship.query.filter_by(friend_id=user_id, status="pending").all()


def get_friends_list(user_id: int) -> list:
    """
        Returns the user's friends in a list.

        First, we are querying the friendships table by the user_id, which means that the user is whom sent the
    request. The way this is stored in the database is that the user's friend in this case is the user that accepted the request,
    so we get the friend data with [x.friend for ...].

        The opposite happens as well, as we only get the people that got a friend request from the user and
    accept it, and we still have to get the people whom sent the reuqest to the user and they accepted it. That's why we
    query the friendships table by the friend_id passing the user_id, and get the friend data with [x.user for ...].

    Arguments
        user_id (int): The user id.

    Returns
        list: A list containing data regarding the user's friends.
    """
    sent_friends = [
        x.friend
        for x in models.Friendship.query.filter_by(
            user_id=user_id, status="accepted"
        ).all()
    ]

    # The opposite happens here.
    received_friends = [
        x.user
        for x in models.Friendship.query.filter_by(
            friend_id=user_id, status="accepted"
        ).all()
    ]

    return sent_friends + received_friends


@extensions.cache.memoize(timeout=60 * 1)  # 1 minute
def get_friendship_status(user_id: int, friend_id: int) -> tuple:
    """
    Determines the friendship status between the current user and the profile user.

    Parameters:
        user_id (int): The user ID of the current user.
        friend_id (int): The user ID of the friend.

    Returns:
        tuple: A tuple containing the friendship status and a boolean indicating
               whether the current user has sent a pending friend request. E.g. ("pending", True)
    """
    # Initialize the pending friend request flag
    pending_friend_request_sent_by_current_user = False

    # Check if there is any friendship relation (sent or received) between the current user and the profile user
    friendship = models.Friendship.query.filter(
        or_(
            and_(
                models.Friendship.user_id == user_id,
                models.Friendship.friend_id == friend_id,
            ),
            and_(
                models.Friendship.user_id == friend_id,
                models.Friendship.friend_id == user_id,
            ),
        )
    ).first()

    if friendship and friendship.status == "pending":
        # Check if the pending request was sent by the current user
        pending_friend_request_sent_by_current_user = friendship.user_id == user_id

    return (
        friendship.status if friendship else "not_friends",
        pending_friend_request_sent_by_current_user,
    )
