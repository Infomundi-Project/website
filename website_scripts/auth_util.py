from flask import session, request, make_response, url_for, redirect
from flask_login import logout_user, login_user
from datetime import datetime
from sqlalchemy import or_

from . import (
    models,
    notifications,
    extensions,
    friends_util,
    security_util,
    hashing_util,
    qol_util,
    input_sanitization,
    cloudflare_util,
    config,
)


def search_user_email_in_database(email: str):
    return models.User.query.filter_by(
        email_fingerprint=hashing_util.generate_hmac_signature(email, as_bytes=True)
    ).first()


def perform_login_actions(user, cleartext_email: str):
    user.last_login = datetime.now()

    login_user(user, remember=session.get("remember_me", True))

    session.permanent = True
    session["obfuscated_email_address"] = input_sanitization.obfuscate_email(
        cleartext_email
    )
    session["session_version"] = user.session_version
    session["email_address"] = cleartext_email
    session["user_id"] = user.id

    message = f"""Hello, {user.username}.

It appears that someone has logged into your Infomundi account from a new device. But fear not, we have kept a watchful eye! Here are the details:

Device: {qol_util.get_device_info(request.headers.get('User-Agent'))}
IP Address: {cloudflare_util.get_user_ip()}
Country: {cloudflare_util.get_user_country()}

It's always wise to make sure that you recognize this login. If this was unexpected, it might be time to change your password.

Should you need to take any action, you can recover your account at: https://{config.BASE_DOMAIN}/auth/forgot_password

If you encounter any issues, please don't hesitate to contact our team for assistance at: https://{config.BASE_DOMAIN}/contact

Best regards,
The Infomundi Team
    """
    subject = "Infomundi - New Login"
    notifications.send_email(cleartext_email, subject, message)


def change_password(user, new_password: str):
    # This function should be refactored
    user.set_password(new_password)
    user.purge_totp()
    user.in_recovery = False
    extensions.db.session.commit()

    message = f"""Hello, {user.username}.

We wanted to inform you that the password for your Infomundi account has been successfully changed. If you made this change, there's nothing else you need to do.

The change was made from the following location:
- IP Address: {cloudflare_util.get_user_ip()}
- Country: {cloudflare_util.get_user_country()}
- Device: {qol_util.get_device_info(request.headers.get('User-Agent'))}

However, if you did not authorize this change, please take immediate action to secure your account. You can recover your account by clicking the link below:

https://{config.BASE_DOMAIN}/auth/forgot_password

If you encounter any issues or need further assistance, feel free to contact us using the form at:

https://{config.BASE_DOMAIN}/contact

Best regards,
The Infomundi Team"""
    subject = "Infomundi - Your Password Has Been Reset"
    if session.get("email_address", ""):
        notifications.send_email(session["email_address"], subject, message)
    session.clear()
    logout_user()


def handle_register_token(email: str, username: str, password: str) -> bool:
    """Generates a verification token, stores in the database and
    uses notifications.send_email to send the verification token to the user.

    Arguments:
        email (str): User's email address.
        username (str): User's username.
        password (str): User's password.

    Returns:
        bool
    """
    email_encrypted = security_util.encrypt(email)
    email_fingerprint = hashing_util.generate_hmac_signature(email, as_bytes=True)

    user = models.User.query.filter(
        or_(
            models.User.email_fingerprint == email_fingerprint,
            models.User.username == username,
        )
    ).first()

    if user:
        # If the user is already enabled, we can't proceed.
        if user.is_enabled:
            return False

        # If the user is not enabled, but the token is expired, we delete the entry.
        created_at = datetime.fromisoformat(user.register_token_timestamp.isoformat())
        if not qol_util.is_date_within_threshold_minutes(created_at, 30):
            extensions.db.session.delete(user)
            extensions.db.session.commit()
            return False

    register_token = security_util.generate_uuid_string()

    message = f"""Hello, {username}.

If you've received this message in error, feel free to disregard it. However, if you're here to verify your account, welcome to Infomundi! We've made it quick and easy for you, simply click on the following link to complete the verification process: 

https://{config.BASE_DOMAIN}/auth/verify?token={register_token}

We're looking forward to seeing you explore our platform!

Best regards,
The Infomundi Team"""

    subject = "Infomundi - Activate Your Account"

    # If we can send the email, save user to the database
    result = notifications.send_email(email, subject, message)
    if result:
        new_user = models.User(
            email_encrypted=email_encrypted,
            email_fingerprint=email_fingerprint,
            username=username,
            password=hashing_util.string_to_argon2_hash(password),
            register_token=security_util.uuid_string_to_bytes(register_token),
            public_id=security_util.generate_uuid_bytes(),
        )
        extensions.db.session.add(new_user)
        extensions.db.session.commit()

    return result


def check_recovery_token(token: str) -> object:
    """Checks if the account recovery token is valid.

    Arguments:
        token (str): Account recovery token.

    Returns:
        object: The user object. None if error.
    """
    user = models.User.query.filter_by(
        recovery_token=security_util.uuid_string_to_bytes(token)
    ).first()
    if not user:
        return None

    created_at = datetime.fromisoformat(user.recovery_token_timestamp.isoformat())
    if not qol_util.is_date_within_threshold_minutes(created_at, 30):
        user.recovery_token = None
        extensions.db.session.commit()
        return None

    user.in_recovery = True
    user.recovery_token = None
    user.recovery_token_timestamp = None
    extensions.db.session.commit()

    return user


def send_recovery_token(email: str) -> bool:
    """Tries to send the account recovery token to the user requesting account recovery.

    Args:
        email (str): The user's email address.

    Returns:
        bool: True if user can proceed with account recovery. Otherwise, False.
    """
    user = search_user_email_in_database(email)
    if not user:
        return False

    # If there's a token already issued to the user, check if it's expired. If expired, proceed. If not, return False.
    if user.recovery_token:
        created_at = datetime.fromisoformat(user.recovery_token_timestamp.isoformat())
        if not qol_util.is_date_within_threshold_minutes(created_at, 30):
            return False

    # Generates a super random token.
    recovery_token = security_util.generate_uuid_string()

    message = f"""Hello.

If you've received this message in error, feel free to disregard it. However, if you're here to recover your Infomundi account, feel free to click on the link below:

https://{config.BASE_DOMAIN}/auth/forgot_password?token={recovery_token}

Please keep in mind that this token will expire in 30 minutes.

Best regards,
The Infomundi Team"""
    subject = "Infomundi - Account Recovery"

    user.recovery_token = security_util.uuid_string_to_bytes(recovery_token)
    user.recovery_token_timestamp = datetime.now()
    extensions.db.session.commit()

    return notifications.send_email(email, subject, message)


def delete_account(email: str, token: str) -> bool:
    user = search_user_email_in_database(email)
    token = security_util.uuid_string_to_bytes(token)

    # If the supplied token doesn't match the database record, return False.
    if user.delete_token != token:
        return False

    # Checks to see if the token is valid. If the token is invalid, deletes it and return False.
    created_at = datetime.fromisoformat(user.delete_token_timestamp.isoformat())
    if not qol_util.is_date_within_threshold_minutes(created_at, 30):
        user.delete_token = None
        extensions.db.session.commit()
        return False

    # Logout and delete user from database
    logout_user()
    friends_util.delete_all_friends(user.id)
    extensions.db.session.delete(user)
    extensions.db.session.commit()

    return True


def send_delete_token(email: str) -> bool:
    user = search_user_email_in_database(email)

    token = security_util.generate_uuid_string()

    subject = "Infomundi - Confirm Account Deletion"
    message = f"""Hello, {user.display_name if user.display_name else user.username}.

If you've received this message in error, feel free to disregard it. However, if you're here to delete your Infomundi account, feel free to click on the link below:

https://{config.BASE_DOMAIN}/auth/delete?token={token}

This link will expire in 30 minutes. Please, keep in mind that this action is permanent and your account data can't be recovered afterwards.

We're sorry to see you go.

Best regards,
The Infomundi Team"""

    result = notifications.send_email(email, subject, message)
    if not result:
        return False

    # Saves delete token information
    user.delete_token = security_util.uuid_string_to_bytes(token)
    user.delete_token_timestamp = datetime.now()
    extensions.db.session.commit()

    return True
