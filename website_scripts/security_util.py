import secrets
import uuid
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .config import ENCRYPTION_KEY


def generate_2fa_token() -> str:
    code = ''
    for _ in range(6):
        code += str(secrets.randbelow(10))
    return code


def generate_uuid_string() -> str:
    return str(uuid.UUID(int=secrets.randbits(128)))


def generate_uuid_bytes() -> bytes:
    return uuid.UUID(int=secrets.randbits(128)).bytes


def uuid_bytes_to_string(uuid_bytes: bytes) -> str:
    return str(uuid.UUID(bytes=uuid_bytes))


def uuid_string_to_bytes(uuid_string: str) -> bytes:
    return uuid.UUID(uuid_string).bytes


def generate_nonce(length: int = 32, limit: int = 0) -> str:
    """Creates a secure random sequence of URL-safe characters provided by the 'secrets' library. 
    Used to generate safe random values.

    Arguments
        length (int): Optional. Byte sequence length. Does not mean that 
            the returning string is going to match the specified length, but the byte sequence 
            will be of X (int) bytes. Higher = safer.
        limit (int): Optional. Limits the token to a specific length.

    Returns
        str: A safe random string.

    Examples
        >>> generate_none()
        'yq-26-VWJ7xTKJkYMfmKFov8dudU9eTY20Rhk1u7uaM'

        >>> generate_nonce(24)
        'Ssw3PS8c1gSfSLksDPQpoqPpJm_g2lyb'

        >>> generate_nonce(limit=10)
        'tLut2cTtSY'
    """
    return secrets.token_urlsafe(length)[:limit] if limit else secrets.token_urlsafe(length)


def derive_key(password: str, salt: bytes, length: int = 32) -> bytes:
    """
    Derives a symmetric encryption key from a cleartext password using the Scrypt key derivation function.

    Args:
        password (str): The user's password or secret.
        salt (bytes): A random salt used to ensure key uniqueness.
        length (int): Desired length of the derived key in bytes. Default is 32 bytes (256 bits).

    Returns:
        bytes: A derived cryptographic key suitable for use with AES.
    """
    kdf = Scrypt(
        salt=salt,
        length=length,
        n=2**14,
        r=8,
        p=1,
    )
    return kdf.derive(password.encode())


def encrypt(plaintext: str, salt: bytes = b'', password: str = ENCRYPTION_KEY) -> bytes:
    """
    Encrypts plaintext using AES-GCM with a key derived from the user's password.

    A new random salt and nonce are generated for each encryption operation.
    The output is a blob containing salt + nonce + ciphertext.

    Args:
        plaintext (str): The plaintext message to encrypt.
        salt (bytes): Optional. The salt to use.
        password (str): Optional. The password from which the encryption key will be derived.

    Returns:
        bytes: Encrypted data including the salt, nonce, and ciphertext.
    """
    if not salt:
        salt = secrets.token_bytes(16)  # Unique salt per encryption
    
    key = derive_key(password, salt)

    aesgcm = AESGCM(key)
    nonce = secrets.token_bytes(12)  # Recommended nonce size for GCM
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)

    encrypted_blob = salt + nonce + ciphertext
    return encrypted_blob


def decrypt(encrypted_blob: bytes, password: str = ENCRYPTION_KEY) -> str:
    """
    Decrypts AES-GCM encrypted data using the password from which the key was derived.

    Automatically extracts the salt and nonce from the encrypted blob to recreate the key.

    Args:
        encrypted_blob (bytes): Data containing salt + nonce + ciphertext.
        password (str): The password originally used to encrypt the data.

    Returns:
        str: The decrypted plaintext message.

    Raises:
        ValueError: If the decryption fails due to an incorrect password or tampered data.
    """
    salt = encrypted_blob[:16]
    nonce = encrypted_blob[16:28]
    ciphertext = encrypted_blob[28:]

    key = derive_key(password, salt)
    aesgcm = AESGCM(key)

    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    except Exception:
        raise ValueError("Decryption failed: invalid password or corrupted data")

    return plaintext.decode()
