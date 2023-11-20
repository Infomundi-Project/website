from email.mime.multipart import MIMEMultipart
from requests import post as post_request
from email.mime.text import MIMEText
from smtplib import SMTP_SSL

from . import config

def post_webhook(data: dict) -> bool:
    """
    Takes 'data' dictionary as argument, makes an embed message and sends to the discord webhook. Returns bool.
    
    Arguments
        data: dict
            Information needed to create the embed message. Should have the following structure:
            {
                'embed': {
                    'title': 'title',
                    'description': 'description',
                    'color': 0xHEXADECIMAL_COLOR,
                    'fields': [
                        {'name': 'field_name', 'value': 'field_value', 'inline': bool}
                    ],
                    'footer': {'text': 'footer_text'}
                },
                'message': 'optional message to send along with the embed'
            }
    """

    # Create a dictionary with the message content
    payload = {
        'content': data['message'],
        "embeds": [data['embed']]
    }

    # Make the HTTP POST request to the Discord webhook URL
    response = post_request(config.WEBHOOK_URL, json=payload)

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as err:
        return False
    else:
        return True

def send_email(recipient_email: str, subject: str, body: str) -> bool:
    """Takes the recipient email, the subject and the body of the email and sends it. Returns bool."""
    
    # Email credentials
    sender_email = "forms@infomundi.net"
    sender_password = config.EMAIL_PASSWORD

    # Server information
    smtp_server = config.SMTP_SERVER
    smtp_port = config.SMTP_PORT

    # Create a message
    message = MIMEMultipart()
    message['From'] = sender_email
    message['To'] = recipient_email
    message['Subject'] = subject
    message.attach(MIMEText(body, 'plain'))

    # Establish a connection to the server
    with SMTP_SSL(smtp_server, smtp_port) as server:
        # Log in to the email account
        server.login(sender_email, sender_password)

        # Send the email
        server.sendmail(sender_email, recipient_email, message.as_string())

    return True