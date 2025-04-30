from user_agents import parse as parse_user_agent
from langdetect import detect as lang_detect
from datetime import datetime, timedelta
from os import path as os_path


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
        lang = "en"

    return lang


def is_mobile(request) -> bool:
    """
    Determines if the user is using a mobile device based on the User-Agent string in the request object.

    Args:
        request: The HTTP request object that contains metadata about the request, including the User-Agent string.

    Returns:
        bool: True if the User-Agent string indicates a mobile device, False otherwise.
    """
    mobile_keywords = (
        "Mobile",
        "Android",
        "iPhone",
        "iPod",
        "iPad",
        "BlackBerry",
        "Phone",
    )

    # If the for loop breaks, it means that a keyword was found in the user agent and we return True later on.
    user_agent = request.headers.get("User-Agent", "")
    for keyword in mobile_keywords:
        if keyword in user_agent:
            break
    else:
        return False

    return True


def is_date_within_threshold_minutes(
    timestamp: datetime, threshold_time: int, is_hours: bool = False
) -> bool:
    """
    Checks if the given timestamp is within the specified threshold of minutes/hours from the current time.

    Args:
        timestamp (datetime): The datetime object representing the timestamp to be checked.
        threshold_minutes (int): The threshold in minutes/hours to compare the timestamp against.

    Returns:
        bool: True if the timestamp is within the threshold minutes from the current time, False otherwise.

    Example:
        >>> from datetime import datetime, timedelta
        >>> now = datetime.now()
        >>> past_time = now - timedelta(minutes=5)
        >>> is_date_within_threshold_minutes(past_time, 10)
        True
        >>> is_date_within_threshold_minutes(past_time, 3)
        False

        >>> future_time = now + timedelta(minutes=5)
        >>> is_date_within_threshold_minutes(future_time, 10)
        True
        >>> is_date_within_threshold_minutes(future_time, 3)
        False
    """
    time_difference = datetime.now() - timestamp

    if is_hours:
        return time_difference <= timedelta(hours=threshold_time)

    return time_difference <= timedelta(minutes=threshold_time)


def is_file_creation_within_threshold_minutes(
    file_path: str, threshold_time: int, is_hours: bool = False
) -> bool:
    """Checks if the creation of the given file, pointed by file_path, is within the specified threshold of minutes/hours from the current time.

    Args:
        file_path (str): File path to compare.
        threshold_time (int): Time to compare. Defaults to minutes.
        is_hours (bool, optional): Time in hours to compare.


    Returns:
        bool: False if cache is not old, meaning that there's less than 24 hours since last modification. Otherwise, True.
    """

    try:
        # Get the modification time of the file using os.path
        file_mtime = datetime.fromtimestamp(os_path.getmtime(file_path))
    except Exception:
        return True

    # Calculate the time difference between now and the file modification time
    time_difference = datetime.now() - file_mtime

    if is_hours:
        return time_difference <= timedelta(hours=threshold_time)

    return time_difference > timedelta(minutes=threshold_time)


def get_device_info(user_agent_string: str):
    """Parses the user agent string and extracts device information out of it. It can't be 100% accurate, as
    the user agent is user-supplied input. However, it may be beneficial for us to use it, as we don't have CASH
    to buy FingerprintJS' license.

    Arguments
        user_agent_string (str): The user agent string (obviously)

    Returns:
        dict or str: Device details.

    Examples:
        >>> get_device_info("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36")
        {'browser': 'Chrome', 'os': 'Windows 10', 'device_type': 'PC'}
    """
    try:
        user_agent = parse_user_agent(user_agent_string)

        # Extract information (we can get the browser version with user_agent.browser.version_string)
        browser = user_agent.browser.family
        os = f"{user_agent.os.family} {user_agent.os.version_string}"
        device = (
            "Mobile"
            if user_agent.is_mobile
            else (
                "Tablet"
                if user_agent.is_tablet
                else "PC" if user_agent.is_pc else "Other"
            )
        )
    except Exception:
        return "No information"

    return f"Browser: {browser}, OS: {os}, device type: {device}"
