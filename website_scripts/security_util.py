import secrets
import base64
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from .custom_exceptions import InfomundiCustomException


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


def derive_key(secret: str, initial_salt: str=''):
    # Takes the initial salt (base64 string), and decodes it to use in the script
    if initial_salt:
        salt = base64.b64decode(initial_salt.encode('utf-8'))
    else:
        # If the salt was not initially provided, then we generate one!! :D 
        salt = secrets.token_bytes(16)
    
    kdf = Scrypt(
        salt=salt,
        length=32,
        n=2**14,
        r=8,
        p=1,
        backend=default_backend()
    )
    key = kdf.derive(secret.encode())
    
    # Returns tuple if salt was not provided initially. Everything is normalised with base64.
    if not initial_salt:
        return (base64.b64encode(salt.decode('utf-8')), base64.b64encode(key.decode('utf-8')))

    return base64.b64encode(key.decode('utf-8'))


def encrypt(plaintext: str, secret: str='', salt: str='', key: str='') -> str:
    if not salt and not key and not secret:
        # Generate a random salt for key derivation
        salt = secrets.token_bytes(16)
        key = derive_key(secret, salt)
    else:
        salt = base64.b64decode(salt.encode('utf-8'))
        key = base64.b64decode(key.encode('utf-8'))

    # Generate a random IV (initialization vector)
    iv = secrets.token_bytes(16)
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    
    # Padding plaintext to be a multiple of block size
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(plaintext.encode()) + padder.finalize()
    
    ciphertext = encryptor.update(padded_data) + encryptor.finalize()
    
    # Combine salt, IV, and ciphertext, then encode them into Base64 string
    encrypted_data = base64.b64encode(salt + iv + ciphertext).decode('utf-8')
    return encrypted_data


def decrypt(encrypted_data: str, initial_key: str = '', secret: str = '') -> str:
    encrypted_data = base64.b64decode(encrypted_data.encode('utf-8'))
    
    # If the key is not provided, we extract the salt from the cipherdata and generate the key out of the original secret.
    if not initial_key:
        if not secret:
            raise InfomundiCustomException('If no key is provided, then the original secret is required')
        salt = encrypted_data[:16]
        key = derive_key(secret, salt)
    else:
        key = base64.b64decode(initial_key.encode('utf-8'))

    iv = encrypted_data[16:32]  # Extract IV from the data
    ciphertext = encrypted_data[32:]  # The remaining is the ciphertext
    
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    
    padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()
    
    # Remove padding
    unpadder = padding.PKCS7(128).unpadder()
    plaintext = unpadder.update(padded_plaintext) + unpadder.finalize()
    
    return plaintext.decode()
