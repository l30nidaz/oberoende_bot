import os
import smtplib
from email.mime.text import MIMEText


def notify_owner_lead(user_id: str, channel: str, lead_text: str):
    
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
    print("SMTP_PASS(main):", os.getenv("SMTP_PASS"))
    
    if not all([smtp_host, smtp_user, smtp_pass, owner_email]):
        # En producción: loggear esto
        print("⚠️ Configuración SMTP incompleta, no se puede enviar email de lead")
        return

    subject = f"Nuevo lead ({channel}) - Oberoende"
    body = (
        f"NUEVO LEAD 💎\n\n"
        f"Canal: {channel}\n"
        f"Cliente (user_id): {user_id}\n\n"
        f"Mensaje / datos:\n{lead_text}\n"
    )

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = owner_email

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(from_email, [owner_email], msg.as_string())