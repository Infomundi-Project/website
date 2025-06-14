import qrcode
import base64
import pyotp
import io

from . import hashing_util, config


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
    qr_code_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

    # Return the base64-encoded QR code string
    return qr_code_base64


def verify_totp(secret_key, token) -> bool:
    totp = pyotp.TOTP(secret_key)
    return totp.verify(token)
