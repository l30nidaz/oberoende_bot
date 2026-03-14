import os
import smtplib
from email.mime.text import MIMEText


def notify_owner_lead(
    user_id: str,
    channel: str,
    lead_text: str,
    subject: str | None = None
):
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    owner_email = os.getenv("OWNER_EMAIL")
    from_email = os.getenv("FROM_EMAIL", smtp_user)

    print("SMTP_HOST(main):", os.getenv("SMTP_HOST"))
    print("SMTP_USER(main):", os.getenv("SMTP_USER"))
    print("FROM_EMAIL(main):", os.getenv("FROM_EMAIL"))
    print("OWNER_EMAIL(main):", os.getenv("OWNER_EMAIL"))

    if not all([smtp_host, smtp_user, smtp_pass, owner_email]):
        print("⚠️ Configuración SMTP incompleta, no se puede enviar email de lead")
        return

    email_subject = subject or f"Nuevo lead ({channel})"

    msg = MIMEText(lead_text, "plain", "utf-8")
    msg["Subject"] = email_subject
    msg["From"] = from_email
    msg["To"] = owner_email

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(from_email, [owner_email], msg.as_string())