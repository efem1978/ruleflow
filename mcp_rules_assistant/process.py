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

    def _emit(evt: Dict[str, Any]) -> None:
        try:
            if on_event:
                on_event(evt)
        finally:
            if do_log:
                phase = evt.get("phase")
                if phase == "start":
                    logger.info(
                        "run_cmd start attempt=%s cwd=%s cmd=%s",
                        evt.get("attempt"),
                        evt.get("cwd"),
                        " ".join(cmd),
                    )
                elif phase == "end":
                    logger.info(
                        "run_cmd end rc=%s elapsed=%.3fs cmd=%s",
                        evt.get("returncode"),
                        evt.get("elapsed", 0.0),
                        " ".join(cmd),
                    )
                elif phase == "error":
                    logger.warning(
                        "run_cmd error attempt=%s err=%r cmd=%s",
                        evt.get("attempt"),
                        evt.get("exception"),
                        " ".join(cmd),
                    )
        # 可选：将事件追加落盘，默认关闭；通过 MCP_RUN_CMD_EVENTS=1 开启
        try:
            if os.environ.get("MCP_RUN_CMD_EVENTS", "0") in ("1", "true", "True"):
                root = Path(str(cwd))
                out_dir = root / ".mcp" / "dashboard"
                out_dir.mkdir(parents=True, exist_ok=True)
                jl = out_dir / "cmd_events.jsonl"
                import json as _json

                jl.write_text(
                    (jl.read_text("utf-8") if jl.exists() else "")
                    + _json.dumps(evt, ensure_ascii=False)
                    + "\n",
                    encoding="utf-8",
                )
                # 简易滚动：超过 200 行时仅保留末尾 200 行
                try:
                    lines = jl.read_text("utf-8").splitlines()
                    if len(lines) > 200:
                        jl.write_text("\n".join(lines[-200:]) + "\n", encoding="utf-8")
                except Exception:
                    pass
        except Exception:
            # 不影响主流程
            pass

    while True:
        try:
            t0 = time.time()
            if (
                on_event
                or do_log
                or os.environ.get("MCP_RUN_CMD_EVENTS", "0") in ("1", "true", "True")
            ):
                _emit(
                    {
                        "phase": "start",
                        "cmd": cmd,
                        "cwd": str(cwd),
                        "attempt": attempt,
                    }
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
            if (
                on_event
                or do_log
                or os.environ.get("MCP_RUN_CMD_EVENTS", "0") in ("1", "true", "True")
            ):
                elapsed = max(0.0, time.time() - t0)
                _emit(
                    {
                        "phase": "end",
                        "cmd": cmd,
                        "cwd": str(cwd),
                        "attempt": attempt,
                        "returncode": getattr(p, "returncode", None),
                        "elapsed": elapsed,
                    }
                )
            return p
        except Exception as e:  # noqa: BLE001 - deliberate broad retry boundary
            if (
                on_event
                or do_log
                or os.environ.get("MCP_RUN_CMD_EVENTS", "0") in ("1", "true", "True")
            ):
                _emit(
                    {
                        "phase": "error",
                        "cmd": cmd,
                        "cwd": str(cwd),
                        "attempt": attempt,
                        "exception": repr(e),
                    }
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
