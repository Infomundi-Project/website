#!/bin/bash

# /usr/bin/echo -e "\e[32mThis is a green text\e[0m"
# /usr/bin/echo -e "\e[33mThis is a yellow text\e[0m"
# /usr/bin/echo -e "\e[31mThis is a red text\e[0m"

if [ "$EUID" -ne 0 ]; then
  /usr/bin/echo -e "\e[31m[Fatal Error] This script must be run as root.\e[0m"
  exit 1
else
  /usr/bin/echo "[~] Starting setup process for Infomundi..."
fi

WEBSITE_ROOT_PATH=$(/usr/bin/pwd)

# Step 1: Create cache folder
/usr/bin/mkdir -p data/news/cache
/usr/bin/mkdir logs

# Step 2: Install required software
/usr/bin/echo -e "\e[32m[+] Updating...\e[0m"
/usr/bin/apt update -y &>/dev/null
/usr/bin/echo -e "\e[32m[+] Upgrading installed packages...\e[0m"
/usr/bin/apt upgrade -y &>/dev/null
/usr/bin/echo -e "\e[32m[+] Installing required software...\e[0m"
/usr/bin/apt install -y python3 python3-pip python3-venv apache2 libapache2-mod-wsgi-py3 &>/dev/null

# Step 3: Create python virtual environment and install dependencies
/usr/bin/echo -e "\e[32m[+] Creating python3 virtual environment at $WEBSITE_ROOT_PATH/.venv\e[0m"
/usr/bin/python3 -m venv $WEBSITE_ROOT_PATH/.venv
source $WEBSITE_ROOT_PATH/.venv/bin/activate
/usr/bin/echo -e "\e[32m[+] Installing python3 dependencies...\e[0m"
$WEBSITE_ROOT_PATH/.venv/bin/pip3 install -r requirements.txt &>/dev/null
deactivate

# Step 4: Collect data from the user
/usr/bin/echo -e -n "\e[33m[~] Discord Webhook URL:\e[0m "
read DISCORD_WEBHOOK_URL

/usr/bin/echo -e -n "\e[33m[~] HCaptcha Secret Key:\e[0m "
read CAPTCHA_SECRET_KEY

/usr/bin/echo -e -n "\e[33m[~] App Secret Key (make it random and very secure):\e[0m "
read APP_SECRET_KEY

# Step 5: Configure website_scripts/config.py
CONFIG_FILE="website_scripts/config.py"

CONFIG_STATEMENTS=$(/usr/bin/cat <<-END
from . import json_util

COUNTRY_LIST = json_util./usr/bin/read_json('$WEBSITE_ROOT_PATH/data/json/countries')
NICKNAME_LIST = json_util./usr/bin/read_json('$WEBSITE_ROOT_PATH/data/json/nicknames')

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

/usr/bin/echo -e "$CONFIG_STATEMENTS" > "$CONFIG_FILE"
/usr/bin/echo -e "\e[32m[+] Configuration statements added to $CONFIG_FILE\e[0m"

# Step 6: Create infomundi.wsgi
INFOMUNDI_WSGI_FILE="$WEBSITE_ROOT_PATH/infomundi.wsgi"

WSGI_STATEMENTS=$(/usr/bin/cat <<-END
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

/usr/bin/echo -e "$WSGI_STATEMENTS" > "$INFOMUNDI_WSGI_FILE"
/usr/bin/echo -e "\e[33m[+] infomundi.wsgi\e[0m created at \e[32m$INFOMUNDI_WSGI_FILE\e[0m"

# Step 7: Create infomundi.net.conf
APACHE_CONFIG_FILE="/etc/apache2/sites-available/infomundi.net.conf"

APACHE_CONFIG_STATEMENTS=$(/usr/bin/cat <<-END
<VirtualHost *:80>
        ServerName  infomundi.net
        ServerAdmin contact@infomundi.net
        DocumentRoot $WEBSITE_ROOT_PATH
 
        WSGIDaemonProcess infomundi threads=5
        WSGIScriptAlias / $WEBSITE_ROOT_PATH/infomundi.wsgi
        WSGIApplicationGroup %{GLOBAL}
        <Directory website>
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

/usr/bin/echo -e "$APACHE_CONFIG_STATEMENTS"> "$APACHE_CONFIG_FILE"
/usr/bin/echo -e "\e[33m[+] infomundi.net.conf\e[0m created at \e[32m$APACHE_CONFIG_FILE\e[0m"

# Step 8: Enable site

if a2ensite_path=$(which a2ensite); then
  $a2ensite_path infomundi.net
else
  /usr/bin/echo -e "\e[31m[Fatal Error] a2ensite was not found.\e[0m"
  exit 1
fi

# Step 9: Change permissions
/usr/bin/chown -R www-data:www-data $WEBSITE_ROOT_PATH
/usr/bin/chmod -R 770 $WEBSITE_ROOT_PATH

# Step 10: Restart apache2
/usr/bin/systemctl restart apache2

/usr/bin/echo "[+] Website configured and Apache restarted. Everything should be ready."
