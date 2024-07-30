import hashlib
import secrets
import time
from datetime import datetime, timedelta

from . import models, notifications, extensions
from .scripts import generate_id


def handle_register_token(email: str, hashed_email: str, username: str, hashed_password: str) -> bool:
    """Generates a verification token, stores in a json file and 
    uses notifications.send_email to send the verification token to the user.

    Args:
        email (str): User's email address.
        hashed_email (str): User's sha256 hashed email.
        username (str): User's username.
        hashed_password (str): User's argon2 hashed password.

    Returns:
        bool: False if there's a token associated with the email or if we couldn't get to send the email. Otherwise True.
    """
    token_lookup = models.RegisterToken.query.filter_by(email=email).first()
    
    # This means there's an already issued token for the specified email address.
    if token_lookup:
        return False

    # Generate a REEEEALLY random verification token.
    verification_token = hashlib.md5(secrets.token_bytes(32)).hexdigest()

    message = f"""Hello {username}, 

If you've received this message in error, feel free to disregard it. However, if you're here to verify your account, welcome to Infomundi! We've made it quick and easy for you, simply click on the following link to complete the verification process: 

https://infomundi.net/auth/verify?token={verification_token}

We're looking forward to seeing you explore our platform!

Best regards,
The Infomundi Team"""

    subject = 'Infomundi - Activate Your Account'
    
    # If we can send the email, save token to the database
    result = notifications.send_email(email, subject, message)
    if result:
        new_token = models.RegisterToken(email=hashed_email, username=username, 
            token=verification_token, user_id=generate_id(), password=hashed_password)
        extensions.db.session.add(new_token)
        extensions.db.session.commit()

    return result


def check_recovery_token(token: str) -> object:
    """Checks if the account recovery token is valid.

    Arguments:
        token (str): Account recovery token. MD5 hash.

    Returns:
        object: The user object. None if error.
    """
    user_lookup = models.User.query.filter_by(recovery_token=token).first()
    # Checks if there is any user associated with the specified token. If not, return False
    if not user_lookup:
        return None

    now = datetime.now()
    created_at = datetime.fromisoformat(user_lookup.recovery_token_timestamp.isoformat())
    
    # Checks if the token is expired. If it's expired, we clear it from the database, commit change and return False
    time_difference = now - created_at
    if time_difference > timedelta(minutes=30):
        user_lookup.recovery_token = None
        extensions.db.session.commit()
        return None

    # If passes the above checks, we clear from the database and return the user's sha256 hashed email address.
    user_lookup.in_recovery = True
    user_lookup.recovery_token = None
    extensions.db.session.commit()

    return user_lookup


def send_recovery_token(email: str, hashed_email: str) -> bool:
    """Tries to send the account recovery token to the user requesting account recovery.

    Args:
        email (str): The user's email address.
        hashed_email (str): The user's sha256 hashed email address.

    Returns:
        bool: True if user can proceed with account recovery. Otherwise, False.
    """
    user_lookup = models.User.query.filter_by(email=hashed_email).first()
    if not user_lookup:
        return False

    now = datetime.now()

    # If there's a token already issued to the user, check if it's expired. If expired, proceed. If not, return False.
    if user_lookup.recovery_token:
        created_at = datetime.fromisoformat(user_lookup.recovery_token_timestamp.isoformat())
        
        # Checks if the token is expired
        time_difference = now - created_at
        if time_difference < timedelta(minutes=30):
            return False

    # Generates a super random token.
    verification_token = hashlib.md5(secrets.token_bytes(32)).hexdigest()

    message = f"""Hello,

If you've received this message in error, feel free to disregard it. However, if you're here to recover your Infomundi account, feel free to click on the link below:

https://infomundi.net/auth/forgot_password?token={verification_token}

Please keep in mind that this token will expire in 30 minutes.

Best regards,
The Infomundi Team"""
    subject = 'Infomundi - Account Recovery'
    
    # If we get to send the email, save it to the tokens file.
    result = notifications.send_email(email, subject, message)
    if result:
        user_lookup.recovery_token = verification_token
        user_lookup.recovery_token_timestamp = now
        extensions.db.session.commit()
    # Sleeps for a random time in order to prevent user enumeration based on response time.
    time.sleep(uniform(1.0, 2.5))
    return result
