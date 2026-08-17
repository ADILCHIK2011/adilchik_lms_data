"""Always-on Telegram bot, deployed as a Render web service (see `render.yaml`).

Long-polling was deliberately avoided: Render's free tier spins the instance
down after ~15 minutes of no HTTP traffic, which would silently kill a
polling loop. A webhook is the opposite shape — Telegram POSTs to us only
when there's a message, which is exactly the request that wakes a sleeping
free instance back up. The trade-off is a cold-start delay (worst case
~30-50s) on the first message after a long idle period; every message after
that is fast until it goes back to sleep.

Flow: Telegram -> POST /telegram/webhook -> ack the chat immediately ->
run the full pipeline in a worker thread (it's sync/blocking: network calls,
subprocess, sqlite) -> send the result as a second message. Decoupling the
webhook response from pipeline runtime avoids Telegram's own webhook
timeout/retry behavior kicking in on a slow run.
"""
from __future__ import annotations

import asyncio
import logging

import httpx
from fastapi import FastAPI, Header, HTTPException, Request

from .config import settings
from .orchestrator import run_pipeline
from .report_text import build_summary_text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("agent_system.bot_server")

app = FastAPI(title="LMS Agent Bot")

_TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


def _api_url(method: str) -> str:
    return _TELEGRAM_API.format(token=settings.telegram_bot_token, method=method)


def send_message(chat_id: int | str, text: str) -> None:
    if not settings.telegram_bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN yo'q — xabar yuborilmadi: %s", text[:80])
        return
    try:
        with httpx.Client(timeout=10.0) as client:
            client.post(_api_url("sendMessage"), json={"chat_id": chat_id, "text": text})
    except httpx.HTTPError as exc:
        logger.error("Telegram sendMessage xato: %s", exc)


def _is_allowed(chat_id: int | str) -> bool:
    if not settings.telegram_allowed_chat_ids:
        return True  # no allowlist configured -> open to anyone who finds the bot
    return str(chat_id) in settings.telegram_allowed_chat_ids


async def _run_analysis_and_reply(chat_id: int | str) -> None:
    send_message(chat_id, "Tahlil boshlandi, biroz kuting (odatda 1-2 daqiqa)...")
    try:
        state = await asyncio.to_thread(run_pipeline, settings.data_source)
        text = build_summary_text(state)
    except Exception as exc:  # noqa: BLE001 - a bot reply must never crash silently
        logger.exception("Pipeline xato berdi")
        text = f"Xatolik yuz berdi: {exc}"
    send_message(chat_id, text)


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.on_event("startup")
async def register_webhook() -> None:
    if not (settings.public_base_url and settings.telegram_bot_token):
        logger.info("public_base_url yoki bot token yo'q — webhook avtomatik ro'yxatdan o'tkazilmadi")
        return
    webhook_url = f"{settings.public_base_url.rstrip('/')}/telegram/webhook"
    payload: dict = {"url": webhook_url}
    if settings.telegram_webhook_secret:
        payload["secret_token"] = settings.telegram_webhook_secret
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(_api_url("setWebhook"), json=payload)
        logger.info("setWebhook -> %s: %s", webhook_url, resp.json())
    except httpx.HTTPError as exc:
        logger.error("setWebhook muvaffaqiyatsiz: %s", exc)


@app.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict:
    if settings.telegram_webhook_secret and x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
        raise HTTPException(status_code=403, detail="forbidden")

    update = await request.json()
    message = update.get("message") or update.get("edited_message")
    if not message or "text" not in message:
        return {"ok": True}

    chat_id = message["chat"]["id"]
    text = message["text"].strip()

    if not _is_allowed(chat_id):
        send_message(chat_id, "Kechirasiz, sizga bu botdan foydalanishga ruxsat berilmagan.")
        return {"ok": True}

    command = text.lower().split()[0]
    if command in ("/analyze", "/tahlil"):
        asyncio.create_task(_run_analysis_and_reply(chat_id))
    elif command == "/start":
        send_message(
            chat_id,
            "Salom! Men LMS ma'lumotlarini tahlil qiluvchi botman.\n"
            "/analyze — davomat, o'zlashtirish va reyting tahlilini ishga tushirish.",
        )
    else:
        send_message(chat_id, "Noma'lum buyruq. /analyze ni yuboring.")

    return {"ok": True}
