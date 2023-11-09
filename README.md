# Infomundi
InfoMundi utilizes various global media channels to cover international news, developing a community dedicated to staying well-informed about global affairs.

This is the repository that holds all the necessary code and assets for running InfoMundi.

## Clone
`git clone git@github.com:Infomundi-Project/website.git`

## Configuration and Start
1. Create a folder to hold cache: `cd website && mkdir data/news/cache`
2. Install required software: `sudo apt install python3 python3-pip python3-venv`
3. Install python dependencies: `pip3 install -r requirements.txt`
4. Add configuration statements to `website_scripts/config.py` as follows

```python
from . import scripts

COUNTRY_LIST = scripts.read_json('<WEBSITE-ROOT-PATH>/data/json/countries')

CACHE_PATH = '<WEBSITE-ROOT-PATH>/data/news/cache'
FEEDS_PATH = '<WEBSITE-ROOT-PATH>/data/news/feeds'
COMMENTS_PATH = '<WEBSITE-ROOT-PATH>/data/json/comments'
STATISTICS_PATH = '<WEBSITE-ROOT-PATH>/data/json/statistics'

CAPTCHA_SECRET_KEY = 'HCAPTCHA_SECRET_KEY'
APP_SECRET_KEY = 'APP_SECRET_KEY'
```

5. Install apache2 and required wsgi module to work with python3: `apt install apache2 libapache2-mod-wsgi-py3`

6. Create `infomundi.wsgi`

```python
import logging
import sys

sys.path.insert(0, '<WEBSITE-ROOT-PATH>')
sys.path.insert(0, '<WEBSITE-ROOT-PATH>/.venv/lib/python3.11/site-packages/')
 
# Set up logging
logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
 
# Import and run the Flask app
from app import app as application
```

7. Create `/etc/apache2/sites-available/infomundi.net.conf`

```
<VirtualHost *:80>
        ServerName  infomundi.net
        ServerAdmin contact@infomundi.net
        DocumentRoot <WEBSITE-ROOT-PATH>
 
        WSGIDaemonProcess infomundi threads=5
        WSGIScriptAlias / <PATH-TO-WSGI-SCRIPT>/infomundi.wsgi
        WSGIApplicationGroup %{GLOBAL}
        <Directory infomundi>
             WSGIProcessGroup infomundi
             WSGIApplicationGroup %{GLOBAL}
             Order deny,allow
             Allow from all
        </Directory>
 
        ErrorLog <WEBSITE-PATH>/logs/infomundi-error.log
        CustomLog <WEBSITE-PATH>/logs/infomundi-access.log combined
</VirtualHost>
```

7. Enable the site: `a2ensite infomundi.net`
8. Restart apache2 (or start if it was not running already)