from flask_login import logout_user, login_user
from datetime import datetime, timedelta
from flask import session, request
from sqlalchemy import or_

from . import models, notifications, extensions, friends_util, security_util, hashing_util, qol_util, input_sanitization, cloudflare_util


def perform_login_actions(user, cleartext_email: str):
    # Save the timestamp of the last login
    user.last_login = datetime.now()
    extensions.db.session.commit()

    login_user(user, remember=session['remember_me'])
    
    session.permanent = True
    session['obfuscated_email_address'] = input_sanitization.obfuscate_email(cleartext_email)
    session['session_version'] = user.session_version
    session['email_address'] = cleartext_email

    message = f"""Hello, {user.username}.

It appears that someone has logged into your Infomundi account from a new device. But fear not, we have kept a watchful eye! Here are the details:

Device: {qol_util.get_device_info(request.headers.get('User-Agent'))}
IP Address: {cloudflare_util.get_user_ip()}
Country: {cloudflare_util.get_user_country()}

It's always wise to make sure that you recognize this login. If this was unexpected, it might be time to change your password.

Should you need to take any action, you can recover your account at: https://infomundi.net/auth/forgot_password

If you encounter any issues, please don't hesitate to contact our team for assistance at: https://infomundi.net/contact

Best regards,
The Infomundi Team
    """
    subject = 'Infomundi - Login From a New Device'
    notifications.send_email(cleartext_email, subject, message)


def configure_key(user, cleartext_password, cleartext_email: str = ''):
    """
    Here's the deal, when the user creates an account through Google, we don't know their cleartext password, ever.
    However, we still need to encrypt the TOTP secret if the user choses to enable 2FA authentication via TOTP. To make this work,
    we can use the user's cleartext email address, it's better than nothing, as the email itself is stored in hash format (argon2) in
    the database.

    We check to see if the user has a salt associated with their account, if they do, we generate their key and simply return. If they do not,
    we call the derive_key function without specifying the salt. This way, we'll get a random salt generated and the user's derived key based on
    the details (cleartext_password or cleartext_email) that we passed along. The salt is associated with the user and saved to the database, and we
    return the derived key as usual.

    Arguments:
        user (UserMixin): The user, so we can change/read value for them in the database
        cleartext_password (str): User's cleartext password
        cleartext_email (str): Optional. User's cleartext email.

    Returns:
        str: We return the user's key
    """
    if user.derived_key_salt:
        return security_util.derive_key(cleartext_email if cleartext_email else cleartext_password, user.derived_key_salt)

    # Return key salt and key value as the salt wasn't specified!
    key_salt, key_value = security_util.derive_key(cleartext_email if cleartext_email else cleartext_password)
    user.derived_key_salt = key_salt
    extensions.db.session.commit()
    
    return key_value



def handle_register_token(email: str, hashed_email: str, username: str, hashed_password: str) -> bool:
    """Generates a verification token, stores in the database and 
    uses notifications.send_email to send the verification token to the user.

    Arguments:
        email (str): User's email address.
        hashed_email (str): User's sha256 hashed email.
        username (str): User's username.
        hashed_password (str): User's argon2 hashed password.

    Returns:
        bool: False if there's a token associated with the email or if we couldn't get to send the email. Otherwise True.
    """
    token_lookup = models.RegisterToken.query.filter(or_(
        models.RegisterToken.email == hashed_email,
        models.RegisterToken.email == username
    )).first()
    
    # This means there's an already issued token for the specified email address.
    if token_lookup:
        created_at = datetime.fromisoformat(token_lookup.timestamp.isoformat())
        # If it's within the threshold, return False. Otherwise, delete the token.
        if qol_util.is_within_threshold_minutes(created_at, 30):
            return False
        
        extensions.db.session.delete(token_lookup)
        extensions.db.session.commit()

    # Generate a REEEEALLY random verification token.
    verification_token = security_util.generate_nonce(24)

    message = f"""Hello, {username}.

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
            token=verification_token, user_id=security_util.generate_nonce(10), password=hashed_password)
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

    created_at = datetime.fromisoformat(user_lookup.recovery_token_timestamp.isoformat())
    if not qol_util.is_within_threshold_minutes(created_at, 30):
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

    # If there's a token already issued to the user, check if it's expired. If expired, proceed. If not, return False.
    if user_lookup.recovery_token:
        created_at = datetime.fromisoformat(user_lookup.recovery_token_timestamp.isoformat())
        if not qol_util.is_within_threshold_minutes(created_at, 30):
            return False

    # Generates a super random token.
    verification_token = security_util.generate_nonce(24)

    message = f"""Hello.

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
        user_lookup.recovery_token_timestamp = datetime.now()
        extensions.db.session.commit()
    
    return result


def delete_account(email, token):
    hashed_email = hashing_util.sha256_hash_text(email)
    user = models.User.query.filter_by(email=hashed_email).first()

    # If the supplied token doesn't match the database record, return False.
    if user.delete_token != token:
        return False

    # Checks to see if the token is valid. If the token is invalid, deletes it and return False.
    created_at = datetime.fromisoformat(user.delete_token_timestamp.isoformat())
    if not qol_util.is_within_threshold_minutes(created_at, 30):
        user.delete_token = None
        extensions.db.session.commit()
        return False

    # Logout and delete user from database
    logout_user()
    friends_util.delete_all_friends(user.user_id)
    extensions.db.session.delete(user)
    extensions.db.session.commit()
    
    return True


def send_delete_token(email: str, current_password: str) -> bool:
    hashed_email = hashing_util.sha256_hash_text(email)
    user = models.User.query.filter_by(email=hashed_email).first()

    if not user.check_password(current_password):
        return False

    token = security_util.generate_nonce(24)
    
    subject = "Infomundi - Confirm Account Deletion"
    message = f"""Hello, {user.display_name if user.display_name else user.username}.

If you've received this message in error, feel free to disregard it. However, if you're here to delete your Infomundi account, feel free to click on the link below:

https://infomundi.net/auth/delete?token={token}

This link will expire in 30 minutes. Please, keep in mind that this action is permanent and your account data can't be recovered afterwards.

We're sorry to see you go.

Best regards,
The Infomundi Team"""
        
    result = notifications.send_email(email, subject, message)
    if not result:
        return False

    # Saves delete token information
    user.delete_token = token
    user.delete_token_timestamp = datetime.now()
    extensions.db.session.commit()

    return True
