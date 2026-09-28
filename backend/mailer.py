"""Email delivery for account notifications."""
import os
import smtplib
from email.message import EmailMessage


def send_account_credentials(to_email: str, recipient_name: str, password: str) -> None:
    """Send a newly generated password through the configured SMTP account."""
    smtp_host = os.getenv("SMTP_HOST", "localhost")
    smtp_port = int(os.getenv("SMTP_PORT", "1025"))
    smtp_username = (os.getenv("SMTP_USERNAME") or "").strip()
    smtp_password = (os.getenv("SMTP_PASSWORD") or "").replace(" ", "").replace("\t", "").strip()
    mail_from = (os.getenv("MAIL_FROM", smtp_username or "") or "").strip()

    mail_from = mail_from or "learnsync@local.test"
    use_tls = os.getenv("SMTP_STARTTLS", "false").lower() in {"1", "true", "yes"}
    if bool(smtp_username) != bool(smtp_password):
        raise RuntimeError("SMTP_USERNAME and SMTP_PASSWORD must be configured together")

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
        if use_tls:
            smtp.starttls()
        if smtp_username:
            smtp.login(smtp_username, smtp_password)
        smtp.send_message(message)
