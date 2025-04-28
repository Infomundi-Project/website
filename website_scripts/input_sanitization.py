import bleach
import html
import re

from urllib.parse import urlparse
from unidecode import unidecode
from bs4 import BeautifulSoup

from . import security_util, config


def has_external_links(text: str) -> bool:
    """
    Analyze the given text and return any detected patterns that
    could indicate a user is trying to direct others to an external website.
    """
    patterns = [
        # Standard URLs
        r'https?://[^\s]+',
        # 'www.' prefix without protocol
        r'www\.[^\s]+',
        # Common TLDs
        r'\b[^\s]+\.(com|org|net|io|info|biz|co|us|edu|gov)\b',
        # Obfuscated with dots or spaces
        r'\b[^\s]+\s*\.\s*(com|org|net|io|info|biz|co|us|edu|gov)\b',
        # Dot spelled out
        r'\b[^\s]+\s+dot\s+(com|org|net|io|info|biz|co|us|edu|gov)\b',
        # Dot in brackets
        r'\b[^\s]+\s*\[\s*dot\s*\]\s*(com|org|net|io|info|biz|co|us|edu|gov)\b',
        # Protocol obfuscated with spaces
        r'(?:(?:http|https)\s*[:]\s*//[^\s]+)',
        # URL shorteners and redirect services
        r'\b(?:bit\.ly|tinyurl\.com|goo\.gl|t\.co|ow\.ly|buff\.ly|lc\.chat)\b[^\s]*',
        # Punycode (xn--)
        r'\b(?:xn--[^\s]+)\b',
        # Raw IP addresses (with optional port/path)
        r'\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?(?:/[^\s]*)?',
        # URL-encoded separators
        r'%3A%2F%2F',
        # Data URIs
        r'data:[^\s]+base64,',
        # HTML anchor tags
        r'<a\s+href=["\']([^"\']+)["\']',
        # JavaScript redirects
        r'javascript\s*:',
        # Markdown-style links
        r'\[.*?\]\(.*?\)',
    ]

    findings = []
    for pat in patterns:
        for match in re.finditer(pat, text, flags=re.IGNORECASE):
            findings.append({
                'pattern': pat,
                'match': match.group().strip()
            })

    return bool(findings)


def clean_publisher_name(name):
    # Remove common patterns
    name = re.sub(r' - Latest.*', '', name, flags=re.IGNORECASE)
    name = re.sub(r' - Breaking.*', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\|.*', '', name, flags=re.IGNORECASE)
    name = re.sub(r'–.*', '', name, flags=re.IGNORECASE)
    name = re.sub(r'News24.*', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s+', ' ', name).strip()  # Clean up extra spaces
    return name


def decode_html_entities(text: str):
    """
    Decodes a string of HTML entities iteratively until it no longer changes. 
    Returns the fully decoded string.
    """
    while True:
        decoded = html.unescape(str(text))
        if decoded == text:  # Stop if no further changes occur
            return text
        text = decoded


def sanitize_description(description: str) -> str:
    """
    Sanitize a user description by using bleach to remove potentially dangerous content
    while allowing safe HTML tags and attributes.
    
    Arguments:
        description (str): The description to sanitize.
    
    Returns:
        str: The sanitized description.
    """
    description = description.strip()

    # Define allowed tags and attributes
    allowed_tags = list(bleach.sanitizer.ALLOWED_TAGS) + ['p', 'b', 'i', 'u', 'em', 'strong', 'a', 'br']
    allowed_attributes = bleach.sanitizer.ALLOWED_ATTRIBUTES
    allowed_attributes['a'] = ['href', 'title']
    
    # Sanitize the description
    sanitized_description = bleach.clean(
        description,
        tags=allowed_tags,
        attributes=allowed_attributes,
        strip=True  # Strip disallowed tags instead of escaping
    )
    
    return sanitized_description


def sanitize_html(text: str) -> str:
    """Takes an input string and uses bleach library to sanitize it by stripping html.

    Arguments:
        text (str): Any user-input text.

    Returns:
        str: Sanitized input.

    Example:
        >>> sanitize_html('A defesa do ex-presidente \
            <a href="https://www1.folha.uol.com.br/folha-topicos/jair-bolsonaro/">Jair Bolsonaro</a> \
            (<a href="https://www1.folha.uol.com.br/folha-topicos/pl/">PL</a>) pediu que o ministro \
            <a href="https://www1.folha.uol.com.br/folha-topicos/alexandre-de-moraes/">Alexandre de Moraes</a>, \
            do <a href="https://www1.folha.uol.com.br/folha-topicos/stf/">STF</a>')
        'A defesa do ex-presidente Jair Bolsonaro (PL) pediu que o ministro Alexandre de Moraes, do STF'

        >>> input_sanitization.sanitize_html('An <script>evil()</script> script')
        'An evil() script'
    """
    return bleach.clean(text.strip(), 
        tags=[],
        attributes=[],
        strip=True
        ).strip()


def sanitize_text(text: str) -> str:
    """
    Sanitize text by removing characters that do not conform to the allowed set:
    - Only contains alphanumeric characters, spaces, and selected special characters.
    
    Arguments:
        text (str): The input text to sanitize.
    
    Returns:
        str: The sanitized text.
    """
    text = unidecode(text.strip())  # Convert non-ASCII to closest ASCII representation

    # Define allowed characters and remove disallowed ones
    allowed_chars_pattern = re.compile(r'[^a-zA-Z0-9 ,.!?\-\'"]+')
    sanitized_text = allowed_chars_pattern.sub('', text)

    # Collapse multiple spaces caused by removed characters
    sanitized_text = re.sub(r'\s+', ' ', sanitized_text).strip()

    return sanitized_text


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
    return re.compile(r'^[a-zA-Z0-9_-]{3,25}$').match(username)


def sanitize_username(username: str) -> str:
    allowed_pattern = re.compile(r'[a-zA-Z0-9_-]')

    # Substitute any character not in the allowed set with an empty string
    return ''.join(allowed_pattern.findall(username))[:25]


def create_username_out_of_display_name(display_name: str) -> str:
    nonce = security_util.generate_nonce(5)
    
    display_name = nonce + unidecode(display_name.lower().strip())
    if ' ' not in display_name:
        return sanitize_username(display_name)[:config.MAX_USERNAME_LEN]
    
    # Gets the first name and initial of the last name
    return sanitize_username(display_name.split(' ')[0][:config.MAX_USERNAME_LEN - 1] + display_name.split(' ')[1][0])


def is_valid_email(email):
    # Regular expression for validating the local part of the email
    local_part_regex = r"^[a-zA-Z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-zA-Z0-9!#$%&'*+/=?^_`{|}~-]+)*$"
    
    # Regular expression for validating the domain part of the email
    domain_regex = r"^[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*$"
    
    # Check if the email contains only one '@' symbol
    if '@' not in email or email.count('@') != 1:
        return False
    
    # Split the email into local-part and domain
    local_part, domain = email.split('@')

    # Check if the local part length is within the allowed limit
    if len(local_part) > 64:
        return False

    # Check if the local part is valid
    if not re.match(local_part_regex, local_part):
        return False

    # Check if the domain length is within the allowed limit
    if len(domain) > 255:
        return False

    # Check if the domain is valid and has at least one period (.) to separate domain and TLD
    if not re.match(domain_regex, domain) or '.' not in domain:
        return False

    # Check if domain labels are within the limit of 63 characters each
    domain_labels = domain.split('.')
    for label in domain_labels:
        if len(label) > 63:
            return False

    # Additional check for disallowed patterns in the email
    # Check for consecutive dots or invalid characters like spaces or special symbols
    if '..' in email or ' ' in email or '!' in email or '@' in domain[0] or '@' in domain[-1]:
        return False

    return True


def is_strong_password(password: str) -> bool:
    """One regex check for all conditions:
    
    - At least 8 characters long and no more than 100 characters
    - Contains at least one uppercase letter
    - Contains at least one lowercase letter
    - Contains at least one digit
    - Contains at least one special character

    """
    return bool(re.match(r"^(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[!@#$%^&*(),.?\":{}|<>]).{8,100}$", password))


def is_valid_text(text: str) -> bool:
    """
    Sanitize text by ensuring it conforms to a set of rules:
    - Only contains alphanumeric characters, spaces, and selected special characters.
    - Is >= 3 characters and <= 1500 characters.
    
    """
    if not is_text_length_between((3, 1500), text):
        return False

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
        if all([result.scheme in ("http", "https"), result.netloc]):
            # Check if the netloc (domain) is valid using a regex
            netloc_regex = re.compile(r'^([A-Za-z0-9-]+\.)+[A-Za-z]{2,6}$')
            return bool(netloc_regex.match(result.netloc))
        return False
    except ValueError:
        return False


def is_safe_url(target: str) -> bool:
    allowed_domain = "infomundi.net"
    
    try:
        test_url = urlparse(target)
    except ValueError:
        return False
    
    if test_url.scheme != 'https':
        return False

    netloc = test_url.netloc.split(":")[0]  # Strip port

    # Ensure netloc ends with .infomundi.net
    if not netloc.endswith(f".{allowed_domain}"):
        return False

    # Extract the subdomain part (everything before ".infomundi.net")
    subdomain = netloc.removesuffix(f".{allowed_domain}")

    # Validate subdomain structure
    subdomain_regex = re.compile(r"^(?!-)(?!.*--)[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*(?<!-)$")

    if not subdomain or not subdomain_regex.fullmatch(subdomain):
        return False  # Reject malformed subdomains

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


def has_x_linebreaks(text: str, newlines: int=2) -> bool:
    """
    Check if the given text contains more than specified number of newlines (defaults to 2)
    """
    if not text:
        return False
    
    newline_count = text.count('\n') + text.count('<br>')
    return newline_count >= newlines


def obfuscate_email(email: str) -> str:
    # Split the email address into local part and domain part
    local, domain = email.split('@')
    
    # Obfuscate part of the local part
    if len(local) > 2:
        local_obfuscated = local[0] + '*' * (len(local) - 2) + local[-1]
    else:
        local_obfuscated = local[0] + '*'
    
    # Split the domain into name and TLD
    domain_name, domain_tld = domain.split('.')
    
    # Obfuscate part of the domain name
    if len(domain_name) > 2:
        domain_name_obfuscated = domain_name[0] + '*' * (len(domain_name) - 2) + domain_name[-1]
    else:
        domain_name_obfuscated = domain_name[0] + '*'
    
    # Combine the obfuscated parts
    obfuscated_email = f"{local_obfuscated}@{domain_name_obfuscated}.{domain_tld}"
    
    return obfuscated_email


def close_open_html_tags(html: str) -> str:
    """
    Ensures all open HTML tags are properly closed.
    """
    soup = BeautifulSoup(html, "html.parser")
    return str(soup)
