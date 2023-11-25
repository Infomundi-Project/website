#!/bin/bash

# echo -e "\e[32mThis is a green text\e[0m"
# echo -e "\e[33mThis is a yellow text\e[0m"
# echo -e "\e[31mThis is a red text\e[0m"

if [ "$EUID" -ne 0 ]; then
  echo "\e[31m[Fatal Error] This script must be run as root.\e[0m"
  exit 1
else
  echo "[~] Starting setup process for Infomundi..."
fi

WEBSITE_ROOT_PATH=$(pwd)

# Step 1: Create cache folder
mkdir -p data/news/cache

# Step 2: Install required software
apt update -y && apt upgrade -y
apt install -y python3 python3-pip python3-venv apache2 libapache2-mod-wsgi-py3

# Step 3: Install python dependencies
pip3 install -r requirements.txt

# Step 4: Collect data from the user
echo -n "\e[33m[~] Discord Webhook URL:\e[0m "
read DISCORD_WEBHOOK_URL

echo -n "\e[33m[~] HCaptcha Secret Key:\e[0m "
read CAPTCHA_SECRET_KEY

echo -n "\e[33m[~] App Secret Key (make it random and very secure):\e[0m "
read APP_SECRET_KEY

# Step 5: Configure website_scripts/config.py
CONFIG_FILE="website_scripts/config.py"

CONFIG_STATEMENTS=$(cat <<-END
from . import json_util

COUNTRY_LIST = json_util.read_json('$WEBSITE_ROOT_PATH/data/json/countries')
NICKNAME_LIST = json_util.read_json('$WEBSITE_ROOT_PATH/data/json/nicknames')

CACHE_PATH = '$WEBSITE_ROOT_PATH/data/news/cache'
FEEDS_PATH = '$WEBSITE_ROOT_PATH/data/news/feeds'
COMMENTS_PATH = '$WEBSITE_ROOT_PATH/data/json/comments'
STATISTICS_PATH = '$WEBSITE_ROOT_PATH/data/json/statistics'
USERS_PATH = '$WEBSITE_ROOT_PATH/data/json/users'
TELEMETRY_PATH = '$WEBSITE_ROOT_PATH/data/json/telemetry'

CAPTCHA_SECRET_KEY = '$CAPTCHA_SECRET_KEY'
APP_SECRET_KEY = '$APP_SECRET_KEY'

EMAIL_PASSWORD = ''
SMTP_SERVER = ''
SMTP_PORT = 465

# Webhook
WEBHOOK_URL = '$DISCORD_WEBHOOK_URL'
END
)

echo -e "$CONFIG_STATEMENTS" > "$CONFIG_FILE"
echo -e "\e[32m[+] Configuration statements added to $CONFIG_FILE\e[0m // \e[33mChange CAPTCHA_SECRET_KEY and APP_SECRET_KEY accordingly\e[0m"

# Step 6: Create infomundi.wsgi
INFOMUNDI_WSGI_FILE="$WEBSITE_ROOT_PATH/infomundi.wsgi"

WSGI_STATEMENTS=$(cat <<-END
import logging
import sys

sys.path.insert(0, '$WEBSITE_ROOT_PATH')
sys.path.insert(0, '$WEBSITE_ROOT_PATH/.venv/lib/python3.11/site-packages/')

# Set up logging
logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

# Import and run the Flask app
from app import app as application
END
)

echo -e "$WSGI_STATEMENTS" > "$INFOMUNDI_WSGI_FILE"
echo -e "\e[33m[+] infomundi.wsgi\e[0m \e[32mcreated at $INFOMUNDI_WSGI_FILE\e[0m"

# Step 7: Create infomundi.net.conf
APACHE_CONFIG_FILE="/etc/apache2/sites-available/infomundi.net.conf"

APACHE_CONFIG_STATEMENTS=$(cat <<-END
<VirtualHost *:80>
        ServerName  infomundi.net
        ServerAdmin contact@infomundi.net
        DocumentRoot $WEBSITE_ROOT_PATH
 
        WSGIDaemonProcess infomundi threads=5
        WSGIScriptAlias / $WEBSITE_ROOT_PATH/infomundi.wsgi
        WSGIApplicationGroup %{GLOBAL}
        <Directory $WEBSITE_ROOT_PATH>
             WSGIProcessGroup infomundi
             WSGIApplicationGroup %{GLOBAL}
             Order deny,allow
             Allow from all
        </Directory>
 
        ErrorLog $WEBSITE_ROOT_PATH/logs/infomundi-error.log
        CustomLog $WEBSITE_ROOT_PATH/logs/infomundi-access.log combined
</VirtualHost>
END
)

echo -e "$APACHE_CONFIG_STATEMENTS"> "$APACHE_CONFIG_FILE"
echo -e "\e[33m[+] infomundi.net.conf\e[0m \e[32mcreated at $APACHE_CONFIG_FILE\e[0m"

# Step 8: Enable the site
a2ensite infomundi.net

# Step 9: Restart apache2
service apache2 restart

echo "[+] Website configured and Apache restarted. Visit http://infomundi.net."
