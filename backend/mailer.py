"""Email delivery for account notifications."""
import os
import smtplib
from email.message import EmailMessage


def send_account_credentials(to_email: str, recipient_name: str, password: str) -> None:
    """Send a newly generated password through the configured SMTP account."""
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    mail_from = os.getenv("MAIL_FROM", smtp_username or "")

    if not smtp_username or not smtp_password or not mail_from:
        raise RuntimeError("SMTP_USERNAME, SMTP_PASSWORD, and MAIL_FROM must be configured")

    message = EmailMessage()
    message["Subject"] = "Your LearnSync account"
    message["From"] = mail_from
    message["To"] = to_email
    message.set_content(
        f"""Hello {recipient_name},

Your LearnSync account is ready.

Email: {to_email}
Temporary password: {password}

Please sign in and change this password immediately.
"""
    )

    with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as smtp:
        smtp.starttls()
        smtp.login(smtp_username, smtp_password)
        smtp.send_message(message)