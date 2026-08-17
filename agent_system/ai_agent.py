"""Claude <-> MCP bridge: this is what lets the Telegram bot answer an
arbitrary prompt instead of only fixed commands/keywords.

Flow per message:
  1. connect to our own MCP tool server (`mcp_server.py`) over Streamable
     HTTP at the loopback address — same process, different ASGI mount, so
     this is a real MCP client/server handshake, not a shortcut
  2. list its tools, translate them to Anthropic's tool schema
  3. run the standard agentic tool-use loop: send the user's message with
     the tool list, execute whatever tools Claude asks for via the MCP
     session, feed results back, repeat until Claude returns plain text
  4. that text is the Telegram reply

If `ANTHROPIC_API_KEY` is not set, `answer()` returns `None` and
`bot_server.py` falls back to the keyword-based router in `queries.py` —
the bot works either way, just less flexibly without a key.
"""
from __future__ import annotations

import logging
import os

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from .config import settings

logger = logging.getLogger("agent_system.ai_agent")

MAX_TOOL_ROUNDS = 6
SYSTEM_PROMPT = (
    "Siz O'zbekistondagi IT-akademiya LMS tizimi uchun yordamchi botsiz. "
    "Foydalanuvchi savoliga javob berish uchun sizga berilgan vositalardan "
    "(tools) foydalaning — hech qachon raqamlarni o'zingizdan o'ylab topmang, "
    "faqat vositalar qaytargan ma'lumotga tayaning. Javobni o'zbek tilida, "
    "qisqa va aniq yozing. Agar vosita natijasida kerakli ma'lumot topilmasa, "
    "buni ochiq tan oling."
)


def _internal_mcp_url() -> str:
    port = os.getenv("PORT", "8000")
    return f"http://127.0.0.1:{port}/mcp"


def _mcp_tool_to_anthropic(tool) -> dict:
    return {
        "name": tool.name,
        "description": tool.description or "",
        "input_schema": tool.inputSchema,
    }


async def answer(user_text: str) -> str | None:
    if not settings.anthropic_api_key:
        return None

    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    async with streamable_http_client(_internal_mcp_url()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            tool_schemas = [_mcp_tool_to_anthropic(t) for t in tools_result.tools]

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
                    try:
                        result = await session.call_tool(tool_use.name, tool_use.input)
                        text = "\n".join(
                            b.text for b in result.content if hasattr(b, "text")
                        )
                        is_error = result.isError
                    except Exception as exc:  # noqa: BLE001
                        logger.exception("MCP tool chaqiruvi xato berdi: %s", tool_use.name)
                        text = f"Vosita xatosi: {exc}"
                        is_error = True

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
