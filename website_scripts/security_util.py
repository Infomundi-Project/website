import base64
import secrets


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

