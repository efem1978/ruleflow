import json
import os
from pathlib import Path
from typing import Any, Dict

import mcp_rules_assistant.dev_agent as dev


class RaisingDict(dict):
    """A dict that raises for specific keys on get() to hit defensive except blocks."""

    def __init__(self, *args, raise_keys=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._raise_keys = set(raise_keys or [])

    def get(self, key, default=None):  # type: ignore[override]
        if key in self._raise_keys:
            raise RuntimeError("boom")
        return super().get(key, default)


def _mk_dash(tmp: Path) -> Path:
    d = tmp / ".mcp" / "dashboard"
    d.mkdir(parents=True, exist_ok=True)
    return d


def test_update_failure_freeze_and_prev_coverage_read_exception(
    tmp_path: Path, monkeypatch
):
    """Covers: 593-594, 649-652, 673-674, 681-682, 687-688 defensive except paths."""

    agent = dev.DevAgent(project_root=tmp_path)
    dash = _mk_dash(tmp_path)

    # Preload fail counters to trigger freeze activation
    (dash / dev.FAIL_COUNTERS_FILE).write_text(
        json.dumps({"counters": {"tests": 10}, "last_trigger": {}, "freeze": {}}),
        encoding="utf-8",
    )

    # Status mapping that raises on coverage/progress/timestamp access
    status: Dict[str, Any] = RaisingDict(
        {
            "checks": {dev.STEP_LINT: "ok", dev.STEP_TYPE: "ok"},
            "tests": {"ok": True, "mode": "full"},
            "coverage": {"weak": []},
            "progress": {"overall": 1.0},
            "timestamp": 0.0,
        },
        raise_keys={"coverage", "progress", "timestamp"},
    )

    # Make _read_json raise when reading status.json (but not fail_counters)
    def _read_json_selective(p: Path):
        if p.name == dev.STATUS_FILE:
            raise RuntimeError("io")
        return {}

    monkeypatch.setattr(agent, "_read_json", _read_json_selective)

    agent._update_failure_and_freeze_status(status, dash)

    # Freeze must be present and fail_counters written
    assert isinstance(status.get("freeze"), dict)
    assert (dash / dev.FAIL_COUNTERS_FILE).exists()


def test_auto_append_memory_env_parse_and_append_exceptions(
    tmp_path: Path, monkeypatch
):
    """Covers: 767-772, 805-806, 813-815, 824-829 in _auto_append_memory."""

    agent = dev.DevAgent(project_root=tmp_path)
    dash = _mk_dash(tmp_path)

    os.environ.update(
        {
            "DEV_AGENT_MEM_ENABLE": "1",
            "DEV_AGENT_MEM_MIN_SEC": "bad",  # force int() except
            "DEV_AGENT_MEM_MAX_TURNS": "bad",  # force int() except
        }
    )

    # Status mapping that raises on weak/overall reads inside the helper
    status = RaisingDict(
        {"plan": {}, "coverage": {"weak": []}, "progress": {"overall": 0.5}},
        raise_keys={"coverage", "progress"},
    )

    class DummyMM:
        def __init__(self, *a, **k):
            pass

        def append_turn(self, *a, **k):  # always raise to hit outer+inner except
            raise RuntimeError("append-fail")

    monkeypatch.setattr(dev, "MemoryManager", DummyMM)

    # Make logger.debug also raise to hit the nested except
    class DummyLogger:
        def debug(self, *a, **k):
            raise RuntimeError("log-fail")

    # Avoid patching global logging.getLogger; override class property for this test
    monkeypatch.setattr(
        dev.DevAgent, "_log", property(lambda self: DummyLogger()), raising=False
    )

    ok = agent._auto_append_memory(status, dash)
    assert ok is False


def test_run_on_event_error_and_auto_append_raise(tmp_path: Path, monkeypatch):
    """Drive agent.run() for one cycle, force _on_evt exception, cover 1039/1041 and 1075/1076."""

    agent = dev.DevAgent(project_root=tmp_path)
    _mk_dash(tmp_path)

    # stub impacted/full to call on_event with a non-dict that makes dict(evt) fail
    def stub_impacted(self, *, cycle_idx: int, full_every: int = 5, on_event=None):
        if on_event:
            on_event(123)  # dict(123) -> TypeError
        return {"ok": True, "mode": "full", "code": 0, "stdout": "", "stderr": ""}

    monkeypatch.setattr(dev.DevAgent, "_run_impacted_or_full", stub_impacted)
    monkeypatch.setattr(
        dev.DevAgent,
        "_run_cycle_checks",
        lambda self, **k: {
            dev.STEP_LINT: "ok",
            dev.STEP_TYPE: "ok",
            dev.STEP_TESTS: "ok",
        },
    )
    monkeypatch.setattr(
        dev.DevAgent,
        "_ensure_dashboard_dir",
        lambda self, rebuild=True: _mk_dash(tmp_path),
    )
    # Make auto append memory raise to hit try/except around it
    monkeypatch.setattr(
        dev.DevAgent,
        "_auto_append_memory",
        lambda self, *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    agent.run(interval=1, max_cycles=1)


def test_main_env_parse_exception(monkeypatch):
    """Cover 1131-1132 in main(): invalid DEV_AGENT_MAX_CYCLES but do not run the loop."""

    monkeypatch.setenv("DEV_AGENT_MAX_CYCLES", "bad-int")
    called = {"ok": False}

    def stub_run(self, interval: int, max_cycles: int = 0):
        # ensure we don't enter the main loop
        called["ok"] = True

    monkeypatch.setattr(dev.DevAgent, "run", stub_run)
    dev.main(["--interval", "1", "--max-cycles", "0"])  # force env path
    assert called["ok"] is True


def test_collect_tasks_counts_and_plan_overall_extras(tmp_path: Path):
    """Cover 1442-1443 fallback and 1456-1457 pending-only branch."""

    # Trigger exception inside _collect_tasks_counts by giving non-existent plan path
    done, pending, pend_list, done_list = dev._collect_tasks_counts(
        tmp_path, plan_text="", include_docs=False
    )
    # The function should not crash and return ints/lists
    assert isinstance(done, int) and isinstance(pending, int)
    assert isinstance(pend_list, list) and isinstance(done_list, list)

    # Pending-only -> uses pending_len to compute plan_progress
    plan_prog, overall = dev._compute_plan_overall(
        0, 0, cov_progress=0.5, pending_len=3
    )
    assert plan_prog == 0.0
    assert overall == 0.6 * 0.5 + 0.4 * 0.0
