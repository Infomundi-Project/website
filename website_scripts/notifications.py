import requests
from email.mime.multipart import MIMEMultipart
from smtplib import SMTP_SSL, SMTPException
from email.mime.text import MIMEText

from . import config


def post_webhook(data: dict) -> bool:
    """
    Takes 'data' dictionary as argument, and posts to the mattermost webhook. Returns bool.
    
    Arguments
        data: dict
            Information needed to create the embed message. Should have the following structure:
            {
                'text': 'some text'
            }
    """

    # Make the HTTP POST request to the Discord webhook URL
    response = requests.post(config.WEBHOOK_URL, json=data)

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as err:
        return False
    else:
        return True


def send_email(recipient_email: str, subject: str, body: str) -> bool:
    """Takes the recipient email, the subject and the body of the email and sends it. 

    Returns bool."""
    
    # Email credentials
    sender_email = "contact@infomundi.net"

    # Server information
    smtp_server = config.SMTP_SERVER
    smtp_port = config.SMTP_PORT

    # Create a message
    message = MIMEMultipart()
    message['From'] = 'Infomundi <noreply@infomundi.net>'
    message['To'] = recipient_email
    message['Subject'] = subject
    message['Reply-To'] = 'noreply@infomundi.net'
    message.attach(MIMEText(body, 'plain'))

    try:
        with SMTP_SSL(smtp_server, smtp_port) as server:
            # Log in to the email account
            server.login(sender_email, config.EMAIL_PASSWORD)

            # Send the email
            server.sendmail(sender_email, recipient_email, message.as_string())
    except SMTPException as e:
        return False

    return True