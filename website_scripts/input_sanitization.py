import bleach
import html
import re

from html.parser import HTMLParser
from urllib.parse import urlparse
from unidecode import unidecode
from collections import deque

from . import security_util, config


def decode_html_entities(text):
    """
    Decodes a string of HTML entities until it no longer changes. Returns the decoded string.
    """
    # Check if the text changes after the first decode
    decoded_once = html.unescape(text)
    
    if text == decoded_once:
        # No change after first decode, text is plain
        return text
    
    # Check if the text changes again after a second decode
    decoded_twice = html.unescape(decoded_once)
    if decoded_once == decoded_twice:
        # No change after the second decode, text is single-encoded
        return decoded_once
    
    # Text changes after second decode, text is double-encoded
    return decoded_twice


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
        )


def sanitize_text(text: str) -> str:
    """
    Sanitize text by removing characters that do not conform to the allowed set:
    - Only contains alphanumeric characters, spaces, and selected special characters.
    
    Arguments:
        text (str): The input text to sanitize.
    
    Returns:
        str: The sanitized text.
    """
    text = unidecode(text.strip())
    
    # Define the allowed characters using a regex pattern
    allowed_chars_pattern = re.compile(r'[^a-zA-Z0-9 ,.!?:\-\'"]')
    
    # Substitute any character not in the allowed set with an empty string
    sanitized_text = allowed_chars_pattern.sub('', text)
    
    return sanitized_text


def sanitize_username(username: str) -> str:
    allowed_pattern = re.compile(r'[a-zA-Z0-9_-]')

    # Substitute any character not in the allowed set with an empty string
    return ''.join(allowed_pattern.findall(username))


def create_username_out_of_display_name(display_name: str) -> str:
    nonce = security_util.generate_nonce(5)
    
    display_name = nonce + unidecode(display_name.lower().strip())
    if ' ' not in display_name:
        return sanitize_username(display_name)[:config.MAX_USERNAME_LEN]
    
    # Gets the first name and initial of the last name
    return sanitize_username(display_name.split(' ')[0][:config.MAX_USERNAME_LEN - 1] + display_name.split(' ')[1][0])


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


def is_strong_password(password: str) -> bool:
    # One regex check for all conditions:
    # - At least 8 characters long and no more than 50 characters
    # - Contains at least one uppercase letter
    # - Contains at least one lowercase letter
    # - Contains at least one digit
    # - Contains at least one special character
    return bool(re.match(r"^(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[!@#$%^&*(),.?\":{}|<>]).{8,50}$", password))


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
        if all([result.scheme == "https", result.netloc]):
            # Check if the netloc (domain) is valid using a regex
            netloc_regex = re.compile(r'^([A-Za-z0-9-]+\.)+[A-Za-z]{2,6}$')
            return bool(netloc_regex.match(result.netloc))
        return False
    except ValueError:
        return False


def is_safe_url(target: str) -> bool:
    """
    Checks if the target URL is safe by confirming it matches a specific domain.
    
    Arguments:
        target (str): A target URL.
    
    Returns:
        bool: True if the URL is safe, False otherwise.
    """
    allowed_domains = ("infomundi.net", "commento.infomundi.net", "bucket.infomundi.net")
    
    try:
        test_url = urlparse(target)
    except ValueError:
        return False
    
    # Ensure the URL scheme is http or https
    if test_url.scheme != 'https':
        return False
    
    # Check if the netloc is exactly in the allowed domains
    if test_url.netloc not in allowed_domains:
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


def close_open_html_tags(html_string: str) -> str:
    """
    Closes any unclosed HTML tags in the provided HTML string.

    Args:
        html_string (str): The HTML string to check and correct for unclosed tags.

    How it works:
        - The function defines a set of valid HTML tags that it will check for closure.
        - It uses an inner HTML parser class (`SimpleHTMLParser`) to parse the HTML string.
        - The parser tracks open tags using a stack.
        - When it encounters a closing tag, it ensures all open tags up to that point are closed.
        - After parsing, it ensures any remaining open tags in the stack are closed.
        - Only specified tags are considered (['p', 'b', 'i', 'u', 'em', 'strong', 'a', 'br']).

    Returns:
        str: The corrected HTML string with all tags properly closed.

    Examples:
        >>> close_open_html_tags("<p>Some text<b>bold text<i>italic text</b>unclosed italic<p>Another paragraph")
        '<p>Some text<b>bold text<i>italic text</i></b>unclosed italic</p><p>Another paragraph</p>'
    """
    valid_tags = {'p', 'b', 'i', 'u', 'em', 'strong', 'a', 'br'}
    self_closing_tags = {'br'}
    stack = deque()
    result = []

    class SimpleHTMLParser(HTMLParser):
        def handle_starttag(self, tag, attrs):
            if tag in valid_tags:
                result.append(f'<{tag}')
                for attr, value in attrs:
                    result.append(f' {attr}="{value}"')
                result.append('>')
                if tag not in self_closing_tags:
                    stack.append(tag)

        def handle_endtag(self, tag):
            if tag in valid_tags:
                while stack and stack[-1] != tag:
                    unclosed_tag = stack.pop()
                    result.append(f'</{unclosed_tag}>')
                if stack:
                    stack.pop()
                result.append(f'</{tag}>')

        def handle_data(self, data):
            result.append(data)

        def handle_entityref(self, name):
            result.append(f'&{name};')

        def handle_charref(self, name):
            result.append(f'&#{name};')

        def handle_comment(self, data):
            result.append(f'<!--{data}-->')

        def handle_decl(self, decl):
            result.append(f'<!{decl}>')

        def handle_pi(self, data):
            result.append(f'<?{data}>')

    parser = SimpleHTMLParser()
    parser.feed(html_string)
    
    while stack:
        unclosed_tag = stack.pop()
        result.append(f'</{unclosed_tag}>')
    
    return ''.join(result)
