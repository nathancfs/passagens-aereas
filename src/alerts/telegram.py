"""Telegram alert sender."""

import os
import httpx

from ..models import Alert

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def send(alert: Alert) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    # Use subscription-specific chat_id if available, fall back to env default
    chat_id = alert.chat_id or os.environ["TELEGRAM_CHAT_ID"]

    text = _format(alert)

    try:
        resp = httpx.post(
            TELEGRAM_API.format(token=token),
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        resp.raise_for_status()
        print(f"[telegram] alert sent for {alert.route_key} {alert.departure_date} → chat {chat_id}")
    except Exception as exc:
        print(f"[telegram] send error: {exc}")


def _format(alert: Alert) -> str:
    drop_info = f" (-{alert.drop_pct}% vs mínimo anterior)" if alert.drop_pct > 0 else ""
    return (
        f"✈️ <b>Nova mínima: {alert.route_key}</b>\n"
        f"📅 Partida: {alert.departure_date.strftime('%d/%m/%Y')}\n"
        f"💰 Preço: R$ {alert.new_price:,.0f}{drop_info}\n"
        f"🔗 <a href=\"{alert.deep_link}\">Ver passagem</a>\n"
        f"<i>Fonte: {alert.source}</i>"
    )
