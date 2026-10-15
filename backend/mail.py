"""Send a confirmation code when mail is configured."""

import logging
import smtplib
from email.message import EmailMessage

log = logging.getLogger(__name__)


def send_code(settings, address: str, code: str) -> bool:
    """True when the message left this machine. False when mail is not set up."""
    host = (settings.smtp_host or "").strip()
    sender = (settings.smtp_from or settings.smtp_user or "").strip()
    if not host or not sender:
        return False
    message = EmailMessage()
    message["Subject"] = "Your Ira confirmation code"
    message["From"] = sender
    message["To"] = address
    message.set_content(
        f"Your confirmation code is {code}.\n\nIt expires in 15 minutes.\n"
    )
    try:
        with smtplib.SMTP(host, settings.smtp_port, timeout=10) as smtp:
            smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(message)
    except Exception as exc:
        log.warning("Confirmation email failed: %s", exc)
        return False
    return True
