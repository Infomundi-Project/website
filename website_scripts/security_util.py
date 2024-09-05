import secrets
import base64
from random import randint
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from .custom_exceptions import InfomundiCustomException


def generate_2fa_token() -> str:
    return str(randint(100000, 999999))  # 6-digit code


def generate_nonce(length: int=32) -> str:
    """Uses the 'base64' library to base64 encode (url safe) a secure random sequence of bytes provided by the 'secrets' library. Used to generate safe random values.

    Arguments
        length (int): Optional. Byte sequence length. Does not mean that the returning string is going to match the specified length, but the byte sequence will be of X (int) bytes. Higher = safer.

    Returns
        str: A safe random string.

    Examples
        >>> generate_none()
        '2zVMl8vFJDNilLSYqcaZlNE3XVUQW9xn-HnW6j4MkYo='

        >>> generate_nonce(24)
        'jjuXC1xv2idEsxGhmw-3tNraGtDKQxGI'
    """
    return base64.urlsafe_b64encode(secrets.token_bytes(length)).decode('utf-8')


def derive_key(secret: str, initial_salt: str = ''):
    # Decodes the base64-encoded salt if provided, otherwise generates a new one
    if initial_salt:
        salt = base64.b64decode(initial_salt.encode('utf-8'))
    else:
        salt = secrets.token_bytes(16)  # Generate a random salt

    # Derive a key using Scrypt key derivation function
    kdf = Scrypt(
        salt=salt,
        length=32,
        n=2**14,
        r=8,
        p=1,
        backend=default_backend()
    )
    key = kdf.derive(secret.encode())  # Derive the key from the secret (binary)

    # Return salt and key both base64-encoded (if new salt is generated)
    if not initial_salt:
        return base64.b64encode(salt).decode('utf-8'), base64.b64encode(key).decode('utf-8')
    
    # Return only the key as base64-encoded if salt was provided
    return base64.b64encode(key).decode('utf-8')


def encrypt(plaintext: str, secret: str = '', salt: str = '', key: str = '') -> str:
    if not key and secret:
        # If key is not provided, derive it along with salt
        salt, key = derive_key(secret)
    elif salt and key:
        # If salt and key are provided, decode them from base64
        salt = base64.b64decode(salt.encode('utf-8'))
        key = base64.b64decode(key.encode('utf-8'))
    else:
        raise InfomundiCustomException('Either the secret or both the salt and key must be provided')

    # Generate a random IV (initialization vector)
    iv = secrets.token_bytes(16)
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()

    # Padding plaintext to be a multiple of block size
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(plaintext.encode()) + padder.finalize()

    # Encrypt the padded data
    ciphertext = encryptor.update(padded_data) + encryptor.finalize()

    # Combine salt, IV, and ciphertext, then encode them into Base64 string
    encrypted_data = base64.b64encode(salt + iv + ciphertext).decode('utf-8')
    return encrypted_data


def decrypt(encrypted_data: str, initial_key: str = '', secret: str = '') -> str:
    encrypted_data = base64.b64decode(encrypted_data.encode('utf-8'))

    # Extract salt, IV, and ciphertext from the encrypted data
    salt = encrypted_data[:16]
    iv = encrypted_data[16:32]
    ciphertext = encrypted_data[32:]

    # If the key is not provided, derive it from the secret and salt
    if not initial_key:
        if not secret:
            raise InfomundiCustomException('If no key is provided, the original secret is required')
        key = derive_key(secret, base64.b64encode(salt).decode('utf-8'))
    else:
        key = base64.b64decode(initial_key.encode('utf-8'))

    # Decrypt the data using the derived key and IV
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()

    # Decrypt and remove padding
    padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    plaintext = unpadder.update(padded_plaintext) + unpadder.finalize()

    return plaintext.decode()
