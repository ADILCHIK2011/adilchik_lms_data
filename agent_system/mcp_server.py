"""The MCP tool server: exposes the LMS query layer (`queries.py`) as proper
MCP tools over Streamable HTTP, mounted at `/mcp` on the same FastAPI app
(`bot_server.py`) that serves the Telegram webhook — one Render service,
two jobs.

Two consequences of this being a real MCP server, not just a function table:
  1. It's connectable by *any* MCP client, not only our own bot — Claude
     Desktop, claude.ai connectors, or another agent can point at
     `https://<your-app>.onrender.com/mcp` and get the same tools.
  2. Every tool here is read-only / side-effect-free on purpose. Agent 3's
     side effects — real Telegram sends to parents, writing to the cloud DB —
     stay behind the explicit `/analyze` command in `bot_server.py`, not
     something a language model can trigger off an ambiguous prompt.

`stateless_http=True` because Render's free tier can restart/redeploy the
single instance at any time, and there is no reason a read-only tool call
needs session affinity.
"""
from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from .config import settings
from . import queries

mcp = MCPServer(
    name="lms-agent-tools",
    title="LMS Ma'lumotlar Tahlil Vositalari",
    instructions=(
        "Bu vositalar O'zbekistondagi bitta IT-akademiya LMS'idagi 294 ta o'quvchi "
        "haqidagi haqiqiy ma'lumotlarga (davomat, uy vazifasi, coin, reyting) "
        "kirish imkonini beradi. Har doim shu vositalardan foydalanib javob ber, "
        "raqamlarni o'zingdan o'ylab topma."
    ),
)


def _bundle():
    return queries.get_cached_quick_analysis(settings.data_source)


@mcp.tool(description="Eng ko'p coin (tanga) to'plagan o'quvchilar ro'yxati")
def top_coin_students(n: int = 5) -> str:
    bundle, _, _ = _bundle()
    return queries.top_coin_holders(bundle, n)


@mcp.tool(description="Eng kam coin (tanga) to'plagan o'quvchilar ro'yxati")
def bottom_coin_students(n: int = 5) -> str:
    bundle, _, _ = _bundle()
    return queries.bottom_coin_holders(bundle, n)


@mcp.tool(description="Umumiy o'zlashtirish (performance_score) bo'yicha eng yaxshi o'quvchilar")
def top_performing_students(n: int = 5) -> str:
    _, _, performance_out = _bundle()
    return queries.top_performance(performance_out, n)


@mcp.tool(description="Umumiy o'zlashtirish (performance_score) bo'yicha eng past o'quvchilar — yordam kerak bo'lganlar")
def bottom_performing_students(n: int = 5) -> str:
    _, _, performance_out = _bundle()
    return queries.bottom_performance(performance_out, n)


@mcp.tool(description="Davomat holati: kam kelganlar soni, curator ogohlantirishlari, eng ko'p qoldirganlar")
def attendance_overview() -> str:
    _, attendance_out, _ = _bundle()
    return queries.attendance_summary(attendance_out)


@mcp.tool(description="Bitta o'quvchi haqida to'liq ma'lumot: reyting, davomat, ball, coin, shaxsiy tavsiya. Ism (to'liq yoki qisman) bilan qidiradi.")
def student_info(name: str) -> str:
    bundle, attendance_out, performance_out = _bundle()
    return queries.student_report(bundle, attendance_out, performance_out, name)


@mcp.tool(description="Bitta guruh haqida statistika: o'quvchilar soni, o'rtacha ball, o'rtacha davomat, eng qiyin mavzular. Guruh nomi (masalan 'FE-RCT-006') bilan qidiradi.")
def group_info(group_name: str) -> str:
    bundle, _, performance_out = _bundle()
    return queries.group_report(bundle, performance_out, group_name)


@mcp.tool(description="Datasetdagi umumiy sonlar: nechta o'quvchi, guruh, kam kelganlar soni va h.k. — ma'lumot sifati bilan birga")
def dataset_overview() -> str:
    bundle, attendance_out, performance_out = _bundle()
    return (
        f"O'quvchilar: {len(bundle.students)}\n"
        f"Guruhlar: {len(bundle.groups)}\n"
        f"Kam kelgan (bayroqlangan) davrlar: {len(attendance_out.flagged)}\n"
        f"Curator ogohlantirishlari: {len(attendance_out.curator_alerts)}\n"
        f"Yo'q fayllar: {bundle.quality.files_missing or 'yoʻq'}\n"
        f"Karantindagi qatorlar: {len(bundle.quality.quarantined)}"
    )


def mount_path() -> str:
    return "/mcp"


# Built once at import time so `bot_server.py` can both mount it (routes) and
# enter its `.router.lifespan_context` (starts the session manager's task
# group) — FastAPI does not forward the ASGI lifespan protocol to mounted
# sub-apps automatically, so the caller must do that merge explicitly.
mcp_app = mcp.streamable_http_app(streamable_http_path="/", stateless_http=True)
