from requests import post as post_request
from json import loads as json_loads
from flask import request

from .config import CAPTCHA_SECRET_KEY


def is_valid_captcha(token: str) -> bool:
    """Uses the cloudflare turnstile API to check if the user passed the CAPTCHA challenge. 

    Args:
        token (str): The turnstile token.

    Returns:
        bool: True if CAPTCHA is valid, otherwise False.
    """
    
    if not token:
        return False

    response = post_request(url="https://challenges.cloudflare.com/turnstile/v0/siteverify", data={'secret': CAPTCHA_SECRET_KEY, 'response': token})

    # Parse JSON from response and return if was a success (True or False).
    return json_loads(response.content)['success']


def get_user_ip() -> str:
    """Uses Cloudflare's headers to obtain the user real IP address.

    Arguments:
        request (object): The request object.

    Returns:
        str: User's IPv4 or IPv6 address.
    """
    ipv4 = request.headers.get('CF-Connecting-IP', '')
    ipv6 = request.headers.get('CF-Connecting-IPv6', '')
    return ipv4 or ipv6


def get_user_country() -> str:
    """Gets the country of the IP making the request. May return an empty string if the appropriate header is not found in the request.

    Arguments:
        request (object): The request object.

    Returns:
        str: The cca2 for the user IP. For instance, BR or US or CA and so on.
    """
    return request.headers.get('CF-IPCountry', '')
