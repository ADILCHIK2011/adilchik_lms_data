"""Notification sinks for curator/parent alerts.

`DryRunSink` is the default — it "sends" by logging, so the pipeline is fully
runnable with zero secrets. `TelegramSink` activates automatically once
`TELEGRAM_BOT_TOKEN` is set (no code change needed). A failed Telegram send
is retried with backoff and, if still failing, reported as a failed
`NotificationResult` rather than raising — one parent's bad chat id must
never take down the whole notification run.
"""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod

import httpx

from .config import settings
from .models import NotificationResult

logger = logging.getLogger("agent_system.notify")

MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 1.5


class NotificationSink(ABC):
    @abstractmethod
    def send(self, recipient: str, message: str) -> NotificationResult: ...


class DryRunSink(NotificationSink):
    """No token configured -> log the message instead of sending it."""

    def send(self, recipient: str, message: str) -> NotificationResult:
        logger.info("[DRY-RUN Telegram -> %s] %s", recipient, message)
        return NotificationResult(channel="dry_run", recipient=recipient, ok=True)


class TelegramSink(NotificationSink):
    def __init__(self, bot_token: str):
        self._url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    def send(self, recipient: str, message: str) -> NotificationResult:
        last_error: str | None = None
        attempts_made = 0
        for attempt in range(MAX_RETRIES):
            attempts_made = attempt + 1
            try:
                with httpx.Client(timeout=10.0) as client:
                    resp = client.post(
                        self._url, json={"chat_id": recipient, "text": message}
                    )
                if resp.status_code == 200:
                    return NotificationResult(
                        channel="telegram", recipient=recipient, ok=True, retries=attempt
                    )
                last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                if resp.status_code == 429:
                    time.sleep(BACKOFF_BASE_SECONDS * (2**attempt))
                    continue
                break  # 4xx other than rate-limit is not retryable
            except httpx.HTTPError as exc:
                last_error = str(exc)
                time.sleep(BACKOFF_BASE_SECONDS * (2**attempt))

        return NotificationResult(
            channel="telegram",
            recipient=recipient,
            ok=False,
            error=last_error,
            retries=attempts_made - 1,
        )


def get_notification_sink() -> NotificationSink:
    if settings.telegram_bot_token:
        return TelegramSink(settings.telegram_bot_token)
    return DryRunSink()
