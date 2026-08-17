"""CLI entrypoint.

    python -m agent_system.main --source .
    python -m agent_system.main --source export.zip
    python -m agent_system.main --source . --schedule     # hourly, via APScheduler

One-shot mode runs the full graph once and writes JSON reports to `reports/`.
Schedule mode is what Agent 3's "har soatda sinxronizatsiya" requirement maps
to in practice: re-run the whole pipeline (fresh ingest + both analysis
agents + cloud sync) on a fixed interval, so the cloud DB and Telegram alerts
always reflect the latest export.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone

from .config import settings
from .models import PipelineState
from .orchestrator import run_pipeline
from .report_text import build_summary_text

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger("agent_system.main")


def _write_reports(state: PipelineState) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = settings.reports_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / f"pipeline_state_{ts}.json").write_text(
        state.model_dump_json(indent=2, exclude={"bundle"}), encoding="utf-8"
    )
    (out_dir / "latest.json").write_text(
        state.model_dump_json(indent=2, exclude={"bundle"}), encoding="utf-8"
    )
    logger.info("Hisobot yozildi: %s", out_dir / f"pipeline_state_{ts}.json")


def _print_summary(state: PipelineState) -> None:
    print("\n" + build_summary_text(state))


def run_once(source: str) -> PipelineState:
    state = run_pipeline(source)
    _write_reports(state)
    _print_summary(state)
    return state


def main() -> int:
    parser = argparse.ArgumentParser(description="LMS multi-agent tahlil quvuri")
    parser.add_argument("--source", default=settings.data_source, help="Katalog yoki .zip fayl")
    parser.add_argument(
        "--schedule", action="store_true", help="Har soatda avtomatik qayta ishga tushirish"
    )
    args = parser.parse_args()

    if not args.schedule:
        state = run_once(args.source)
        return 1 if state.aborted else 0

    from apscheduler.schedulers.blocking import BlockingScheduler

    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(
        run_once,
        "interval",
        minutes=settings.sync_interval_minutes,
        args=[args.source],
        next_run_time=datetime.now(timezone.utc),  # run immediately, then on interval
        id="lms_pipeline_sync",
    )
    logger.info("Scheduler ishga tushdi: har %d daqiqada", settings.sync_interval_minutes)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
