from requests import post as post_request
from json import loads as json_loads
from flask import request
import os

from . import config


def is_local_environment() -> bool:
    """Check if the application is running in a local development environment.

    Returns:
        bool: True if running locally, otherwise False.
    """
    # Check common local hostnames
    hostname = request.host.split(':')[0]  # Remove port if present
    
    local_hostnames = {
        'localhost',
        '127.0.0.1',
        '::1',
        '[::1]',
    }
    
    # Check if hostname is local
    if hostname in local_hostnames:
        return True
    
    # Check for .local domains
    if hostname.endswith('.local'):
        return True
    
    # Check for private IP ranges
    if (hostname.startswith('192.168.') or 
        hostname.startswith('10.') or
        any(hostname.startswith(f'172.{i}.') for i in range(16, 32))):
        return True
    
    # Check Flask environment variables
    flask_env = os.getenv('FLASK_ENV', '').lower()
    flask_debug = os.getenv('FLASK_DEBUG', '').lower()
    
    if flask_env == 'development' or flask_debug in ('1', 'true'):
        return True
    
    return False


def is_valid_turnstile(token: str) -> bool:
    """Uses the cloudflare turnstile API to check if the user passed the CAPTCHA challenge.
    
    Automatically bypasses validation in local development environments.

    Args:
        token (str): The turnstile token.

    Returns:
        bool: True if CAPTCHA is valid, otherwise False.
    """
    # Bypass captcha in local development
    if is_local_environment():
        print("[DEV] Turnstile validation bypassed: local environment detected")
        return True
    
    if not token:
        return False

    response = post_request(
        url="https://challenges.cloudflare.com/turnstile/v0/siteverify",
        timeout=3,
        data={"secret": config.TURNSTILE_SECRET_KEY, "response": token},
    )

    # Parse JSON from response and return if was a success (True or False).
    return json_loads(response.content)["success"]


def get_user_ip() -> str:
    """Uses Cloudflare's headers to obtain the user real IP address.
    
    Falls back to request remote_addr in local development.

    Arguments:
        request (object): The request object.

    Returns:
        str: User's IPv4 or IPv6 address.
    """
    # In local dev, Cloudflare headers won't exist
    if is_local_environment():
        return request.remote_addr or "127.0.0.1"
    
    ipv4 = request.headers.get("CF-Connecting-IP", "")
    ipv6 = request.headers.get("CF-Connecting-IPv6", "")
    return ipv4 or ipv6


def get_user_country() -> str:
    """Gets the country of the IP making the request. May return an empty string if the appropriate header is not found in the request.
    
    Returns a default value in local development.

    Arguments:
        request (object): The request object.

    Returns:
        str: The cca2 for the user IP. For instance, BR or US or CA and so on.
    """
    # In local dev, return a default country code or empty string
    if is_local_environment():
        return os.getenv('DEV_COUNTRY_CODE', '')  # Can set DEV_COUNTRY_CODE=US for testing
    
    return request.headers.get("CF-IPCountry", "")