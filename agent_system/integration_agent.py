"""Agent 3 — Tashqi muhit bilan bog'lanish agenti.

Runs after Agent 1 + Agent 2 (or on the hourly scheduler, see `main.py`):
  1. drains anything queued in the local fallback store from a previous
     failed cloud sync (`storage.flush_fallback_queue`)
  2. pushes this run's summary to the cloud DB, falling back to the local
     queue on failure (`storage.sync_to_cloud`)
  3. sends a Telegram alert to each parent for every curator alert Agent 1
     raised (2+ consecutive misses) — DryRunSink if no bot token configured
  4. publishes the same summary to an MCP server if one is configured
  5. best-effort tags the report with the data repo's git commit, purely
     informational and never fatal if this isn't a git checkout
"""
from __future__ import annotations

import logging

from .cli_exec import CLIExecutionError, run_cli
from .config import settings
from .mcp_client import get_mcp_client
from .models import (
    AttendanceAgentOutput,
    DataBundle,
    IntegrationAgentOutput,
    NotificationResult,
    PerformanceAgentOutput,
)
from .notify import get_notification_sink
from .storage import flush_fallback_queue, sync_to_cloud

logger = logging.getLogger("agent_system.integration")


def _build_summary_payload(
    bundle: DataBundle,
    attendance_out: AttendanceAgentOutput,
    performance_out: PerformanceAgentOutput,
) -> dict:
    return {
        "student_count": len(bundle.students),
        "data_quality": {
            "files_missing": bundle.quality.files_missing,
            "quarantined_rows": len(bundle.quality.quarantined),
            "orphaned_fk_count": bundle.quality.orphaned_fk_count,
        },
        "attendance": {
            "flagged_count": len(attendance_out.flagged),
            "ok_count": attendance_out.ok_count,
            "curator_alerts": len(attendance_out.curator_alerts),
        },
        "performance": {
            "top_10": [e.model_dump() for e in performance_out.leaderboard[:10]],
            "bottom_10": [e.model_dump() for e in performance_out.bottom_list[:10]],
        },
    }


def _git_commit_tag(repo_dir: str) -> str | None:
    try:
        result = run_cli(["git", "rev-parse", "--short", "HEAD"], cwd=repo_dir, timeout=5)
    except CLIExecutionError:
        return None
    return result.stdout if result.ok else None


def run_integration_agent(
    bundle: DataBundle,
    attendance_out: AttendanceAgentOutput,
    performance_out: PerformanceAgentOutput,
    data_repo_dir: str | None = None,
) -> IntegrationAgentOutput:
    flushed = flush_fallback_queue()
    if flushed:
        logger.info("Oldingi navbatdan %d yozuv bulutga muvaffaqiyatli yuborildi", flushed)

    payload = _build_summary_payload(bundle, attendance_out, performance_out)
    if data_repo_dir:
        commit = _git_commit_tag(data_repo_dir)
        if commit:
            payload["data_repo_commit"] = commit

    sync_result = sync_to_cloud(payload)

    sink = get_notification_sink()
    notifications: list[NotificationResult] = []
    for alert in attendance_out.curator_alerts:
        student = bundle.students.get(alert["student_id"])
        recipient = None
        if student and student.parent and student.parent.telegram:
            recipient = student.parent.telegram
        recipient = recipient or settings.telegram_default_chat_id
        if not recipient:
            notifications.append(
                NotificationResult(
                    channel="dry_run",
                    recipient="unknown",
                    ok=False,
                    error="Ota-ona/curator kontakti topilmadi — xabar yuborilmadi",
                )
            )
            continue
        notifications.append(sink.send(recipient, alert["message"]))

    mcp_client = get_mcp_client()
    mcp_ok, mcp_error = mcp_client.call_tool("publish_lms_report", payload)

    return IntegrationAgentOutput(
        sync=sync_result,
        notifications=notifications,
        mcp_published=mcp_ok,
        mcp_error=mcp_error,
    )
