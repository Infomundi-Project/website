from urllib.parse import urlparse
import re

def is_valid_url(url: str) -> bool:
    """
    Checks if the url is valid.
    - We should be able to parse the url using urllib.parse, indicating that the url is valid.

    Arguments:
        url (str): The target url. Example: https://infomundi.net/

    Returns:
        bool: True if url is valid. Otherwise False.

    Examples:
        >>> is_valid_url('http://totally not valid')
        False

        >>> is_valid_url('https://google.com/')
        True
    """
    try:
        result = urlparse(url)
        if all([result.scheme == "https", result.netloc]):
            # Check if the netloc (domain) is valid using a regex
            netloc_regex = re.compile(r'^([A-Za-z0-9-]+\.)+[A-Za-z]{2,6}$')
            return bool(netloc_regex.match(result.netloc))
        return False
    except ValueError:
        return False

print(is_valid_url('https://totallynotvalid.com/path/something.jpg/merda'))