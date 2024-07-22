import re
import bleach
from urllib.parse import urlparse


def sanitize_description(comment: str) -> str:
    """
    Sanitize a user comment by using bleach to remove potentially dangerous content
    while allowing safe HTML tags and attributes.
    
    Arguments:
        comment (str): The comment to sanitize.
    
    Returns:
        str: The sanitized comment.
    """
    # Define allowed tags and attributes
    allowed_tags = list(bleach.sanitizer.ALLOWED_TAGS) + ['p', 'b', 'i', 'u', 'em', 'strong', 'a', 'br']
    allowed_attributes = bleach.sanitizer.ALLOWED_ATTRIBUTES
    allowed_attributes['a'] = ['href', 'title']
    
    # Sanitize the comment
    sanitized_comment = bleach.clean(
        comment,
        tags=allowed_tags,
        attributes=allowed_attributes,
        strip=True  # Strip disallowed tags instead of escaping
    )
    
    return sanitized_comment


def sanitize_html(text: str) -> str:
    """Takes an input string and uses bleach library to sanitize it by escaping html.

    Arguments:
        text (str): Any user-input text.

    Returns:
        str: Sanitized input.

    Example:
        >>> sanitize_html('an <script>evil()</script> example')
        'an &lt;script&gt;evil()&lt;/script&gt; example'
    """
    text = text.strip()
    
    return bleach.clean(text)


def sanitize_text(text: str) -> str:
    """
    Sanitize text by removing characters that do not conform to the allowed set:
    - Only contains alphanumeric characters, spaces, and selected special characters.
    
    Arguments:
        text (str): The input text to sanitize.
    
    Returns:
        str: The sanitized text.
    """
    text = text.strip()
    
    # Define the allowed characters using a regex pattern
    allowed_chars_pattern = re.compile(r'[^a-zA-Z0-9 ,.!?:\-\'"]')
    
    # Substitute any character not in the allowed set with an empty string
    sanitized_text = allowed_chars_pattern.sub('', text)
    
    return sanitized_text


def is_valid_email(email: str) -> bool:
    """
    Sanitize an email address by ensuring it conforms to a basic pattern and removing extraneous whitespace.
    
    Arguments:
        email (str): The email address to sanitize.
    
    Returns:
        bool: True if email is valid, False otherwise.

    Examples:
        >>> is_valid_email('behindsecurity@proton.me')
        True

        >>> is_valid_email('$h()uld not be_valid@mail.com')
        False
    """
    # Define a regular expression pattern for a basic email format
    email_pattern = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')
    
    # Match the email against the pattern
    if email_pattern.match(email):
        return True
    
    return False


def is_valid_username(username: str) -> bool:
    """
    Sanitize a username by ensuring it conforms to a set of rules:
    - Only contains alphanumeric characters, underscores, and hyphens.
    - Length between 3 and 25 characters.
    - No leading or trailing whitespace.
    
    Arguments:
        username (str): The username to sanitize.
    
    Returns:
        bool: True if username is valid, False otherwise.
    """
    # Define a regular expression pattern for a valid username
    username_pattern = re.compile(r'^[a-zA-Z0-9_-]{3,25}$')
    
    # Match the username against the pattern
    if not username_pattern.match(username):
        return False

    return True


def is_valid_text(text: str) -> bool:
    """
    Sanitize text by ensuring it conforms to a set of rules:
    - Only contains alphanumeric characters, spaces, and selected special characters.
    
    """
    text_regex = re.compile(r'^[a-zA-Z0-9 ,.!?:\-\'"]*$')
    return bool(text_regex.match(text))


def is_valid_url(url: str) -> bool:
    """
    Checks if the url is valid.

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


def is_safe_url(target: str) -> bool:
    """
    Checks if the target url is safe.
    - Should be under the domain infomundi.net

    Arguments:
        target (str): A target url.

    Returns:
        str: True if the url is safe. False otherwise.

    Examples:
        >>> is_safe_url('https://clearly.malicious.com/collect')
        False

        >>> is_safe_url('https://infomundi.net/contact')
        True

        >>> is_safe_url('https://commento.infomundi.net/en/dashboard')
        True
    """
    try:
        test_url = urlparse(target)
    except ValueError:
        return False
    
    # Checks to see if the url ends with the infomundi.net trusted domain
    if not test_url.netloc.endswith('infomundi.net'):
        return False

    return True


def is_md5_hash(text: str) -> bool:
    """
    Check if the text is a MD5 hash.
    - Should be 32 charaters;
    - Should contain only a-f and A-F and 0-9. 
    
    Arguments:
        text (str): The text to compare.

    Returns:
        bool: True if the input text is a md5 hash. Otherwise False.

    Examples:
        >>> is_md5_hash('fe78a7a2a545b3caa1c94bf374368374')
        True

        >>> is_md5_hash('Hello, fe78a7a2a545b3caa1c94bf374368374, this is an example')
        False

        >>> is_md5_hash('Totally not a md5 hash')
        False
    """
    md5_regex = re.compile(r'^[a-fA-F0-9]{32}$')
    return bool(md5_regex.match(text))


def is_text_length_between(length_range: tuple, text: str) -> bool:
    """Check if the text is within the range.

    Arguments:
        length_range (tuple): A tuple with two integers. The first should be the mininum lenght and the second should be the
        maximum length.
        text (str): The text to compare.

    Returns:
        bool: True if the text length is in the range. Otherwise False.

    Examples:
        >>> is_text_length_between((3, 50), 'An example text within the range')
        True

        >>> is_text_length_between((3, 50), 'a')
        False
    """
    text_length = len(text)

    min_length = length_range[0]
    max_length = length_range[1]

    # Prevents incorrect usage. Switches values, where max_length is now min_lentgth and vice versa.
    if min_length > max_length:
        temp = min_length
        min_length = max_length
        max_length = temp

    return (min_length <= text_length <= max_length)


def gentle_cut_text(max_length: int, text: str) -> str:
    """
    Truncate text to a maximum length without cutting words in half.

    Arguments:
        max_length (int): The maximum length of the returned text.
        text (str): The input text to be truncated.

    Returns:
        str: The truncated text, ensuring it does not exceed the specified maximum length and does not cut words.

    Examples:
        >>> gentle_cut_text(20, "This is an example sentence that we need to cut gently.")
        'This is an example'

        >>> gentle_cut_text(20, "Short text.")
        'Short text.'

        >>> gentle_cut_text(20, "Another long example that should be cut at an appropriate space.")
        'Another long example'
    """
    # Return the text if its length is already within the maximum length
    if len(text) <= max_length:
        return text
    
    # Find the last space within the allowed range to avoid cutting words
    cut_index = text.rfind(' ', 0, max_length)
    
    # If no space is found, cut the text exactly at max_length
    if cut_index == -1:
        cut_index = max_length
    
    # Return the truncated text
    return text[:cut_index]
