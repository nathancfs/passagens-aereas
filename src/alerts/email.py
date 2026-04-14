"""Email alert sender via SMTP."""

import os
import smtplib
from email.mime.text import MIMEText

from ..models import Alert


def send(alert: Alert) -> None:
    host = os.environ["SMTP_HOST"]
    port = int(os.environ["SMTP_PORT"])
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASSWORD"]
    to = os.environ["ALERT_EMAIL_TO"]

    subject = f"✈️ Nova mínima: {alert.route_key} — R$ {alert.new_price:,.0f}"
    body = _format(alert)

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to

    try:
        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(user, [to], msg.as_string())
        print(f"[email] alert sent for {alert.route_key} {alert.departure_date}")
    except Exception as exc:
        print(f"[email] send error: {exc}")


def _format(alert: Alert) -> str:
    drop_info = f" (-{alert.drop_pct}% vs mínimo anterior)" if alert.drop_pct > 0 else ""
    return (
        f"Nova mínima detectada: {alert.route_key}\n"
        f"Data de partida: {alert.departure_date.strftime('%d/%m/%Y')}\n"
        f"Preço: R$ {alert.new_price:,.0f}{drop_info}\n"
        f"Link: {alert.deep_link}\n"
        f"Fonte: {alert.source}\n"
    )
