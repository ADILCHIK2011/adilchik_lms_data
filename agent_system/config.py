"""Central configuration, loaded from environment (.env) with safe local defaults.

Every external dependency (Postgres, Telegram, MCP, Anthropic) is optional at
runtime: if unset, the corresponding component runs in a dry-run / offline mode
instead of raising. This is what lets the pipeline run end-to-end on a laptop
with zero secrets configured, and then be handed real credentials in prod
without any code change.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    # --- data source ---
    data_source: str = os.getenv("LMS_DATA_SOURCE", str(BASE_DIR))
    reports_dir: Path = field(default_factory=lambda: BASE_DIR / "reports")

    # --- business rules (Agent 1) ---
    attendance_window_lessons: int = int(os.getenv("ATTENDANCE_WINDOW_LESSONS", "13"))
    attendance_min_present: int = int(os.getenv("ATTENDANCE_MIN_PRESENT", "7"))
    behind_streak_threshold: int = int(os.getenv("BEHIND_STREAK_THRESHOLD", "2"))

    # --- ranking weights (Agent 2) ---
    weight_attendance: float = float(os.getenv("WEIGHT_ATTENDANCE", "0.35"))
    weight_homework: float = float(os.getenv("WEIGHT_HOMEWORK", "0.30"))
    weight_score: float = float(os.getenv("WEIGHT_SCORE", "0.35"))
    weak_topic_score_threshold: float = float(os.getenv("WEAK_TOPIC_SCORE_THRESHOLD", "65"))

    # --- LLM (optional, Agent 2 narrative recommendations) ---
    anthropic_api_key: str | None = os.getenv("ANTHROPIC_API_KEY") or None
    llm_model: str = os.getenv("LLM_MODEL", "claude-sonnet-5")

    # --- Postgres / cloud DB (Agent 3) ---
    database_url: str | None = os.getenv("DATABASE_URL") or None
    sqlite_fallback_path: Path = field(
        default_factory=lambda: BASE_DIR / "reports" / "fallback_queue.sqlite3"
    )

    # --- Telegram (Agent 3) ---
    telegram_bot_token: str | None = os.getenv("TELEGRAM_BOT_TOKEN") or None
    telegram_default_chat_id: str | None = os.getenv("TELEGRAM_DEFAULT_CHAT_ID") or None

    # --- Telegram bot server (bot_server.py — interactive /analyze command) ---
    telegram_webhook_secret: str | None = os.getenv("TELEGRAM_WEBHOOK_SECRET") or None
    telegram_allowed_chat_ids: tuple[str, ...] = tuple(
        c.strip() for c in os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "").split(",") if c.strip()
    )
    # Render sets this automatically for web services; used to self-register the webhook on boot.
    public_base_url: str | None = os.getenv("RENDER_EXTERNAL_URL") or os.getenv("PUBLIC_BASE_URL") or None

    # --- MCP (Agent 3) ---
    mcp_server_url: str | None = os.getenv("MCP_SERVER_URL") or None

    # --- scheduler ---
    sync_interval_minutes: int = int(os.getenv("SYNC_INTERVAL_MINUTES", "60"))

    # --- safe CLI executor allowlist (Agent 3) ---
    cli_allowlist: tuple[str, ...] = (
        "git", "pg_dump", "psql", "python3", "python",
    )


settings = Settings()
settings.reports_dir.mkdir(parents=True, exist_ok=True)
