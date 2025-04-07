import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


from website_scripts import input_sanitization


@pytest.mark.parametrize("input_text, expected", [
    ("Hello, world!", "Hello, world!"),  # Plain text (no HTML entities)
    ("Hello, &amp; world!", "Hello, & world!"),  # Single encoding
    ("Hello, &amp;amp; world!", "Hello, & world!"),  # Double encoding
    ("Hello, &amp;amp;amp; world!", "Hello, & world!"),  # Triple encoding
    ("&lt;p&gt;Test&amp;Check&lt;/p&gt;", "<p>Test&Check</p>"),  # Mixed entities
    ("&#65;&#66;&#67;", "ABC"),  # Numeric character references
    ("This is a test &quot;string&quot; with &#39;quotes&#39;.", "This is a test \"string\" with 'quotes'."),  # HTML entities in a complex string
    ("This is a normal string.", "This is a normal string."),  # Already decoded string remains unchanged
    ("&amp;&amp;&amp;", "&&&"),  # Only entity characters
    ("", ""),  # Empty string
])
def test_decode_html_entities(input_text, expected):
    assert input_sanitization.decode_html_entities(input_text) == expected


@pytest.mark.parametrize("description, expected", [
    # 1. Plain text should remain unchanged
    ("Hello, world!", "Hello, world!"),
    
    # 2. Allowed HTML tags should be preserved
    ("<p>Hello</p>", "<p>Hello</p>"),
    ("<b>Bold</b>", "<b>Bold</b>"),
    ("<i>Italic</i>", "<i>Italic</i>"),
    ("<a href='https://example.com'>Link</a>", "<a href=\"https://example.com\">Link</a>"),
    
    # 3. Disallowed tags should be stripped
    ("<script>alert('XSS');</script>", "alert('XSS');"),
    ("<iframe src='https://malicious.com'></iframe>", ""),
    ("<img src='image.jpg' onerror='alert(1)'>", ""),
    
    # 4. Attributes outside the allowed list should be removed
    ("<a href='https://example.com' onclick='alert(1)'>Click me</a>", "<a href=\"https://example.com\">Click me</a>"),
    
    # 5. Empty input should return an empty string
    ("", ""),
    
    # 6. Spaces around input should be stripped
    ("  Hello, world!  ", "Hello, world!"),
    
    # 7. Complex nested allowed tags should be preserved
    ("<p><b>Bold <i>and Italic</i></b></p>", "<p><b>Bold <i>and Italic</i></b></p>"),
    
    # 8. Multiple disallowed tags mixed with allowed ones
    ("<p>Hello <script>alert('XSS')</script> World</p>", "<p>Hello alert('XSS') World</p>"),
    
    # 9. Numeric character references should be preserved
    ("&lt;p&gt;Test&amp;Check&lt;/p&gt;", "&lt;p&gt;Test&amp;Check&lt;/p&gt;"),
    
    # 10. Unclosed tags should be handled gracefully
    ("<b>Bold text", "<b>Bold text</b>")
])
def test_sanitize_description(description, expected):
    assert input_sanitization.sanitize_description(description) == expected


@pytest.mark.parametrize("input_text, expected_output", [
    ("Hello, world!", "Hello, world!"),  # No HTML
    ("<b>Bold Text</b>", "Bold Text"),  # Stripped allowed HTML
    ("<script>alert('XSS')</script>", "alert('XSS')"),  # XSS attempt
    ("Normal text <i>italic</i>", "Normal text italic"),  # Stripped italic
    ("Click <a href='http://example.com'>here</a>", "Click here"),  # Stripped anchor
    ("<p>This is a paragraph.</p>", "This is a paragraph."),  # Stripped paragraph
    ("<img src='image.jpg'/> Image", "Image"),  # Removed image
    ("<div>Block content</div>", "Block content"),  # Removed div
    ("<script>evil()</script> script", "evil() script"),  # Stripped script
    ("     <h1> Heading </h1>    ", "Heading"),  # Stripped heading, trims spaces
    ("Some text <unknown>with tag</unknown>", "Some text with tag"),  # Stripped unknown tag
    ("<style>body { color: red; }</style> Styled text", "body { color: red; } Styled text"),  # Removed style
    ("<a href=\"javascript:alert(1)\">Click me</a>", "Click me"),  # JavaScript attack
    ("", ""),  # Empty string
])
def test_sanitize_html(input_text, expected_output):
    assert input_sanitization.sanitize_html(input_text) == expected_output


@pytest.mark.parametrize("input_text, expected_output", [
    # Test case 1: Plain text (no special characters)
    ("Hello world", "Hello world"),

    # Test case 2: Text with allowed punctuation
    ("Hello, world!", "Hello, world!"),

    # Test case 3: Text with special characters that should be removed
    ("Hello @#$%^&*()_+=", "Hello"),

    # Test case 4: Text with accented characters (should be converted)
    ("Café naïve façade", "Cafe naive facade"),

    # Test case 5: Numbers and valid characters should remain unchanged
    ("Price: $100.99!", "Price 100.99!"),

    # Test case 6: Text with emojis (should be removed)
    ("Hello 😊🎉🔥", "Hello"),

    # Test case 7: Mixed text with allowed and disallowed characters
    ("Hello, world! 🚀 @2025", "Hello, world! 2025"),

    # Test case 8: Newlines and tabs should be removed
    ("Hello\nWorld\t!", "HelloWorld!"),

    # Test case 9: String with non-Latin characters (should be removed)
    ("Привет мир こんにちは世界", "Privet mir konnichihaShi Jie"),

    # Test case 10: Empty string should remain empty
    ("", ""),
])
def test_sanitize_text(input_text, expected_output):
    assert input_sanitization.sanitize_text(input_text) == expected_output


@pytest.mark.parametrize("input_username, expected_output", [
    # Valid usernames (should remain unchanged)
    ("John_Doe-123", "John_Doe-123"),
    ("abcdefXYZ", "abcdefXYZ"),
    ("1234567890", "1234567890"),
    ("____", "____"),
    ("----", "----"),
    ("User_2025-Test", "User_2025-Test"),

    # Spaces & special characters should be removed
    ("John Doe", "JohnDoe"),
    ("Us3r!@#N@m3", "Us3rNm3"),
    ("U$er_Na%me-!99", "Uer_Name-99"),
    ("Cool😎User", "CoolUser"),
    ("hello.world,test", "helloworldtest"),

    # Non-English characters should be removed
    ("你好世界", ""),
    ("Привет-мир", "-"),
    ("مرحبا_بالعالم", "_"),

    # Entirely invalid usernames should be removed completely
    ("!@#$%^&*()=+", ""),
    ("   user123   ", "user123"),
    ("user\t123\n", "user123"),
    ("user\x00name", "username"),
    ("@username!", "username"),
    ("<username>", "username"),
    ("user/name\\test", "usernametest"),
])
def test_sanitize_username(input_username, expected_output):
    assert input_sanitization.sanitize_username(input_username) == expected_output


@pytest.mark.parametrize("email, expected_output", [
    # Valid cases
    ("user@example.com", True),
    ("user@mail.example.co.uk", True),
    ("user123@example.com", True),
    ("user.name+test@example.com", True),
    ("user@x.co", True),
    ("first-last@my-domain.com", True),
    ("user_name@example.com", True),

    # Invalid cases
    ("invalid-email.com", False),  # No @
    ("user@@example.com", False),  # Multiple @
    ("", False),  # Empty string
    ("user @example.com", False),  # Space in email
    (" user@example.com ", False),  # Leading/trailing spaces
    ("user@example", False),  # No TLD
    ("user@example..com", False),  # Double dot in domain
    ("user!@example.com", False),  # Special character in local part
    ("user@example#.com", False),  # Special character in domain
    (".user@example.com", False),  # Starts with a dot
    ("user.@example.com", False),  # Ends with a dot
    ("@example.com", False),  # No local part
    ("user@", False),  # No domain part
    ("a" * 320 + "@example.com", False),  # Exceeds max length
])
def test_is_valid_email(email, expected_output):
    assert input_sanitization.is_valid_email(email) == expected_output, f"Failed for email: {email}"


@pytest.mark.parametrize("url, expected", [
    # Valid URLs
    ("https://google.com/", True),
    ("http://example.com", True),
    ("https://infomundi.net", True),
    
    # Invalid URLs (Invalid schemes)
    ("ftp://example.com", False),
    ("file://localhost", False),
    
    # Missing scheme (assuming 'http' is the default)
    ("www.google.com", False),
    ("google.com", False),
    
    # URLs with special characters or malformed structure
    ("http://example.com:8080/path", False),  # Valid with port and path (edited)
    ("https://example.com/?query=test#fragment", True),  # Valid with query and fragment
    
    # URLs with invalid characters
    ("http://ex@mpl@.com", False),
    ("https://example!.com", False),
    
    # Invalid netloc (empty domain or invalid domain name)
    ("http://", False),  # Missing netloc
    ("http://.com", False),  # Missing domain
    ("http://example..com", False),  # Double dots in domain
    
    # Non-standard domains (e.g., with country codes)
    ("https://example.co.uk", True),  # Valid with country code TLD
    
    # Edge cases
    ("http://a.com", True),  # Valid single character domain
    ("https://a.b", False),  # Invalid domain with only one part
    
    # Invalid URLs that raise ValueError
    ("http://[::1]", False),  # IPv6 link-local address
    ("not-a-url", False),  # Completely malformed string
])
def test_is_valid_url(url, expected):
    assert input_sanitization.is_valid_url(url) == expected


@pytest.mark.parametrize("html, expected", [
    ("<p>Test", "<p>Test</p>"),  # Single unclosed tag
    ("<div><span>Content", "<div><span>Content</span></div>"),  # Nested unclosed tags
    ("<b>Bold <i>Italic", "<b>Bold <i>Italic</i></b>"),  # Inline elements
    ("<table><tr><td>Data", "<table><tr><td>Data</td></tr></table>"),  # Table structures
    ("Plain text", "Plain text"),  # No HTML at all
    ("<p>Paragraph</p>", "<p>Paragraph</p>"),  # Already well-formed HTML
    ("<div><p>Nested</div>", "<div><p>Nested</p></div>"),  # Mixed well-formed and unclosed tags
    ("<br><hr>", "<br/><hr/>"),  # Self-closing tags remain unchanged
    ("", ""),  # Empty string should remain empty
])
def test_close_open_html_tags(html, expected):
    assert input_sanitization.close_open_html_tags(html) == expected


@pytest.mark.parametrize("target, expected", [
    # Valid cases
    ("https://sub.infomundi.net", True),
    ("https://deep.sub.infomundi.net", True),
    ("https://another.sub.infomundi.net", True),
    
    # Invalid scheme
    ("http://sub.infomundi.net", False),
    ("ftp://sub.infomundi.net", False),
    ("", False),
    ("sub.infomundi.net", False),  # Missing scheme
    ("//sub.infomundi.net", False),  # Missing scheme but valid domain
    
    # Invalid domain
    ("https://infomundi.com", False),
    ("https://evil.infomundi.com", False),
    ("https://infomundi.net.evil.com", False),  # Looks similar but isn't valid
    ("https://example.com", False),
    ("https://sub.example.com", False),
    
    # Edge cases
    ("https://infomundi.net", False),  # Root domain not allowed per function logic
    ("https://INFOMUNDI.NET", False),  # Case sensitivity check
    ("https://sub.infomundi.net:8080", True),  # Allowed with port
    ("https://sub.infomundi.net/path", True),  # Allowed with path
    ("https://sub.infomundi.net?query=1", True),  # Allowed with query params
    ("https://sub.infomundi.net/#fragment", True),  # Allowed with fragment
    ("https://sub..infomundi.net", False),  # Double dots (invalid subdomain)
    ("https://-sub.infomundi.net", False),  # Invalid subdomain starting with '-'
    ("https://sub-.infomundi.net", False),  # Invalid subdomain ending with '-'
    ("https://.infomundi.net", False),  # Starts with a dot (invalid)
    ("https://..infomundi.net", False),  # Multiple leading dots (invalid)
    ("https://sub_infomundi.net", False),  # Underscore in domain
    ("https://sub.infomundi.net%00.evil.com", False),  # Null byte attack
    ("https://xn--sub-infomundi.net", False),  # IDN homograph attack attempt
])
def test_is_safe_url(target, expected):
    assert input_sanitization.is_safe_url(target) == expected


if __name__ == "__main__":
    pytest.main()
