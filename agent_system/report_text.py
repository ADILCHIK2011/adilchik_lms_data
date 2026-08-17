"""Renders a `PipelineState` into a plain-text summary. Shared by the CLI
(`main.py`, printed to stdout) and the Telegram bot (`bot_server.py`, sent as
a chat message) so the two surfaces never drift out of sync.
"""
from __future__ import annotations

from .models import PipelineState


def build_summary_text(state: PipelineState) -> str:
    if state.aborted:
        return "PIPELINE TO'XTATILDI:\n" + "\n".join(f"- {e}" for e in state.errors)

    bundle = state.bundle
    att = state.attendance_out
    perf = state.performance_out
    integ = state.integration_out

    lines: list[str] = []
    lines.append("Ma'lumot sifati")
    lines.append(f"  O'quvchilar: {len(bundle.students)}")
    if bundle.quality.files_missing:
        lines.append(f"  Yo'q fayllar: {', '.join(bundle.quality.files_missing)}")
    lines.append(f"  Karantindagi qatorlar: {len(bundle.quality.quarantined)}")
    lines.append(f"  Orphan FK: {bundle.quality.orphaned_fk_count}")

    lines.append("")
    lines.append("Agent 1: Davomat")
    lines.append(f"  Kam kelganlar (bayroq): {len(att.flagged)}")
    lines.append(f"  Muammosiz o'quvchilar: {att.ok_count}")
    lines.append(f"  Curator ogohlantirishlari: {len(att.curator_alerts)}")
    for f in att.flagged[:5]:
        lines.append(
            f"    - {f.student_name} [{f.period}]: {f.present_count}/{f.lessons_in_window} "
            f"kelgan (kerak >= {f.required_min}) - {f.likely_reason.value}"
        )

    lines.append("")
    lines.append("Agent 2: O'zlashtirish va reyting")
    lines.append("  Top 5:")
    for e in perf.leaderboard[:5]:
        lines.append(f"    {e.rank}. {e.student_name} - {e.performance_score} ball")
    lines.append("  Bottom 5:")
    for e in perf.bottom_list[:5]:
        lines.append(f"    {e.rank}. {e.student_name} - {e.performance_score} ball")

    lines.append("")
    lines.append("Agent 3: Integratsiya")
    if integ.sync:
        lines.append(
            f"  Cloud sync: {integ.sync.target} ok={integ.sync.ok} rows={integ.sync.rows_written}"
        )
    ok_notif = sum(1 for n in integ.notifications if n.ok)
    lines.append(f"  Xabarnomalar: {ok_notif}/{len(integ.notifications)} muvaffaqiyatli")
    lines.append(f"  MCP: published={integ.mcp_published}")

    text = "\n".join(lines)
    return text[:4000]  # Telegram sendMessage hard limit is 4096 chars
