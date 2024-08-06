from langdetect import detect as lang_detect
from datetime import datetime, timedelta


def detect_language(text: str) -> str:
    """Tries to detect the language of a text value.
    
    Args:
        text (str): Any given text.

    Returns:
        str: The text's language code. Defaults to 'en' when fails to detect the actual language.
    
    Examples:
        >>> detect_language('Esse é um texto que está escrito em português!')
        'pt'
        >>> detect_language('This is written in English.')
        'en'
    """
    try:
        lang = lang_detect(text)
    except Exception:
        lang = 'en'
    
    return lang


def is_mobile(request) -> bool:
    """
    Determines if the user is using a mobile device based on the User-Agent string in the request object.

    Args:
        request: The HTTP request object that contains metadata about the request, including the User-Agent string.

    Returns:
        bool: True if the User-Agent string indicates a mobile device, False otherwise.
    """
    mobile_keywords = ('Mobile', 'Android', 'iPhone', 'iPod', 'iPad', 'BlackBerry', 'Phone')

    # If the for loop breaks, it means that a keyword was found in the user agent and we return True later on.
    user_agent = request.headers.get('User-Agent', '')
    for keyword in mobile_keywords:
        if keyword in user_agent:
            break
    else:
        return False

    return True


def is_within_threshold_minutes(timestamp: datetime, threshold_minutes: int) -> bool:
    """
    Checks if the given timestamp is within the specified threshold of minutes from the current time.

    Args:
        timestamp (datetime): The datetime object representing the timestamp to be checked.
        threshold_minutes (int): The threshold in minutes to compare the timestamp against.

    Returns:
        bool: True if the timestamp is within the threshold minutes from the current time, False otherwise.

    Example:
        >>> from datetime import datetime, timedelta
        >>> now = datetime.now()
        >>> past_time = now - timedelta(minutes=5)
        >>> is_within_threshold_minutes(past_time, 10)
        True
        >>> is_within_threshold_minutes(past_time, 3)
        False

        >>> future_time = now + timedelta(minutes=5)
        >>> is_within_threshold_minutes(future_time, 10)
        True
        >>> is_within_threshold_minutes(future_time, 3)
        False
    """
    time_difference = datetime.now() - timestamp
    return time_difference <= timedelta(minutes=threshold_minutes)