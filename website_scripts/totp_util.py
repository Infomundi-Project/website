import qrcode
import base64
import pyotp
import io

from . import security_util, hashing_util, config


def generate_totp_secret():
    return pyotp.random_base32()


def generate_totp(secret_key):
    totp = pyotp.TOTP(secret_key)
    return totp.now()


def generate_qr_code(secret_key, account_name) -> str:
    totp = pyotp.TOTP(secret_key)
    uri = totp.provisioning_uri(name=account_name, issuer_name="Infomundi")
    
    qr = qrcode.make(uri)
    
    # Convert the QR image to base64
    buffered = io.BytesIO()
    qr.save(buffered, format="PNG")
    qr_code_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
    
    # Return the base64-encoded QR code string
    return qr_code_base64


def verify_totp(secret_key, token) -> bool:
    totp = pyotp.TOTP(secret_key)
    return totp.verify(token)


def deal_with_it(user, code: str, recovery_token: str) -> tuple:
    """
    Deals with the entire process of verifying the TOTP code. If the recovery code is supplied instead, we make sure to remove
    the TOTP configuration for the user.

    Arguments
        user (flask_login.UserMixin): The user performing the interaction
        code (str): 6-digit two factor authentication code
        recovery_token (str): TOTP recovery token

    Returns
        tuple: A tuple containg the status and message regarding the performed action. Example: (False, 'Invalid TOTP recovery code!')
    """
    if recovery_token:
        if hashing_util.argon2_verify_hash(user.totp_recovery, recovery_token):
            user.purge_totp()
            return (True, f'We removed your TOTP configuration, {user.username}. Please, re-enable it whenever possible. Welcome back to Infomundi!')
        else:
            return (False, 'Invalid TOTP recovery code!')

    # Decrypt user's totp secret
    totp_secret = security_util.decrypt(user.totp_secret)

    is_valid_totp = verify_totp(totp_secret, code)
    if not is_valid_totp:
        return (False, 'Invalid TOTP code!')
    
    return (True, 'Success!')
