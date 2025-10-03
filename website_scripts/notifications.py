from email.mime.multipart import MIMEMultipart
from requests import post as post_request
from email.mime.text import MIMEText
from email.utils import formatdate
from sqlalchemy import insert

from smtplib import SMTP

from . import config, extensions, models
from .custom_exceptions import InfomundiCustomException


def post_webhook(text: str = "", data: dict = {}) -> bool:
    """Takes 'data' dictionary as argument, and posts to the mattermost webhook. Returns bool.

    Arguments:
        data: dict
            Information needed to create the embed message. Should have the following structure:
            {
                'content': 'some text'
            }

    Returns:
        bool: True if we were able to POST the webhook, otherwise False.
    """
    if not text and not data:
        raise InfomundiCustomException("Either text or data is required")

    if text:
        data = {"content": text}

    try:
        response = post_request(config.WEBHOOK_URL, timeout=3, json=data)
        response.raise_for_status()
    except Exception as e:
        raise InfomundiCustomException(f"Something went wrong: {e}")

    return True


def notify(notif_dicts: list):
    """Creates a Notification for specified users in the data

    Types allowed: ("default", "new_comment", "comment_reply", "comment_reaction", "friend_request", "friend_accepted", "friend_status", "mentions", "security", "profile_edit")

    Args:
        notif_dicts: list
            List of dicts containing info regarding the notifications to be added to the database. e.g.
            [
                {"user_id": user_id, "type": type, "message": message, "url": url}, { ... }
            ]
    """
    types_allowed = (
        "default",
        "new_comment",
        "comment_reply",
        "comment_reaction",
        "friend_request",
        "friend_accepted",
        "friend_status",
        "mentions",
        "security",
        "profile_edit",
    )
    for n in notif_dicts:
        if n.get("user_id") is None:
            break

        if n.get("type") not in types_allowed:
            raise InfomundiCustomException(
                f"'type' value is invalid. Types allowed: {types_allowed}"
            )
    else:
        extensions.db.session.execute(insert(models.Notification), notif_dicts)
        extensions.db.session.commit()


def notify_single(user_id: int, type: str, message: str, **fk_kwargs):
    """
    Create-and-commit a Notification for a user,
    but first check if an unread one already exists.
    """
    types_allowed = (
        "default",
        "new_comment",
        "comment_reply",
        "comment_reaction",
        "friend_request",
        "friend_accepted",
        "friend_status",
        "mentions",
        "security",
        "profile_edit",
    )

    if type not in types_allowed:
        raise InfomundiCustomException(
            f"Type should be one of {' '.join(types_allowed)}"
        )

    filters = {
        "user_id": user_id,
        "type": type,
        "is_read": False,
        **fk_kwargs,
    }

    existing = (
        extensions.db.session.query(models.Notification).filter_by(**filters).first()
    )
    if existing:
        # We already have a pending one—just return it.
        return existing

    # Otherwise, create & commit a fresh notification
    n = models.Notification(user_id=user_id, type=type, message=message, **fk_kwargs)
    extensions.db.session.add(n)
    extensions.db.session.commit()
    return n


def send_email(
    recipient_email: str,
    subject: str,
    body: str,
    reply_to: str = "noreply@infomundi.net",
    from_email: str = "Infomundi <noreply@infomundi.net>",
) -> bool:
    """Takes the recipient email, the subject and the body of the email and sends it.

    Arguments:
        recipient_email: str
            Email address to send message to
        subject: str
            Email's subject
        body: str
            Email's message
        reply_to: str
            Reply-To address. Defaults to 'noreply@infomundi.net'

    Returns:
        bool: True if we were able to send the message, otherwise False.
    """

    # Create a message
    message = MIMEMultipart()
    message["From"] = from_email
    message["To"] = recipient_email
    message["Subject"] = subject
    message["Date"] = formatdate(localtime=True)

    if reply_to != from_email:
        message["Reply-To"] = reply_to

    message.attach(MIMEText(body, "plain"))

    try:
        with SMTP(config.SMTP_SERVER, config.SMTP_PORT) as server:
            server.starttls()  # Upgrade the connection to secure TLS
            server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)

            # Send the email
            server.sendmail(config.SMTP_USERNAME, recipient_email, message.as_string())
    except Exception:
        return False

    return True
