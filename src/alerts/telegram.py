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
    label = alert.score_label or "Alerta de preço"
    vs_mean = f"-{abs(alert.drop_pct):.0f}% vs média" if alert.drop_pct > 0 else ""
    stats_line = (
        f"📊 Mais barato que {alert.score_pct:.0f}% dos últimos registros\n"
        f"   Média: R$ {alert.hist_mean:,.0f} | Mínima: R$ {alert.hist_min:,.0f} ({alert.hist_count} amostras)"
    )
    return (
        f"✈️ <b>{alert.route_key}</b> | {label}\n"
        f"📅 Partida: {alert.departure_date.strftime('%d/%m/%Y')}\n"
        f"💰 <b>R$ {alert.new_price:,.0f}</b>{f'  {vs_mean}' if vs_mean else ''}\n"
        f"{stats_line}\n"
        f"🔗 <a href=\"{alert.deep_link}\">Buscar passagem</a>\n"
        f"<i>Fonte: {alert.source}</i>"
    )
