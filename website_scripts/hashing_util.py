import hashlib
import argon2
import hmac

def argon2_hash_text(cleartext: str) -> str:
    return argon2.PasswordHasher().hash(cleartext)


def argon2_verify_hash(hashed_data: str, cleartext: str) -> bool:
    try:
        argon2.PasswordHasher().verify(hashed_data, cleartext)
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


def md5_hash_text(text: str) -> str:
    return hashlib.md5(text.encode('utf-8')).hexdigest()


def generate_hmac_signature(key: str, message: str, algorithm: str = 'sha256') -> str:
    """
    Generate an HMAC signature for a given message and key.
    
    Parameters:
        key (str): The secret key used for signing.
        message (str): The message to be signed.
        algorithm (str): The hashing algorithm to use ('sha256', 'sha1', 'md5', etc.). Default is 'sha256'.
    
    Returns:
        str: The generated HMAC signature as a hexadecimal string.
    """
    key_bytes = key.encode('utf-8')
    message_bytes = message.encode('utf-8')
    hash_function = getattr(hashlib, algorithm)
    hmac_obj = hmac.new(key_bytes, message_bytes, hash_function)
    return hmac_obj.hexdigest()


def is_hmac_authentic(key: str, message: str, provided_signature: str, algorithm: str = 'sha256') -> bool:
    """
    Verify if the provided HMAC signature matches the expected signature for the given message and key.
    
    Parameters:
        key (str): The secret key used for signing.
        message (str): The message to be verified.
        provided_signature (str): The HMAC signature to verify.
        algorithm (str): The hashing algorithm to use ('sha256', 'sha1', 'md5', etc.). Default is 'sha256'.
    
    Returns:
        bool: True if the signature is authentic, False otherwise.
    """
    # Generate the correct signature
    expected_signature = generate_hmac_signature(key, message, algorithm)
    
    # Use hmac.compare_digest for constant-time comparison to prevent timing attacks
    return hmac.compare_digest(expected_signature, provided_signature)
