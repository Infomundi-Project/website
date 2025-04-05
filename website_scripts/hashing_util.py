import hashlib
import argon2
import hmac

from .config import HMAC_KEY


def string_to_argon2_hash(cleartext: str) -> str:
    return argon2.PasswordHasher().hash(cleartext)


def argon2_verify_hash(hashed_data: str, cleartext: str) -> bool:
    try:
        argon2.PasswordHasher().verify(hashed_data, cleartext)
    except Exception:
        return False

    return True


def sha256_verify_hash(text: str, hash_value: str) -> bool:
    """
    Verifies that the given text matches the provided SHA-256 hash.

    Args:
        text (str): The input text to be verified.
        hash_value (str): The SHA-256 hash to compare against.

    Returns:
        bool: True if the text matches the hash, False otherwise.

    Example:
        >>> hash_value = sha256_hash_text('hello world')
        >>> verify_sha256_hash('hello world', hash_value)
        True
        >>> verify_sha256_hash('hello', hash_value)
        False
    """
    return sha256_hash_text(text) == hash_value


def binary_to_sha256_hex(binary_data: bytes) -> str:
    """Convert a binary SHA-256 hash to a 64-character hex string"""
    return binary_data.hex()


def sha256_binary_to_string(binary_data: bytes) -> str:
    """Convert SHA-256 hash (binary) to a 64-character hex string"""
    return hashlib.sha256(binary_data).hexdigest()


def sha256_hex_to_binary(sha256_hex: str) -> bytes:
    """Convert SHA-256 hex to binary (32-byte BLOB equivalent)"""
    return bytes.fromhex(sha256_hex)


def string_to_sha256_binary(input_string: str) -> bytes:
    """Convert a string to a SHA-256 binary hash"""
    return hashlib.sha256(input_string.encode()).digest()


def string_to_sha256_hex(input_string: str) -> str:
    """Convert a string to a SHA-256 hex hash"""
    return hashlib.sha256(input_string.encode()).hexdigest()


def string_to_sha512_hex(text: str) -> str:
    """
    Hashes the given text using SHA-512 and returns the hash in hexadecimal format.

    Args:
        text (str): The input text to be hashed.

    Returns:
        str: The resulting SHA-512 hash in hexadecimal format.

    Example:
        >>> string_to_sha512_hex('hello world')
        '570ea4d47019c5f953442981d994c7c936341de56cdda26dde54055b96e811c03464038a4178d514107244b632fa73c941075006c60dadc8d0cbb6ab15b599aa'
    """
    sha512 = hashlib.sha512()
    sha512.update(text.encode('utf-8'))
    return sha512.hexdigest()


def sha512_verify_hash(text: str, hash_value: str) -> bool:
    """
    Verifies that the given text matches the provided SHA-512 hash.

    Args:
        text (str): The input text to be verified.
        hash_value (str): The SHA-512 hash to compare against.

    Returns:
        bool: True if the text matches the hash, False otherwise.

    Example:
        >>> hash_value = string_to_sha512_hex('hello world')
        >>> verify_sha512_hash('hello world', hash_value)
        True
        >>> verify_sha512_hash('hello', hash_value)
        False
    """
    return string_to_sha512_hex(text) == hash_value


def binary_to_md5_hex(binary_data: bytes) -> str:
    """Convert a string to MD5 hash (hex format)

    Example:
        >>> binary_md5 = md5_hex_to_binary("5d41402abc4b2a76b9719d911017c592")
        >>> print(binary_to_md5_hex(binary_md5))
        5d41402abc4b2a76b9719d911017c592
    """
    return binary_data.hex()


def md5_binary_to_string(binary_data: bytes) -> str:
    """Convert MD5 hash (binary) to a 32-character hex string

    Example:
        >>> binary_md5 = md5_hex_to_binary("5d41402abc4b2a76b9719d911017c592")
        >>> print(md5_binary_to_string(binary_md5))
        52df1db4ad8b6c8a1c98e92b3ea1aada
    """
    return hashlib.md5(binary_data, usedforsecurity=False).hexdigest()


def md5_hex_to_binary(md5_hex: str) -> bytes:
    """Convert MD5 hex to binary (16-byte BLOB equivalent)
    
    Example:
        >>> print(md5_hex_to_binary("5d41402abc4b2a76b9719d911017c592"))
        b']A@\\x02\\xab\\xc4\\xb2\\xa7k\\x97\\x19\\xd9\\x11\\x01|Y'
    """
    return bytes.fromhex(md5_hex)


def string_to_md5_binary(input_string: str) -> bytes:
    """Convert an MD5 hash from a string to binary in one step

    Example:
        >>> print(string_to_md5_binary("hello"))
        b']A@\\x02\\xab\\xc4\\xb2\\xa7k\\x97\\x19\\xd9\\x11\\x01|Y'
    """
    return hashlib.md5(input_string.encode(), usedforsecurity=False).digest()


def string_to_md5_hex(input_string: str) -> str:
    """

    Example:
        >>> print(string_to_md5_hex("hello"))  
        5d41402abc4b2a76b9719d911017c592
    """
    return hashlib.md5(input_string.encode(), usedforsecurity=False).hexdigest()


def generate_hmac_signature(message: str, key: str = HMAC_KEY, algorithm: str = 'sha256', as_bytes: bool = False):
    """
    Generate an HMAC signature for a given message and key.
    
    Parameters:
        key (str): The secret key used for signing. Default is the HMAC key for the application.
        message (str): The message to be signed.
        algorithm (str): The hashing algorithm to use ('sha256', 'sha1', 'md5', etc.). Default is 'sha256'.
        return_format (str): Changes the signature return format ('string', 'bytes'). Default is 'string'.
    
    Returns:
        str or bytes: The generated HMAC signature as a hexadecimal string or bytes.
    """
    key_bytes = key.encode('utf-8')
    message_bytes = message.encode('utf-8')
    hash_function = getattr(hashlib, algorithm)
    hmac_obj = hmac.new(key_bytes, message_bytes, hash_function)
    
    if as_bytes:
        return hmac_obj.digest()

    return hmac_obj.hexdigest()


def is_hmac_authentic(key: str, message: str, provided_signature: str, algorithm: str = 'sha256') -> bool:
    """
    Verify if the provided HMAC signature matches the expected signature for the given message and key.
    
    Parameters:
        key (str): The secret key used for signing.
        message (str): The message to be verified.
        provided_signature (str): The HMAC signature to verify.
        algorithm (str): The hashing algorithm to use. Default is 'sha256'.
    
    Returns:
        bool: True if the signature is authentic, False otherwise.
    """
    # Generate the correct signature
    expected_signature = generate_hmac_signature(message, key=key)
    
    # Use hmac.compare_digest for constant-time comparison to prevent timing attacks
    return hmac.compare_digest(expected_signature, provided_signature)
