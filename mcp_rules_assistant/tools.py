from __future__ import annotations

from dataclasses import dataclass
import builtins


@dataclass
class Tool:
    name: str
    description: str


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def list(self) -> builtins.list[Tool]:
        return list(self._tools.values())


registry = ToolRegistry()


def setup_default_tools() -> None:
    registry.register(
        Tool("project.detect", "Detect project language/framework/complexity"),
    )
    registry.register(Tool("project.switch", "Switch or create project context"))
    registry.register(Tool("project.link", "Add cross-project relationship link"))
    registry.register(Tool("memory.toggle_auto", "Enable/disable rolling memory"))
    registry.register(Tool("memory.snapshot", "Produce last 20 turns and summary"))
    registry.register(Tool("memory.append_turn", "Append a conversation turn"))
    registry.register(Tool("rules.init", "Select general rules by profile"))
    registry.register(Tool("rules.ingest", "Ingest project rules from docs"))
    registry.register(Tool("rules.validate", "Deduplicate and detect conflicts"))
    registry.register(Tool("rules.enforce", "Set enforcement level"))
    registry.register(
        Tool(
            "rules.onboard", "Interactive onboarding to choose and apply rules profile",
        ),
    )
    registry.register(Tool("env.prepare", "Prepare language environment"))
    registry.register(Tool("fs.apply_patch", "Guarded write with checks"))
    registry.register(Tool("git.install_hooks", "Install git hooks"))
    registry.register(Tool("nl.command", "Natural language command dispatcher"))
    registry.register(Tool("plan.update", "Update project plan markdown"))
    registry.register(Tool("plan.set", "Set plan fields (status/current/next)"))
    registry.register(Tool("plan.suggest_next", "Suggest next steps from memory/plan"))
    registry.register(Tool("config.get", "Get project config or section"))
    registry.register(Tool("config.update", "Update project config 'ci' section"))
    registry.register(Tool("ci.generate", "Generate CI workflow (GitHub Actions)"))
    registry.register(Tool("ci.validate", "Validate generated CI workflow content"))
    registry.register(Tool("ci.autofix", "Auto-fix CI by regenerating missing steps"))
    registry.register(Tool("coverage.near", "List files near threshold within window"))
    registry.register(
        Tool("coverage.report", "Summarize weak/groups/near in one payload"),
    )
    registry.register(
        Tool(
            "rules.maxima", "Return coverage upper-bounds (maxima) from compiled rules",
        ),
    )
    registry.register(
        Tool("env.diagnose", "Diagnose environment/tools/config presence"),
    )
    registry.register(
        Tool(
            "license.activate",
            "Activate license by copying JSON to ~/.mcp/license.json",
        ),
    )
    registry.register(Tool("license.verify", "Verify local license and return status"))
    registry.register(
        Tool("rules.resolve", "Resolve compiled rules into config (apply)"),
    )
    registry.register(Tool("ide.scaffold", "Generate per-IDE integration scaffold"))
    registry.register(
        Tool(
            "compliance.commitment",
            "Return AI compliance commitment text and optionally write to project",
        ),
    )
    registry.register(
        Tool(
            "security.audit_report",
            "Summarize security audit events from .mcp/dashboard/security_audit.jsonl",
        ),
    )
