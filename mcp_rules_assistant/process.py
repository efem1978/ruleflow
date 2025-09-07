from __future__ import annotations

import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

DEFAULT_TIMEOUT: float = 300.0


def run_cmd(
    cmd: list[str],
    *,
    cwd: Path,
    capture_stdout: bool = True,
    env: Optional[Dict[str, str]] = None,
    check: bool = False,
    timeout: Optional[float] = DEFAULT_TIMEOUT,
    retries: int = 0,
    backoff: float = 0.5,
    retry_on_timeout_only: bool = False,
    on_event: Optional[Callable[[Dict[str, Any]], None]] = None,
    log: bool = False,
):
    """Unified subprocess runner with test-friendly defaults + optional retry.

    - Minimal kwargs path for compatibility with simple test doubles.
    - Text mode when capturing; capture stderr alongside stdout; trim long outputs.
    - Retries only on raised exceptions (e.g., TimeoutExpired/OS errors). Disabled by default.
    """
    attempt = 0
    delay = max(0.0, float(backoff))
    do_log = log or os.environ.get("MCP_RUN_CMD_LOG", "0") in ("1", "true", "True")
    logger = logging.getLogger("mcp.run_cmd")
    while True:
        try:
            t0 = time.time()
            if on_event or do_log:
                evt = {
                    "phase": "start",
                    "cmd": cmd,
                    "cwd": str(cwd),
                    "attempt": attempt,
                }
                try:
                    if on_event:
                        on_event(evt)
                finally:
                    if do_log:
                        logger.info(
                            "run_cmd start attempt=%s cwd=%s cmd=%s",
                            attempt,
                            cwd,
                            " ".join(cmd),
                        )
            if (
                not capture_stdout
                and env is None
                and (timeout is None or timeout == DEFAULT_TIMEOUT)
            ):
                p = subprocess.run(cmd, cwd=str(cwd), check=check)
            else:
                kwargs: Dict[str, object] = {"text": True}
                if capture_stdout:
                    kwargs["stdout"] = subprocess.PIPE
                    kwargs["stderr"] = subprocess.PIPE
                if env is not None:
                    kwargs["env"] = env
                if timeout is not None:
                    kwargs["timeout"] = timeout
                p = subprocess.run(cmd, cwd=str(cwd), check=check, **kwargs)  # type: ignore[call-overload]
                try:
                    if isinstance(p.stdout, str) and len(p.stdout) > 8000:
                        p.stdout = p.stdout[-8000:]
                except Exception:
                    pass
                try:
                    if (
                        isinstance(getattr(p, "stderr", None), str)
                        and len(p.stderr) > 8000
                    ):
                        p.stderr = p.stderr[-8000:]
                except Exception:
                    pass
            if on_event or do_log:
                elapsed = max(0.0, time.time() - t0)
                evt = {
                    "phase": "end",
                    "cmd": cmd,
                    "cwd": str(cwd),
                    "attempt": attempt,
                    "returncode": getattr(p, "returncode", None),
                    "elapsed": elapsed,
                }
                try:
                    if on_event:
                        on_event(evt)
                finally:
                    if do_log:
                        logger.info(
                            "run_cmd end rc=%s elapsed=%.3fs cmd=%s",
                            getattr(p, "returncode", None),
                            elapsed,
                            " ".join(cmd),
                        )
            return p
        except Exception as e:  # noqa: BLE001 - deliberate broad retry boundary
            if on_event or do_log:
                evt = {
                    "phase": "error",
                    "cmd": cmd,
                    "cwd": str(cwd),
                    "attempt": attempt,
                    "exception": repr(e),
                }
                try:
                    if on_event:
                        on_event(evt)
                finally:
                    if do_log:
                        logger.warning(
                            "run_cmd error attempt=%s err=%r cmd=%s",
                            attempt,
                            e,
                            " ".join(cmd),
                        )
            if attempt >= int(retries):
                raise
            if retry_on_timeout_only and not isinstance(e, subprocess.TimeoutExpired):
                raise
            try:
                time.sleep(delay)
            except Exception:  # pragma: no cover
                pass
            delay = max(delay * 2.0, delay)
            attempt += 1
