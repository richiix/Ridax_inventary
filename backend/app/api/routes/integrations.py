from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.config import get_settings
from app.db.session import get_db
from app.models.product import Product
from app.models.sale import Sale
from app.models.user import User
from app.services.bot import send_telegram_message, send_whatsapp_message


router = APIRouter()
settings = get_settings()


def resolve_command(db: Session, text: str, chat_id: str) -> str:
    command = text.strip().lower()
    if command in {"/start", "/ayuda", "/help"}:
        return (
            "Bienvenido a RIDAXBot.\n"
            f"Tu chat_id es: {chat_id}\n"
            "Comparte este chat_id con Admin para activar recuperacion de contrasena por Telegram.\n"
            "Comandos: /stock <SKU>, /ventas_hoy"
        )

    if command.startswith("/stock"):
        parts = command.split(" ", 1)
        if len(parts) < 2:
            return "Uso: /stock <SKU>"
        sku = parts[1].upper()
        product = db.scalar(select(Product).where(Product.sku == sku))
        if not product:
            return f"No existe el SKU {sku}."
        return f"Stock actual {product.sku}: {product.stock}"

    if command == "/ventas_hoy":
        now = datetime.now(timezone.utc)
        start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        total = db.scalar(
            select(func.coalesce(func.sum(Sale.total_usd), 0))
            .where(Sale.created_at >= start)
            .where(Sale.is_voided.is_not(True))
        )
        return f"Ventas de hoy (USD): {round(float(total or 0), 2)}"

    return "Comandos: /stock <SKU>, /ventas_hoy"


@router.get("/whatsapp/verify")
def verify_whatsapp(
    mode: str = Query(default="", alias="hub.mode"),
    token: str = Query(default="", alias="hub.verify_token"),
    challenge: str = Query(default="", alias="hub.challenge"),
) -> str:
    if mode == "subscribe" and token == settings.whatsapp_verify_token:
        return challenge
    raise HTTPException(status_code=403, detail="Token de verificacion invalido")


@router.post("/telegram/webhook")
async def telegram_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    payload = await request.json()
    message = payload.get("message", {})
    text = message.get("text", "")
    chat_id = str(message.get("chat", {}).get("id", settings.telegram_default_chat_id))
    response_text = resolve_command(db, text, chat_id)
    result = await send_telegram_message(chat_id, response_text)
    return {"status": "ok", "response_text": response_text, "provider_result": result}


@router.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    payload = await request.json()
    entries = payload.get("entry", [])
    text = ""
    sender = ""
    if entries:
        changes = entries[0].get("changes", [])
        if changes:
            value = changes[0].get("value", {})
            messages = value.get("messages", [])
            if messages:
                sender = messages[0].get("from", "")
                text = messages[0].get("text", {}).get("body", "")

    response_text = resolve_command(db, text, sender)
    provider_result = await send_whatsapp_message(sender, response_text)
    return {"status": "ok", "response_text": response_text, "provider_result": provider_result}


@router.post("/send-test")
async def send_test_message(
    channel: str,
    destination: str,
    text: str,
    _: User = Depends(require_permission("integrations:use")),
) -> dict:
    if channel == "telegram":
        result = await send_telegram_message(destination, text)
        return {"channel": channel, "result": result}
    if channel == "whatsapp":
        result = await send_whatsapp_message(destination, text)
        return {"channel": channel, "result": result}
    raise HTTPException(status_code=400, detail="Canal invalido")
