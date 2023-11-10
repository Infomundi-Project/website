# Changelog

## History

| Version | Date       | Brief Description      | Authors        |
| ------ | ---------- | ----------------------------- | ------------- |
| 1.1.1 | 2023/11/10 | Key enhancements include improved HTML structure in registration and admin pages, preventing HTML tags in story descriptions, and a more professional navbar. Changes involve pagination color in `rss_template.html`, optimized comment form validation, visual adjustments in the news page, and a shift to black-themed news cards. Removed two html files, no fixes were made, and there are no specific security updates in this release.  | @behindsecurity |
| 1.1.0 | 2023/11/08 | Changed the way information is displayed in this file. Improved templates, SEO, script optimization, Apache WSGI, autocomplete, `flask-gzip`, layout enhancements, stats tab, image retrieval, auth prefix, secret key change, os.environ removal, bug fixes, and security mitigation.  | @behindsecurity |
| 1.0.1 | 2023/10/28 | Basically improved performance and made the code more modularized. | @behindsecurity |


## 1.1.1: 2023/11/10

### Enhancements (3)
- IME01: `register.html, admin.html and password_change.html` now extends from `base.html`.
- IME02: Added a filter to prevent html tags from appearing in stories descriptions.
- IME03: The navbar is now more professional.

### Changed (5)
- IMC01: `rss_template.html` pagination, now it turns into blue when the user is in the selected page.
- IMC02: `static/js/validateCommentForm.js` created to enhance optimization (`comments.html`).
- IMC03: Added a border to the Translate element on the news page.
- IMC04: Changed the way the upper text is presented in the news page.
- IMC05: News cards are now black-themed.

### Removed (0)
- IMR01: Removed `404.html` and `loading.html` as they were no longer needed.

### Fixed (0)
- IMF01:

### Security (0)
- IMS01:


## 1.1.0: 2023/11/08 (Major)

### Enhancements (11)
- IME01: All HTML templates extends from `base.html` for better performance and code modularization.
- IME02: Added SEO Meta tags to the `base.html` template.
- IME03: Script rendering optimization on supported scripts (example: `<script defer src="/static/js/autocomplete.js"></script>`).
- IME04: Support for Apache WSGI.
- IME05: Added autocomplete functionality to the "search for countries" form (`/autocomplete` endpoint and `/static/js/autocomplete.js` file).
- IME06: Now we use Flask's `flash()` messages to display error and success messages to the users.
- IME07: Added support for `flask-gzip` to provide content-encoding and enhance performance.
- IME08: Improvements on the layout of `rss_template.html`, `homepage.html` and `comments.html`.
- IME09: Added a message to indicate that there are no comments on the selected story yet.
- IME10: Added a statistics tab containing useful information about the website, for example the local time, total of supported countries, when it was last updated and more (file: `website_scripts/scripts.py` function: `get_statistics`).
- IME11: If the story has no image, when the user clicks to open the comments tab for that story, it makes a request to the story URL and gets its image, sucessfully replacing the infomundi logo for the related image in the cache file. That means, now the story has a image being displayed for everybody.

### Changed (2)
- IMC01: Added /auth prefix for authentication-required endpoints.
- IMC02: App secret key no longer uses os.urandom, but an ordinary string. This was required to fix **IMF01**.

### Removed (1)
- IMR01: Removed the usage of os.environ, instead we are now using config.py to hold all configuration-related variables

### Fixed (2)
- IMF01: Bug that was disconnecting admin users from their account right after login, some configuration statements were added to the `Flask()` app.py.
- IMF02: rss_template.html not fitting well on mobile, added a container-fluid div to solve this issue.

### Security (1)
- IMS01: Fixed a `medium` severity vulnerability where malicious actors could cause a great negative impact in performance by changing the ID of the story to something really big in the form to add a comment to a story. Code snippet (file: views.py // function: add_comments):

```python
if len(news_id) != 32 or search_regex(r'[A-Z]', news_id) or search_regex(r'[\'"!@#$%^&*()_+{}\[\]:;<>,.?~\\/-]', news_id):
	return # returns a message
```


## 1.0.1: 2023/10/28

### Added
- Added comments to explain the purpose of functions and specific blocks of code 
- The total amount of comments now appear right next to the comments balloon on each news
- New create_comment_id() (scripts.py) function to generate comments ID 

### Changed
- Compressed relevant png images to obtain better performance
- Deleted static/js/main.js static/js/index.js static/js/brmap.js static/css/style.css static/css/main.css static/img/earth.png as they were not needed
- Moved create_cache.py to the main folder
- Major changes in create_cache.py script

### Fixed
- Bug when importing scripts.read_json from config.py
- Bug /add_comments endpoint writing to wrong comments file 
- Feed URLs from many countries were not actually correct, now has been fixed
- Bug that content was not fitting into the page correctly, added a container-fluid div to rss_template


## 1.0.0: 2023/10/24

### Added
- Initial release

### Changed
- Initial release

### Fixed
- Initial release