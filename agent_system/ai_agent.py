"""Claude/Groq <-> MCP bridge: this is what lets the Telegram bot answer an
arbitrary prompt instead of only fixed commands/keywords.

Flow per message:
  1. connect to our own MCP tool server (`mcp_server.py`) over Streamable
     HTTP at the loopback address — same process, different ASGI mount, so
     this is a real MCP client/server handshake, not a shortcut
  2. list its tools, translate them to the active provider's tool schema
  3. run the standard agentic tool-use loop: send the user's message with
     the tool list, execute whatever tools the model asks for via the MCP
     session, feed results back, repeat until the model returns plain text
  4. that text is the Telegram reply

Two providers, picked at call time — no code path needs a paid key to work:
  - Groq (`GROQ_API_KEY`): free tier, no credit card, OpenAI-compatible
    `/chat/completions` API with function calling. This is the default
    recommendation precisely because it's free.
  - Anthropic (`ANTHROPIC_API_KEY`): used if set (and Groq isn't).

If neither key is set, `answer()` returns `None` and `bot_server.py` falls
back to the keyword-based router in `queries.py` — the bot works either way,
just less flexibly without a key.
"""
from __future__ import annotations

import logging
import os

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from .config import settings

logger = logging.getLogger("agent_system.ai_agent")

MAX_TOOL_ROUNDS = 6
SYSTEM_PROMPT = (
    "Siz O'zbekistondagi IT-akademiya LMS tizimi uchun yordamchi botsiz. "
    "Foydalanuvchi savoliga javob berish uchun sizga berilgan vositalardan "
    "(tools/functions) foydalaning — hech qachon raqamlarni o'zingizdan "
    "o'ylab topmang, faqat vositalar qaytargan ma'lumotga tayaning. Javobni "
    "o'zbek tilida, qisqa va aniq yozing. Agar vosita natijasida kerakli "
    "ma'lumot topilmasa, buni ochiq tan oling."
)


def _internal_mcp_url() -> str:
    port = os.getenv("PORT", "8000")
    return f"http://127.0.0.1:{port}/mcp"


async def answer(user_text: str) -> str | None:
    if not (settings.groq_api_key or settings.anthropic_api_key):
        return None

    async with streamable_http_client(_internal_mcp_url()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_result = await session.list_tools()

            if settings.groq_api_key:
                return await _run_groq(session, tools_result.tools, user_text)
            return await _run_anthropic(session, tools_result.tools, user_text)


async def _call_mcp_tool(session: ClientSession, name: str, arguments: dict) -> tuple[str, bool]:
    try:
        result = await session.call_tool(name, arguments)
        text = "\n".join(b.text for b in result.content if hasattr(b, "text"))
        return text, result.isError
    except Exception as exc:  # noqa: BLE001
        logger.exception("MCP tool chaqiruvi xato berdi: %s", name)
        return f"Vosita xatosi: {exc}", True


# ------------------------------------------------------------- Anthropic

def _mcp_tool_to_anthropic(tool) -> dict:
    return {"name": tool.name, "description": tool.description or "", "input_schema": tool.input_schema}


async def _run_anthropic(session: ClientSession, tools, user_text: str) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    tool_schemas = [_mcp_tool_to_anthropic(t) for t in tools]
    messages: list[dict] = [{"role": "user", "content": user_text}]

    for _ in range(MAX_TOOL_ROUNDS):
        response = client.messages.create(
            model=settings.llm_model,
            max_tokens=800,
            system=SYSTEM_PROMPT,
            tools=tool_schemas,
            messages=messages,
        )
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if not tool_uses:
            text_blocks = [b.text for b in response.content if b.type == "text"]
            return "\n".join(text_blocks).strip() or "Javob topilmadi."

        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for tool_use in tool_uses:
            text, is_error = await _call_mcp_tool(session, tool_use.name, tool_use.input)
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": text,
                    "is_error": is_error,
                }
            )
        messages.append({"role": "user", "content": tool_results})

    return "Kechirasiz, savolga javob topa olmadim (juda ko'p qadam kerak bo'ldi)."


# ------------------------------------------------------------------ Groq
# OpenAI-compatible /chat/completions with function calling — no SDK needed,
# just httpx against Groq's endpoint.

_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def _mcp_tool_to_openai(tool) -> dict:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.input_schema,
        },
    }


async def _run_groq(session: ClientSession, tools, user_text: str) -> str:
    tool_schemas = [_mcp_tool_to_openai(t) for t in tools]
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_text},
    ]
    headers = {"Authorization": f"Bearer {settings.groq_api_key}"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        for _ in range(MAX_TOOL_ROUNDS):
            resp = await client.post(
                _GROQ_URL,
                headers=headers,
                json={
                    "model": settings.groq_model,
                    "messages": messages,
                    "tools": tool_schemas,
                    "tool_choice": "auto",
                },
            )
            if resp.status_code != 200:
                logger.error("Groq API xato: HTTP %s %s", resp.status_code, resp.text[:300])
                return f"Groq API xatosi (HTTP {resp.status_code}). Kalitni tekshiring."

            message = resp.json()["choices"][0]["message"]
            tool_calls = message.get("tool_calls") or []
            if not tool_calls:
                return (message.get("content") or "").strip() or "Javob topilmadi."

            messages.append(message)
            for call in tool_calls:
                import json as _json

                try:
                    args = _json.loads(call["function"]["arguments"] or "{}")
                except _json.JSONDecodeError:
                    args = {}
                text, _is_error = await _call_mcp_tool(session, call["function"]["name"], args)
                messages.append(
                    {"role": "tool", "tool_call_id": call["id"], "content": text}
                )

    return "Kechirasiz, savolga javob topa olmadim (juda ko'p qadam kerak bo'ldi)."
