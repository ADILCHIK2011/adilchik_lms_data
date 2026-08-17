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
from contextlib import AsyncExitStack, asynccontextmanager

import httpx
from fastapi import FastAPI, Header, HTTPException, Request

from . import ai_agent
from .config import settings
from .mcp_server import mcp_app as _mcp_app, mount_path as _mcp_mount_path
from .orchestrator import run_pipeline
from .queries import (
    attendance_summary,
    bottom_coin_holders,
    bottom_performance,
    load_quick_analysis,
    top_coin_holders,
    top_performance,
)
from .report_text import build_summary_text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("agent_system.bot_server")

@asynccontextmanager
async def _lifespan(_: FastAPI):
    async with AsyncExitStack() as stack:
        # Starts the MCP session manager's task group (see mcp_server.py) —
        # without this, every /mcp request 500s with "Task group is not
        # initialized", since FastAPI never forwards ASGI lifespan events to
        # mounted sub-apps on its own.
        await stack.enter_async_context(_mcp_app.router.lifespan_context(_mcp_app))
        await _register_webhook()
        yield


app = FastAPI(title="LMS Agent Bot", lifespan=_lifespan)
app.mount(_mcp_mount_path(), _mcp_app)

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


# Free-text question -> quick answer, without running Agent 3 (no cloud sync,
# no 294 Telegram sends) so these reply in a couple of seconds instead of
# 1-2 minutes. Order matters: more specific keyword groups are checked first
# so e.g. "coin"+"past" doesn't fall through to the generic performance match.
_COIN_KEYWORDS = ("coin", "tanga")
_LESS_KEYWORDS = ("eng kam", "eng oz", "kam ", "past", "kamroq")
_MORE_KEYWORDS = ("eng ko'p", "eng kop", "ko'p", "kop", "eng yuqori", "yuqori")
_ATTENDANCE_KEYWORDS = ("davomat", "kelmagan", "qoldirgan", "kelmayap", "kelmadi")
_PERF_BAD_KEYWORDS = ("yomon", "zaif", "orqada", "yordam kerak", "past")
_PERF_GOOD_KEYWORDS = ("yaxshi", "reyting", "top", "zo'r", "zor", "eng baland", "eng kuchli")


def _detect_intent(text: str) -> str | None:
    t = text.lower()
    if any(k in t for k in _COIN_KEYWORDS):
        return "coin_bottom" if any(k in t for k in _LESS_KEYWORDS) else "coin_top"
    if any(k in t for k in _ATTENDANCE_KEYWORDS):
        return "attendance"
    if any(k in t for k in _PERF_BAD_KEYWORDS):
        return "perf_bottom"
    if any(k in t for k in _PERF_GOOD_KEYWORDS):
        return "perf_top"
    return None


async def _quick_reply(chat_id: int | str, intent: str) -> None:
    try:
        bundle, attendance_out, performance_out = await asyncio.to_thread(
            load_quick_analysis, settings.data_source
        )
        text = {
            "coin_top": lambda: top_coin_holders(bundle),
            "coin_bottom": lambda: bottom_coin_holders(bundle),
            "attendance": lambda: attendance_summary(attendance_out),
            "perf_top": lambda: top_performance(performance_out),
            "perf_bottom": lambda: bottom_performance(performance_out),
        }[intent]()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Tezkor savolga javob berishda xato")
        text = f"Xatolik yuz berdi: {exc}"
    send_message(chat_id, text)


async def _handle_free_text(chat_id: int | str, text: str) -> None:
    """AI (Claude + MCP tools) if a key is configured, else the keyword
    router above. Either path always replies — never leaves the user hanging.
    """
    if settings.anthropic_api_key:
        try:
            ai_text = await ai_agent.answer(text)
        except Exception:  # noqa: BLE001 - AI failure must fall back, not crash
            logger.exception("AI agent xato berdi, kalit so'z router'iga o'tilmoqda")
            ai_text = None
        if ai_text:
            send_message(chat_id, ai_text)
            return

    intent = _detect_intent(text)
    if intent:
        await _quick_reply(chat_id, intent)
    else:
        send_message(
            chat_id,
            "Tushunmadim. /analyze — to'liq tahlil.\n"
            "Yoki savol bering, masalan: 'eng ko'p coin bor o'quvchi', "
            "'eng yaxshi o'quvchilar', 'Alisher haqida ma'lumot ber'.",
        )


@app.get("/health")
def health() -> dict:
    return {"ok": True}


async def _register_webhook() -> None:
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
    if not text:
        return {"ok": True}

    if not _is_allowed(chat_id):
        send_message(chat_id, "Kechirasiz, sizga bu botdan foydalanishga ruxsat berilmagan.")
        return {"ok": True}

    command = text.lower().split()[0]
    if command in ("/analyze", "/tahlil"):
        asyncio.create_task(_run_analysis_and_reply(chat_id))
    elif command == "/start":
        ai_note = (
            "\nIstalgan savolni yozing (masalan: 'eng ko'p coin bor o'quvchi kim?') — "
            "sun'iy intellekt ma'lumotlar asosida javob beradi."
            if settings.anthropic_api_key
            else ""
        )
        send_message(
            chat_id,
            "Salom! Men LMS ma'lumotlarini tahlil qiluvchi botman.\n"
            "/analyze — to'liq tahlil (davomat, o'zlashtirish, reyting) ishga tushirish."
            + ai_note,
        )
    else:
        asyncio.create_task(_handle_free_text(chat_id, text))

    return {"ok": True}
