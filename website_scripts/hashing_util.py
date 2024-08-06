import hashlib
import argon2


def argon2_hash_text(cleartext: str) -> str:
    return argon2.PasswordHasher().hash(cleartext)


def argon2_verify_hash(hashed_password: str, cleartext: str) -> bool:
    try:
        argon2.PasswordHasher().verify(hashed_password, cleartext)
    except Exception:
        return False

    return True


def sha256_hash_text(text: str) -> str:
    """
    Hashes the given text using SHA-256 and returns the hash in hexadecimal format.

    Args:
        text (str): The input text to be hashed.

    Returns:
        str: The resulting SHA-256 hash in hexadecimal format.

    Example:
        >>> sha256_hash_text('hello world')
        'a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e'
    """
    sha256 = hashlib.sha256()
    sha256.update(text.encode('utf-8'))
    return sha256.hexdigest()


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
