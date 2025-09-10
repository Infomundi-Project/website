import re
from langdetect import detect as lang_detect
from datetime import datetime, timedelta
from collections import namedtuple
from os import path as os_path

# a tiny struct to hold our parsed result
ParsedUA = namedtuple(
    "ParsedUA",
    [
        "browser_family",
        "browser_version",
        "os_family",
        "os_version",
        "is_mobile",
        "is_tablet",
        "is_pc",
    ],
)


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


def parse_user_agent_custom(ua: str) -> ParsedUA:
    """
    Very basic User-Agent parser that recognizes major browsers,
    OS families, and device classes.
    """
    # 1) Browser detection
    browser_family = "Other"
    browser_version = ""
    browser_patterns = [
        ("Edge", r"Edg(?:e|A|IOS)?/([\d\.]+)"),
        ("Opera", r"OPR/([\d\.]+)"),
        ("Chrome", r"Chrome/([\d\.]+)"),
        ("Firefox", r"Firefox/([\d\.]+)"),
        ("Safari", r"Version/([\d\.]+).*Safari/"),
    ]
    for fam, pat in browser_patterns:
        m = re.search(pat, ua)
        if m:
            browser_family = fam
            browser_version = m.group(1)
            break

    # 2) OS detection
    os_family = "Other"
    os_version = ""
    # Windows NT → friendly mapping
    win = re.search(r"Windows NT ([\d\.]+)", ua)
    if win:
        os_family = "Windows"
        nt = win.group(1)
        version_map = {
            "10.0": "10",
            "6.3": "8.1",
            "6.2": "8",
            "6.1": "7",
            "6.0": "Vista",
            "5.1": "XP",
        }
        os_version = version_map.get(nt, nt)
    else:
        mac = re.search(r"Mac OS X ([\d_\.]+)", ua)
        if mac:
            os_family = "macOS"
            os_version = mac.group(1).replace("_", ".")
        else:
            android = re.search(r"Android ([\d\.]+)", ua)
            if android:
                os_family = "Android"
                os_version = android.group(1)
            else:
                ios = re.search(r"iPhone OS ([\d_]+)", ua) or re.search(
                    r"iPad; CPU OS ([\d_]+)", ua
                )
                if ios:
                    os_family = "iOS"
                    os_version = ios.group(1).replace("_", ".")
                elif "Linux" in ua:
                    os_family = "Linux"
                    os_version = ""

    # 3) Device class
    mobile_kw = ("Mobile", "Android", "iPhone", "iPod", "BlackBerry", "Phone")
    tablet_kw = ("Tablet", "iPad")
    is_mobile = any(kw in ua for kw in mobile_kw)
    is_tablet = any(kw in ua for kw in tablet_kw)
    is_pc = not (is_mobile or is_tablet)

    return ParsedUA(
        browser_family,
        browser_version,
        os_family,
        os_version,
        is_mobile,
        is_tablet,
        is_pc,
    )


def get_device_info(user_agent_string: str):
    """
    Parses the UA string without any external library.
    Returns the same dict (or string) your old function did.
    """
    try:
        ua = parse_user_agent_custom(user_agent_string)
        device = (
            "Mobile"
            if ua.is_mobile
            else "Tablet"
            if ua.is_tablet
            else "PC"
            if ua.is_pc
            else "Other"
        )
        return {
            "browser": ua.browser_family,
            "browser_version": ua.browser_version,
            "os": f"{ua.os_family} {ua.os_version}".strip(),
            "device_type": device,
        }
    except Exception:
        return "No information"
