import gnupg
from email.mime.multipart import MIMEMultipart
from requests import post as post_request
from email.mime.text import MIMEText
from email.utils import formatdate
from sqlalchemy import insert
from smtplib import SMTP

from . import config, extensions, models


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
        response = post_request(config.WEBHOOK_URL, timeout=3, json=data)
        response.raise_for_status()
    except Exception:
        return False

    return True


def notify(notif_dicts: list):
    """Creates a Notification for specified users in the data

    Types allowed: ("default", "new_comment", "comment_reply", "friend_request", "friend_accepted")

    Args:
        notif_dicts: list
            List of dicts containing info regarding the notifications to be added to the database. e.g.
            [
                {"user_id": user_id, "type": type, "message": message, "url": url}, { ... }
            ]
    """

    extensions.db.session.execute(insert(models.Notification), notif_dicts)
    extensions.db.session.commit()


def send_email(
    recipient_email: str,
    subject: str,
    body: str,
    reply_to: str = "noreply@infomundi.net",
    from_email: str = "Infomundi <noreply@infomundi.net>",
) -> bool:
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
    message["From"] = from_email
    message["To"] = recipient_email
    message["Subject"] = subject
    message["Date"] = formatdate(localtime=True)

    if reply_to != from_email:
        message["Reply-To"] = reply_to

    message.attach(MIMEText(body, "plain"))

    try:
        with SMTP(config.SMTP_SERVER, config.SMTP_PORT) as server:
            server.starttls()  # Upgrade the connection to secure TLS
            server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)

            # Send the email
            server.sendmail(config.SMTP_USERNAME, recipient_email, message.as_string())
    except Exception:
        return False

    return True


def send_signed_email(
    recipient_email: str,
    subject: str,
    body: str,
    pgp_key_id: str = "contact@infomundi.net",
    pgp_passphrase: str = "",
    reply_to: str = "noreply@infomundi.net",
    from_email: str = "Infomundi <noreply@infomundi.net>",
) -> bool:
    """Sends a PGP/MIME signed email."""

    # 1) Build the unsigned body part
    unsigned = MIMEMultipart(_subtype="mixed")
    unsigned["From"] = from_email
    unsigned["To"] = recipient_email
    unsigned["Subject"] = subject
    unsigned["Date"] = formatdate(localtime=True)
    if reply_to != from_email:
        unsigned["Reply-To"] = reply_to
    unsigned.attach(MIMEText(body, "plain"))

    # 2) Serialize the body to sign
    #    Use bytes for GPG to sign in canonical form
    body_bytes = unsigned.get_payload()[0].as_bytes()

    # 3) Sign with python-gnupg (detached signature)
    gpg = gnupg.GPG()  # assumes secret key is in keyring
    sig = gpg.sign(
        body_bytes,
        keyid=pgp_key_id,
        passphrase=pgp_passphrase,
        detach=True,
        always_trust=True,
    )
    if not sig:
        return False

    # 4) Build the PGP/MIME signed container
    signed = MIMEMultipart(
        _subtype="signed", protocol="application/pgp-signature", micalg="pgp-sha256"
    )
    # copy headers
    for h in ("From", "To", "Subject", "Date", "Reply-To"):
        if unsigned[h]:
            signed[h] = unsigned[h]

    # attach the original text part
    signed.attach(MIMEText(body, "plain"))

    # prepare signature part
    sig_part = MIMEBase("application", "pgp-signature", name="signature.asc")
    sig_part.set_payload(str(sig))  # signature ASCII-armored
    encoders.encode_base64(sig_part)
    sig_part.add_header("Content-Disposition", 'attachment; filename="signature.asc"')
    signed.attach(sig_part)

    # 5) Send it off
    try:
        with SMTP(config.SMTP_SERVER, config.SMTP_PORT) as server:
            server.starttls()
            server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
            server.sendmail(
                config.SMTP_USERNAME,
                recipient_email,
                signed.as_string(),
            )
    except Exception as e:
        return False

    return True
