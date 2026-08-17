"""Safe wrapper for programmatically running CLI / git-bash commands, per the
requirement that Agent 3 can shell out (e.g. `git pull` a data repo before
syncing, or `pg_dump` a backup). Two guardrails make this safe to call from
agent code that may itself be influenced by data:

  - argv only, never a shell string (`shell=True` is never used, so there is
    no command-injection surface even if a value inside `args` came from data)
  - the executable name must be in `settings.cli_allowlist`

Anything else raises `CLIExecutionError` before a subprocess is ever spawned.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass

from .config import settings


class CLIExecutionError(Exception):
    pass


@dataclass
class CLIResult:
    ok: bool
    stdout: str
    stderr: str
    returncode: int


def run_cli(args: list[str], cwd: str | None = None, timeout: int = 30) -> CLIResult:
    if not args:
        raise CLIExecutionError("Bo'sh buyruq")
    if args[0] not in settings.cli_allowlist:
        raise CLIExecutionError(
            f"'{args[0]}' ruxsat etilgan buyruqlar ro'yxatida yo'q: {settings.cli_allowlist}"
        )
    try:
        proc = subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
        return CLIResult(
            ok=proc.returncode == 0,
            stdout=proc.stdout.strip(),
            stderr=proc.stderr.strip(),
            returncode=proc.returncode,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return CLIResult(ok=False, stdout="", stderr=str(exc), returncode=-1)
