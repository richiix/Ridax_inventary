from __future__ import annotations

import httpx

from app.core.config import get_settings


async def send_telegram_message(chat_id: str, text: str) -> dict:
    settings = get_settings()
    if not settings.telegram_bot_token:
        return {"status": "simulated", "channel": "telegram", "message": text}

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(url, json={"chat_id": chat_id, "text": text})
        response.raise_for_status()
        return response.json()


async def send_whatsapp_message(phone_number: str, text: str) -> dict:
    settings = get_settings()
    if not settings.whatsapp_access_token or not settings.whatsapp_phone_number_id:
        return {"status": "simulated", "channel": "whatsapp", "message": text}

    url = f"https://graph.facebook.com/v21.0/{settings.whatsapp_phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "text",
        "text": {"body": text},
    }
    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}"}

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
