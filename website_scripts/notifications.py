import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from smtplib import SMTP

from . import config


def post_webhook(data: dict) -> bool:
    """Takes 'data' dictionary as argument, and posts to the mattermost webhook. Returns bool.
    
    Arguments:
        data: dict
            Information needed to create the embed message. Should have the following structure:
            {
                'text': 'some text'
            }

    Returns: 
        bool: True if we were able to POST the webhook, otherwise False.
    """

    try:
        response = requests.post(config.WEBHOOK_URL, json=data)
        response.raise_for_status()
    except Exception as err:
        return False

    return True


def send_email(recipient_email: str, subject: str, body: str, reply_to: str='noreply@infomundi.net', from_email: str='Infomundi <noreply@infomundi.net>') -> bool:
    """Takes the recipient email, the subject and the body of the email and sends it.
    
    Arguments:
        recipient_email: str
            Email address to send message to
        subject: str
            Email's subject
        body: str
            Email's message
        reply_to: str
            Reply-To address. Defaults to 'noreply@infomundi.net'
    
    Returns:
        bool: True if we were able to send the message, otherwise False.
    """
    
    # Create a message
    message = MIMEMultipart()
    message['From'] = from_email
    message['To'] = recipient_email
    message['Subject'] = subject
    message['Reply-To'] = reply_to
    message.attach(MIMEText(body, 'plain'))

    try:
        with SMTP(config.SMTP_SERVER, config.SMTP_PORT) as server:
            server.starttls()  # Upgrade the connection to secure TLS
            server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)

            # Send the email
            server.sendmail(config.SMTP_USERNAME, recipient_email, message.as_string())
    except Exception as e:
        return False

    return True
