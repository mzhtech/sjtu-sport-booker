import smtplib
from email.message import EmailMessage


def send_smtp_message(config, subject, body):
    if not config.get("enabled"):
        return {"sent": False, "reason": "disabled"}

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config["sender"]
    message["To"] = config["receiver"]
    message.set_content(body)

    smtp_class = smtplib.SMTP_SSL if config.get("use_ssl", True) else smtplib.SMTP
    with smtp_class(config["smtp_host"], config["smtp_port"], timeout=10) as server:
        if not config.get("use_ssl", True):
            server.starttls()
        server.login(config["sender"], config["password"])
        server.send_message(message)

    return {"sent": True}
