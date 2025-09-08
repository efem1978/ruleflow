from __future__ import annotations

import json as _json
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Optional

import typer
import yaml
from rich import print as rprint

from . import __version__
from . import hooks as hooks_mod
from . import rules_ingest as rules_ingest
from . import server
from .auto_status import generate_status
from .config import (
    DEFAULT_PROJECT_CONFIG_PATH,
    ensure_project_config,
    human_summary,
    load_config,
)
from .coverage_summary import summarize as cov_summary
from .coverage_summary import summarize_groups as cov_groups
from .coverage_summary import summarize_near as cov_near
from .coverage_summary import summarize_tree as cov_tree
from .license_utils import generate_license, verify_license
from .mcp_server import JsonRpcServer
from .progress import ensure_plan, read_plan, update_plan_fields, write_plan

app = typer.Typer(add_completion=False, help="MCP Rules & Context Assistant CLI")


@app.command()
def init() -> None:
    """Initialize project config at .mcp/assistant.yaml"""
    ensure_project_config(DEFAULT_PROJECT_CONFIG_PATH)
    rprint(
        "[green]✔ Created[/] .mcp/assistant.yaml with performance defaults (Fast mode)"
    )


@app.command("license-status")
def license_status() -> None:
    """占位：显示简易许可状态（读取 ~/.mcp/license.json 是否存在）。"""
    lic = (Path.home() / ".mcp" / "license.json").resolve()
    if lic.exists():
        rprint({"ok": True, "activated": True, "path": str(lic)})
    else:
        rprint({"ok": True, "activated": False})


@app.command("license-activate")
def license_activate(
    file: str = typer.Option(..., "--file", help="许可文件路径（JSON）")
) -> None:
    """占位：激活许可（复制到 ~/.mcp/license.json）。"""
    src = Path(file).expanduser().resolve()
    if not src.exists():
        rprint({"ok": False, "message": f"license file not found: {src}"})
        raise typer.Exit(1)
    dst = (Path.home() / ".mcp" / "license.json").resolve()
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(str(src), str(dst))
    rprint({"ok": True, "activated": True, "path": str(dst)})


@app.command("license-verify")
def license_verify() -> None:
    """校验许可文件（演示版：有效期与签名一致性）。"""
    res = verify_license()
    rprint(res)


@app.command("license-generate")
def license_generate(
    issued_to: str = typer.Option(..., "--issued-to", help="被授权人/组织"),
    expires: str = typer.Option(..., "--expires", help="到期日 YYYY-MM-DD"),
    machine: str = typer.Option("", "--machine", help="机器指纹（可留空）"),
    alg: str = typer.Option("hs256", "--alg", help="hs256/rs256/ed25519"),
    private_key: Optional[str] = typer.Option(
        None, "--private-key", help="rs256/ed25519 私钥 PEM 路径"
    ),
    out: Optional[str] = typer.Option(None, "--out", help="输出路径（默认打印）"),
) -> None:
    """离线生成 license（演示版）：支持 hs256/rs256/ed25519。

    - hs256：使用环境变量 MCP_LICENSE_SALT（可选）计算签名；便于本地试用/演示。
    - rs256：需要 --private-key 指定 PEM 格式 RSA 私钥；验证通过 MCP_LICENSE_PUBKEY 公钥。
    - ed25519：需要 --private-key 指定 PEM 格式 Ed25519 私钥；验证通过 MCP_LICENSE_ED25519_PUBKEY 公钥。
    """
    pk_bytes = None
    if alg.lower() in {"rs256", "ed25519"}:
        if not private_key:
            rprint({"ok": False, "message": "--private-key required for rs256/ed25519"})
            raise typer.Exit(2)
        p = Path(private_key).expanduser().resolve()
        if not p.exists():
            rprint({"ok": False, "message": f"private key not found: {p}"})
            raise typer.Exit(2)
        pk_bytes = p.read_bytes()
    lic = generate_license(
        issued_to=issued_to,
        expires=expires,
        machine=machine,
        alg=alg,
        private_key_pem=pk_bytes,
    )
    text = _json.dumps(lic, ensure_ascii=False, indent=2)
    if out:
        op = Path(out).expanduser().resolve()
        op.parent.mkdir(parents=True, exist_ok=True)
        op.write_text(text, encoding="utf-8")
        rprint({"ok": True, "path": str(op)})
    else:
        rprint(text)


@app.command("precommit-migrate-stages")
def precommit_migrate_stages() -> None:
    """将 .pre-commit-config.yaml 中的 stages 从旧值（commit/push）改为新值（pre-commit/pre-push）。"""
    cfg = Path(".pre-commit-config.yaml")
    if not cfg.exists():
        rprint({"ok": False, "message": ".pre-commit-config.yaml not found"})
        raise typer.Exit(1)
    try:
        data = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
    except Exception as e:
        rprint({"ok": False, "message": f"yaml parse error: {e}"})
        raise typer.Exit(1)
    changed = False
    repos = data.get("repos") or []
    if isinstance(repos, list):
        for repo in repos:
            hooks = (repo or {}).get("hooks") or []
            if isinstance(hooks, list):
                for h in hooks:
                    st = (h or {}).get("stages")
                    if isinstance(st, list):
                        new_st = []
                        for s in st:
                            if s == "commit":
                                new_st.append("pre-commit")
                            elif s == "push":
                                new_st.append("pre-push")
                            else:
                                new_st.append(s)
                        if new_st != st:
                            h["stages"] = new_st
                            changed = True
    if changed:
        cfg.write_text(
            yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
    rprint({"ok": True, "changed": changed, "path": str(cfg)})


@app.command("print-config")
def print_config() -> None:
    cfg = load_config()
    rprint(cfg)


@app.command("explain-performance")
def explain_performance() -> None:
    cfg = load_config()
    rprint("[bold]Performance Summary[/]")
    rprint(human_summary(cfg))
    rprint("Defaults favor minimal overhead on save; heavier checks on push/CI.")


@app.command("start")
def start_server() -> None:
    server.start()


@app.command("version")
def version() -> None:
    rprint(f"mcp-rules-assistant {__version__}")


@app.command("install-hooks")
def install_hooks() -> None:
    """生成 .pre-commit-config.yaml 并安装 pre-commit & pre-push 钩子（极轻内环）。"""
    out = hooks_mod.install_git_hooks()
    rprint("[green]✔ Hooks installed[/]")
    for k, v in out.items():
        rprint(f" - {k}: {v}")
    rprint("若未安装 pre-commit，请先运行: pip install pre-commit")
    rprint(
        "首次使用建议：已尝试自动执行 pre-commit install（含 commit-msg 与 pre-push）。"
    )
    rprint(
        "提交门禁说明：需确保 .mcp/plan.md 处于 in_progress，且提交消息包含 [step:当前步骤]。"
    )
    rprint(
        "分支规范建议：feature 用 feat/*，修复用 fix/*，杂项用 chore/*（或遵循团队规范）。"
    )
    rprint(
        "本地打标签（可选）：完成里程碑可执行 git tag vX.Y.Z；如需发布包参见 docs/RELEASE.md。"
    )


@app.command("generate-ci")
def generate_ci() -> None:
    path = hooks_mod.generate_github_ci()
    rprint(f"[green]✔ CI workflow written[/] {path}")


@app.command("ingest-rules")
def ingest_rules(
    paths: list[str] = typer.Argument(..., help="文件或文件夹路径，可多选"),
) -> None:
    """摄取项目规则文档，生成编译版与冲突报告。"""
    res = rules_ingest.ingest(paths)
    rprint("[green]✔ 规则摄取完成[/]")
    rprint({k: v for k, v in res.items() if k in {"files", "extracted"}})
    if res.get("compiled", {}).get("conflicts"):
        rprint(
            "[yellow]存在规则冲突，请查看 .mcp/rules_compiled.md 的 Conflicts 段落[/]"
        )
    else:
        rprint("[green]无显著冲突[/]")


@app.command("rules-validate")
def rules_validate() -> None:
    """校验已摄取的规则原始数据并输出冲突/建议摘要。"""
    res = rules_ingest.compile_rules()
    if not res.get("ok"):
        rprint(
            f"[yellow]{res.get('message', '尚未摄取规则，请先运行 ingest-rules')}[/]"
        )
        raise typer.Exit(1)
    conflicts = res.get("conflicts", [])
    suggests = res.get("suggestions", [])
    rprint({"conflicts": len(conflicts), "suggestions": len(suggests)})


@app.command("rules-explain")
def rules_explain(
    json_out: bool = typer.Option(False, "--json", help="以 JSON 输出，便于管道处理"),
    with_suggestions: str = typer.Option(
        "none", "--with-suggestions", help="建议输出：none/short"
    ),
) -> None:
    """读取 .mcp/rules_compiled.json 并输出关键策略摘要（覆盖率阈值/门禁偏好/安全与容器策略/冲突数/建议数）。"""
    p = Path(".mcp/rules_compiled.json")
    if not p.exists():
        rprint("[yellow]尚未找到 .mcp/rules_compiled.json，请先运行 ingest-rules[/]")
        raise typer.Exit(1)
    import json as _json

    data = _json.loads(p.read_text(encoding="utf-8"))
    pol = data.get("policy", {}) or {}
    conflicts = data.get("conflicts", []) or []
    sugg = data.get("suggestions", []) or []
    meta = data.get("meta", {}) or {}
    maxima = meta.get("maxima", {}) if isinstance(meta.get("maxima", {}), dict) else {}
    if json_out:
        import json as _json

        payload: dict = {
            "coverage": {
                "min_module": pol.get("coverage.min_module"),
                "min_core": pol.get("coverage.min_core"),
            },
            "flags": {
                k: bool(pol.get(k))
                for k in [
                    "test.no_skip_xfail",
                    "test.warnings_as_errors",
                    "test.mutation_required",
                    "security.secrets_scan",
                    "security.sast_strict",
                    "container.required",
                    "container.policy.baseline",
                ]
                if k in pol
            },
            "conflicts": len(conflicts),
            "suggestions": len(sugg),
            "maxima": (
                {k: maxima.get(k) for k in sorted(maxima.keys())} if maxima else {}
            ),
            "suggestions_severity": {
                "must": sum(
                    1
                    for s in sugg
                    if isinstance(s, dict) and s.get("severity") == "must"
                ),
                "warn": sum(
                    1
                    for s in sugg
                    if isinstance(s, dict) and s.get("severity") == "warn"
                ),
                "info": sum(
                    1
                    for s in sugg
                    if isinstance(s, dict) and s.get("severity") == "info"
                ),
            },
        }
        if with_suggestions.lower() == "short":
            payload["suggestions_keys"] = [
                str(x.get("key")) for x in sugg if isinstance(x, dict) and x.get("key")
            ]
        print(_json.dumps(payload, ensure_ascii=False))
        return
    lines = []
    mm = pol.get("coverage.min_module")
    mc = pol.get("coverage.min_core")
    lines.append(
        f"coverage.min_module={mm if mm is not None else 'N/A'}; coverage.min_core={mc if mc is not None else 'N/A'}"
    )
    for k in [
        "test.no_skip_xfail",
        "test.warnings_as_errors",
        "test.mutation_required",
        "security.secrets_scan",
        "security.sast_strict",
        "container.required",
        "container.policy.baseline",
    ]:
        if k in pol:
            lines.append(f"{k}={bool(pol.get(k))}")
    lines.append(f"conflicts={len(conflicts)}; suggestions={len(sugg)}")
    if maxima:
        lines.append("maxima_keys: " + ", ".join(sorted(maxima.keys())[:20]))
    if sugg:
        must = sum(
            1 for s in sugg if isinstance(s, dict) and s.get("severity") == "must"
        )
        warn = sum(
            1 for s in sugg if isinstance(s, dict) and s.get("severity") == "warn"
        )
        info = sum(
            1 for s in sugg if isinstance(s, dict) and s.get("severity") == "info"
        )
        lines.append(f"suggestions_severity: must={must}, warn={warn}, info={info}")
    if maxima:
        lines.append("maxima_keys: " + ", ".join(sorted(maxima.keys())[:20]))
    if with_suggestions.lower() == "short":
        keys = [str(x.get("key")) for x in sugg if isinstance(x, dict) and x.get("key")]
        if keys:
            lines.append("suggestions_keys: " + ", ".join(keys[:20]))
    rprint("\n".join(lines))


@app.command("rules-onboard")
def rules_onboard(
    scenario: str = typer.Option(
        "personal", "--scenario", help="personal/pro/enterprise/institution"
    ),
    complexity: str = typer.Option("small", "--complexity", help="small/medium/large"),
    dev_mode: str = typer.Option("tdd", "--dev-mode", help="tdd/bdd/doc/spike"),
    apply: bool = typer.Option(True, "--apply/--dry-run", help="写入配置或仅预览"),
) -> None:
    """规则引导：选择场景/复杂度/模式并应用推荐阈值（min_module、是否启用变异测试）。"""
    from .rules import Complexity, Scenario, choose_thresholds, explain_thresholds

    try:
        th = choose_thresholds(Scenario(scenario), Complexity(complexity))
    except Exception:
        rprint("[yellow]输入无效，已回退到 personal/small[/]")
        th = choose_thresholds(Scenario.PERSONAL, Complexity.SMALL)
    if apply:
        ensure_project_config()
        p = DEFAULT_PROJECT_CONFIG_PATH
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except Exception:
            data = {}
        perf = (
            data.get("performance", {})
            if isinstance(data.get("performance", {}), dict)
            else {}
        )
        on_push = (
            perf.get("on_push", {}) if isinstance(perf.get("on_push", {}), dict) else {}
        )
        cov = (
            on_push.get("coverage", {})
            if isinstance(on_push.get("coverage", {}), dict)
            else {}
        )
        cov["min_module"] = float(th.coverage_min_module)
        on_push["coverage"] = cov
        on_push["mutation_test"] = bool(th.mutation_required)
        perf["on_push"] = on_push
        data["performance"] = perf
        p.write_text(
            yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
        rprint(
            {
                "ok": True,
                "scenario": scenario,
                "complexity": complexity,
                "devMode": dev_mode,
                "thresholds": explain_thresholds(th),
                "applied": True,
                "path": str(p),
            }
        )
    else:
        rprint(
            {
                "ok": True,
                "scenario": scenario,
                "complexity": complexity,
                "devMode": dev_mode,
                "thresholds": explain_thresholds(th),
                "applied": False,
            }
        )


@app.command("ide-scaffold")
def ide_scaffold(
    editor: str = typer.Option(..., "--editor", help="vscode/cursor/jetbrains/neovim")
) -> None:
    """生成各 IDE 最小集成脚手架（写入 .mcp/ide/<editor>/）。"""
    editor_l = editor.strip().lower()
    if editor_l not in {"vscode", "cursor", "jetbrains", "neovim"}:
        rprint({"ok": False, "message": "unsupported editor"})
        raise typer.Exit(1)
    srv = JsonRpcServer()
    srv.project_root = Path.cwd()
    res = srv._call_tool("ide.scaffold", {"editor": editor_l})
    rprint(res)


@app.command("compliance-commitment")
def compliance_commitment(
    out: Optional[str] = typer.Option(
        None, "--out", help="写入到指定路径（默认写入 .mcp/compliance.md）"
    ),
    dry: bool = typer.Option(False, "--dry-run", help="仅打印，不写入"),
) -> None:
    """输出/写入 AI 合规承诺（中文+英文）。"""
    srv = JsonRpcServer()
    srv.project_root = Path.cwd()
    res = srv._call_tool("compliance.commitment", {"write": not dry})
    if out:
        p = Path(out).expanduser().resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        # text is in res["text"]
        p.write_text(str(res.get("text", "")), encoding="utf-8")
        rprint({"ok": True, "path": str(p)})
    else:
        # 兜底：若未写入成功，CLI 侧直接写入标准路径
        if not dry:
            default_p = Path(".mcp/compliance.md")
            if not default_p.exists():
                default_p.parent.mkdir(parents=True, exist_ok=True)
                default_p.write_text(str(res.get("text", "")), encoding="utf-8")
        rprint(res)


@app.command("cleanup")
def cleanup(
    artifacts: bool = typer.Option(
        True, "--artifacts/--no-artifacts", help="清理测试与覆盖率工件"
    ),
) -> None:
    """清理常见工件（coverage.xml/.coverage/.pytest_cache/cov*.json 等）。"""
    removed: list[str] = []
    import glob
    from shutil import rmtree

    def rm(p: Path) -> None:
        try:
            if p.is_dir():
                rmtree(p, ignore_errors=True)
            elif p.exists():
                p.unlink()
            removed.append(str(p))
        except Exception:
            pass

    if artifacts:
        for pat in [
            "coverage.xml",
            ".coverage",
            ".coverage*",
            "cov.json",
            "cov*.json",
            "pytest-junit.xml",
        ]:
            for f in glob.glob(pat):
                rm(Path(f))
        rm(Path(".pytest_cache"))
        rm(Path("htmlcov"))
    rprint({"ok": True, "removed": removed})


@app.command("coverage")
def coverage() -> None:
    """读取 coverage.xml 并输出薄弱文件 Top 20（基于配置阈值/模块策略）。"""
    cfg = load_config()
    perf = (
        cfg.get("performance", {})
        if isinstance(cfg.get("performance", {}), dict)
        else {}
    )
    min_module = float(
        (perf.get("on_push", {}) or {}).get("coverage", {}).get("min_module", 0.9)
    )
    policy = (
        (cfg.get("coverage", {}) or {}).get("policy", None)
        if isinstance(cfg.get("coverage", {}), dict)
        else None
    )
    res = cov_summary(policy=policy, min_module=min_module)
    if not res.get("ok"):
        rprint(f"[yellow]{res.get('message', 'coverage.xml 不存在')}[/]")
        raise typer.Exit(1)
    weak_obj = res.get("weak", [])
    weak: list[dict] = list(weak_obj) if isinstance(weak_obj, list) else []
    if not weak:
        rprint("[green]覆盖率良好，未发现低于阈值的文件[/]")
        return
    rprint("[bold]覆盖率薄弱文件（Top 20）[/]")
    for it in weak:
        delta = float(
            it.get(
                "delta", float(it.get("threshold", 0)) - float(it.get("coverage", 0))
            )
        )
        rprint(
            f" - {it['coverage']*100:.1f}% < {int((it.get('threshold', 0))*100)}% (Δ {delta*100:.1f}%) — {it['file']}"
        )


@app.command("coverage-groups")
def coverage_groups() -> None:
    """按模块策略输出覆盖率分组摘要。"""
    cfg = load_config()
    perf = (
        cfg.get("performance", {})
        if isinstance(cfg.get("performance", {}), dict)
        else {}
    )
    min_module = float(
        (perf.get("on_push", {}) or {}).get("coverage", {}).get("min_module", 0.9)
    )
    policy = (
        (cfg.get("coverage", {}) or {}).get("policy", None)
        if isinstance(cfg.get("coverage", {}), dict)
        else None
    )
    res = cov_groups(policy=policy, min_module=min_module)
    if not res.get("ok"):
        rprint(f"[yellow]{res.get('message', 'coverage.xml 不存在')}[/]")
        raise typer.Exit(1)
    rprint("[bold]覆盖率分组摘要（按策略前缀）[/]")
    groups_obj = res.get("groups", [])
    groups: list[dict] = list(groups_obj) if isinstance(groups_obj, list) else []
    for g in groups:
        rprint(
            f" - {g['prefix']}: {g['coverage']*100:.1f}% < {int((g.get('threshold',0))*100)}% — 弱项 {g['weak_count']}/{g['files_count']}"
        )


@app.command("coverage-tree")
def coverage_tree() -> None:
    """按目录构建薄弱文件树（前3层），用于快速定位。"""
    cfg = load_config()
    perf = (
        cfg.get("performance", {})
        if isinstance(cfg.get("performance", {}), dict)
        else {}
    )
    min_module = float(
        (perf.get("on_push", {}) or {}).get("coverage", {}).get("min_module", 0.9)
    )
    policy = (
        (cfg.get("coverage", {}) or {}).get("policy", None)
        if isinstance(cfg.get("coverage", {}), dict)
        else None
    )
    res = cov_tree(policy=policy, min_module=min_module)
    if not res.get("ok"):
        rprint(f"[yellow]{res.get('message', 'coverage.xml 不存在')}[/]")
        raise typer.Exit(1)
    tree_obj = res.get("tree") or {}
    tree: dict = tree_obj if isinstance(tree_obj, dict) else {}

    def walk(node: dict, prefix: str = "") -> None:
        name = node.get("name", "")
        files = node.get("files", []) or []
        children = node.get("children") or {}
        if name and (files or children):
            rprint(f"{prefix}{name}/ ({len(files)} files)")
        for f in files[:5]:
            rprint(
                f"{prefix}  - {f.get('coverage',0)*100:.1f}% < {int((f.get('threshold',0))*100)}% — {f.get('file')}"
            )
        for k in sorted(children.keys()):
            walk(children[k], prefix + "  ")

    walk(tree, "")


@app.command("coverage-near")
def coverage_near(
    within: Optional[float] = typer.Option(
        None, help="距阈值百分比（例如 3 = 3%），留空使用配置 coverage.near.within"
    ),
    top: Optional[int] = typer.Option(
        None, help="显示前 N 个，留空使用配置 coverage.near.top"
    ),
    policy_prefix: str = typer.Option("", help="仅显示以该前缀开头的文件（可为空）"),
    format: str = typer.Option("text", help="输出格式：text/json/csv"),
    output: Optional[str] = typer.Option(None, help="将结果写入文件（可选）"),
) -> None:
    """显示“未低于阈值但距离阈值不超过 within%”的文件清单。"""
    cfg = load_config()
    perf = (
        cfg.get("performance", {})
        if isinstance(cfg.get("performance", {}), dict)
        else {}
    )
    min_module = float(
        (perf.get("on_push", {}) or {}).get("coverage", {}).get("min_module", 0.9)
    )
    policy = (
        (cfg.get("coverage", {}) or {}).get("policy", None)
        if isinstance(cfg.get("coverage", {}), dict)
        else None
    )
    near_cfg = (
        (cfg.get("coverage", {}) or {}).get("near", {})
        if isinstance(cfg.get("coverage", {}), dict)
        else {}
    )
    within_pct = (
        float(near_cfg.get("within", 0.03) * 100.0) if within is None else float(within)
    )
    top_n = int(near_cfg.get("top", 20)) if top is None else int(top)
    within_pct = max(1.0, min(10.0, within_pct))
    res = cov_near(
        policy=policy, min_module=min_module, within=within_pct / 100.0, top=top_n
    )
    if not res.get("ok"):
        rprint(f"[yellow]{res.get('message', 'coverage.xml 不存在')}[/]")
        raise typer.Exit(1)
    near_obj = res.get("near", [])
    near: list[dict] = list(near_obj) if isinstance(near_obj, list) else []
    if policy_prefix:
        near = [it for it in near if str(it.get("file", "")).startswith(policy_prefix)]
    if not near:
        rprint("[green]无近阈值文件（均高于阈值超过设定窗口）[/]")
        return
    fmt = format.lower()
    if fmt == "json":
        import json as _json

        text = _json.dumps(near, ensure_ascii=False)
        if output:
            Path(output).write_text(text, encoding="utf-8")
        else:
            print(text)
        return
    if fmt == "csv":
        import csv

        if output:
            with open(output, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["file", "coverage", "threshold", "delta_up"])
                for it in near:
                    w.writerow(
                        [
                            it.get("file", ""),
                            it.get("coverage", 0.0),
                            it.get("threshold", 0.0),
                            it.get("delta_up", 0.0),
                        ]
                    )
        else:
            import sys

            w = csv.writer(sys.stdout)
            w.writerow(["file", "coverage", "threshold", "delta_up"])
            for it in near:
                w.writerow(
                    [
                        it.get("file", ""),
                        it.get("coverage", 0.0),
                        it.get("threshold", 0.0),
                        it.get("delta_up", 0.0),
                    ]
                )
        return
    rprint("[bold]近阈值文件（距阈值以内）[/]")
    for it in near:
        delta_up = float(it.get("delta_up", 0.0))
        rprint(
            f" - {it['coverage']*100:.1f}% ≥ {int((it.get('threshold', 0))*100)}% (距阈值 {delta_up*100:.1f}%) — {it['file']}"
        )


@app.command("coverage-clean-cache")
def coverage_clean_cache() -> None:
    """删除覆盖率解析缓存文件 .mcp/coverage_cache.json"""
    p = Path(".mcp/coverage_cache.json")
    if p.exists():
        try:
            p.unlink()
            rprint("[green]✔ 已删除缓存[/] .mcp/coverage_cache.json")
        except Exception as e:
            rprint(f"[yellow]删除失败：{e}[/]")
            raise typer.Exit(1)
    else:
        rprint("[yellow]未找到缓存文件（已是干净状态）[/]")


@app.command("coverage-report")
def coverage_report(
    json_out: bool = typer.Option(
        True, "--json/--text", help="以 JSON 输出（默认）或文本"
    ),
    within: Optional[float] = typer.Option(
        None, help="近阈值窗口（百分比），留空用配置"
    ),
    top: Optional[int] = typer.Option(None, help="近阈值 Top，留空用配置"),
) -> None:
    """汇总 coverage 弱项、分组与近阈值，便于一次性查看或导出。"""
    cfg = load_config()
    perf = (
        cfg.get("performance", {})
        if isinstance(cfg.get("performance", {}), dict)
        else {}
    )
    min_module = float(
        (perf.get("on_push", {}) or {}).get("coverage", {}).get("min_module", 0.9)
    )
    policy = (
        (cfg.get("coverage", {}) or {}).get("policy", None)
        if isinstance(cfg.get("coverage", {}), dict)
        else None
    )
    near_cfg = (
        (cfg.get("coverage", {}) or {}).get("near", {})
        if isinstance(cfg.get("coverage", {}), dict)
        else {}
    )
    within_pct = (
        float(near_cfg.get("within", 0.03) * 100.0) if within is None else float(within)
    )
    top_n = int(near_cfg.get("top", 20)) if top is None else int(top)
    within_pct = max(1.0, min(10.0, within_pct))

    res_sum = cov_summary(policy=policy, min_module=min_module)
    if not res_sum.get("ok"):
        rprint(f"[yellow]{res_sum.get('message', 'coverage.xml 不存在')}[/]")
        raise typer.Exit(1)
    res_grp = cov_groups(policy=policy, min_module=min_module)
    res_near = cov_near(
        policy=policy, min_module=min_module, within=within_pct / 100.0, top=top_n
    )

    if json_out:
        import json as _json

        _w_obj = res_sum.get("weak", [])
        _g_obj = res_grp.get("groups", [])
        _n_obj = res_near.get("near", [])
        w_list: list = _w_obj if isinstance(_w_obj, list) else []
        g_list: list = _g_obj if isinstance(_g_obj, list) else []
        n_list: list = _n_obj if isinstance(_n_obj, list) else []
        payload = {
            "weak": w_list,
            "groups": g_list,
            "near": n_list,
            "min_module": min_module,
        }
        print(_json.dumps(payload, ensure_ascii=False))
        return
    # text output (compact)
    rprint("[bold]Weak (Top)")
    _obj_w = res_sum.get("weak", [])
    weak_list: list = _obj_w if isinstance(_obj_w, list) else []
    for it in weak_list[:20]:
        delta = float(
            it.get(
                "delta", float(it.get("threshold", 0)) - float(it.get("coverage", 0))
            )
        )
        rprint(
            f" - {it['coverage']*100:.1f}% < {int((it.get('threshold', 0))*100)}% (Δ {delta*100:.1f}%) — {it['file']}"
        )
    rprint("[bold]Groups")
    _obj_g = res_grp.get("groups", [])
    grp_list: list = _obj_g if isinstance(_obj_g, list) else []
    for g in grp_list:
        rprint(
            f" - {g['prefix']}: {g['coverage']*100:.1f}% < {int((g.get('threshold',0))*100)}% — 弱项 {g['weak_count']}/{g['files_count']}"
        )
    rprint("[bold]Near")
    _obj_n = res_near.get("near", [])
    near_list: list = _obj_n if isinstance(_obj_n, list) else []
    for it in near_list:
        delta_up = float(it.get("delta_up", 0.0))
        rprint(
            f" - {it['coverage']*100:.1f}% ≥ {int((it.get('threshold', 0))*100)}% (距阈值 {delta_up*100:.1f}%) — {it['file']}"
        )


@app.command("diagnose")
def diagnose(
    json_out: bool = typer.Option(
        True, "--json/--text", help="以 JSON 输出（默认）或文本"
    ),
) -> None:
    """诊断环境/工具/配置与关键文件存在性（便于排障）。"""
    cfg = load_config()
    perf = (
        cfg.get("performance", {})
        if isinstance(cfg.get("performance", {}), dict)
        else {}
    )
    min_module = float(
        (perf.get("on_push", {}) or {}).get("coverage", {}).get("min_module", 0.9)
    )
    coverage_exists = Path("coverage.xml").exists()
    compiled_exists = Path(".mcp/rules_compiled.json").exists()
    maxima = {}
    if compiled_exists:
        try:
            data = _json.loads(
                Path(".mcp/rules_compiled.json").read_text(encoding="utf-8")
            )
            meta = data.get("meta", {}) or {}
            if isinstance(meta.get("maxima", {}), dict):
                maxima = meta.get("maxima", {})
        except Exception:
            maxima = {}
    tools = {
        "python": sys.executable,
        "ruff": shutil.which("ruff") or "",
        "black": shutil.which("black") or "",
        "isort": shutil.which("isort") or "",
        "mypy": shutil.which("mypy") or "",
        "bandit": shutil.which("bandit") or "",
        "pytest": shutil.which("pytest") or "",
        "pre-commit": shutil.which("pre-commit") or "",
        "semgrep": shutil.which("semgrep") or "",
        "hadolint": shutil.which("hadolint") or "",
        "docker": shutil.which("docker") or "",
    }
    # hooks installed status and writable checks
    hooks_dir = Path(".git/hooks")
    hooks = {
        "installed": hooks_dir.exists(),
        "pre_commit": (hooks_dir / "pre-commit").exists(),
        "pre_push": (hooks_dir / "pre-push").exists(),
        "commit_msg": (hooks_dir / "commit-msg").exists(),
    }
    writable = {
        "project_root": os.access(Path.cwd(), os.W_OK),
        ".mcp": (
            os.access(Path(".mcp"), os.W_OK)
            if Path(".mcp").exists()
            else os.access(Path.cwd(), os.W_OK)
        ),
    }
    ci = {
        "workflow_exists": Path(".github/workflows/ci.yml").exists(),
        "dockerfile_exists": Path("Dockerfile").exists(),
    }
    # suggestions: simple guidance based on current findings
    suggestions: list[str] = []
    if not coverage_exists:
        suggestions.append(
            "未找到 coverage.xml：运行 pytest 生成覆盖率，例如 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p pytest_cov --cov --cov-report=xml:coverage.xml`"
        )
    if not hooks.get("installed"):
        suggestions.append(
            "未安装本地钩子：执行 `mcp-rules-assistant install-hooks` 并按提示启用 pre-commit/pre-push"
        )
    if not ci.get("workflow_exists"):
        suggestions.append(
            "未找到 CI 工作流：执行 `mcp-rules-assistant generate-ci` 并将变更提交到仓库"
        )
    if not writable.get("project_root") or not writable.get(".mcp"):
        suggestions.append(
            "当前目录或 .mcp 目录不可写：检查文件权限或以具备写权限的用户运行"
        )

    payload = {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "tools": tools,
        "config": {"min_module": min_module},
        "coverage": {"exists": coverage_exists},
        "rules": {"compiled_exists": compiled_exists},
        "maxima": maxima,
        "hooks": hooks,
        "writable": writable,
        "ci": ci,
        "suggestions": suggestions,
    }
    if json_out:
        print(_json.dumps(payload, ensure_ascii=False))
        return
    # text
    rprint("[bold]Diagnose")
    rprint(f"python={payload['python_version']} platform={payload['platform']}")
    rprint(f"min_module={min_module}")
    rprint(f"coverage.xml exists={coverage_exists}; compiled_rules={compiled_exists}")
    rprint("tools:")
    for k, v in tools.items():
        rprint(f" - {k}: {v or 'missing'}")
    if suggestions:
        rprint("[bold]Suggestions[/]")
        for s in suggestions:
            rprint(f" - {s}")


@app.command("status-update")
def status_update(json_out: bool = typer.Option(True, "--json/--text")) -> None:
    """Refresh dashboard status (.mcp/dashboard/status.json) from plan/memory/coverage.

    Prints the status in JSON (default) or compact text.
    """
    payload = generate_status()
    if json_out:
        import json as _json

        print(_json.dumps(payload, ensure_ascii=False))
        return
    rprint("[bold]Status[/]")
    rprint(
        f"plan: status={payload['plan']['status']} current={payload['plan']['current']} next={payload['plan']['next']}"
    )
    cov = payload.get("coverage", {}) or {}
    rprint(
        f"coverage: count={cov.get('count',0)} weak={len(cov.get('weak',[]) or [])} progress={cov.get('progress',0):.2f}"
    )


def _scan_plan_tasks(text: str) -> tuple[list[str], list[str]]:
    pending: list[str] = []
    done: list[str] = []
    in_code = False
    for raw in text.splitlines():
        s = raw.rstrip()
        st = s.strip()
        if st.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        ls = s.lstrip()
        if ls.startswith("- [ ] "):
            pending.append(ls[6:].strip())
        elif ls.startswith(("- [x] ", "- [X] ")):
            done.append(ls[6:].strip())
    return pending, done


@app.command("plan-tasks")
def plan_tasks(
    json_out: bool = typer.Option(True, "--json/--text", help="输出 JSON（默认）或文本")
) -> None:
    """仅从 .mcp/plan.md 提取任务清单（权威）。"""
    p = ensure_plan()
    text = p.read_text(encoding="utf-8")
    pending, done = _scan_plan_tasks(text)
    if json_out:
        print(
            _json.dumps(
                {
                    "pending": pending,
                    "done": done,
                    "counts": {"pending": len(pending), "done": len(done)},
                },
                ensure_ascii=False,
            )
        )
        return
    rprint("[bold]Plan Tasks[/]")
    rprint(f"pending={len(pending)} done={len(done)}")
    if pending:
        rprint("[bold]Pending[/]")
        for it in pending:
            rprint(f" - {it}")
    if done:
        rprint("[bold]Done[/]")
        for it in done:
            rprint(f" - {it}")


@app.command("rules-suggestions")
def rules_suggestions(
    format: str = typer.Option("text", help="输出格式：text/json/csv"),
    output: Optional[str] = typer.Option(None, help="将结果写入文件（可选）"),
) -> None:
    """输出已编译规则的建议清单（含 severity）。"""
    p = Path(".mcp/rules_compiled.json")
    if not p.exists():
        rprint("[yellow]尚未找到 .mcp/rules_compiled.json，请先运行 ingest-rules[/]")
        raise typer.Exit(1)
    import json as _json

    data = _json.loads(p.read_text(encoding="utf-8"))
    sugg = data.get("suggestions", []) or []
    fmt = format.lower()
    if fmt == "json":
        text = _json.dumps(sugg, ensure_ascii=False)
        if output:
            Path(output).write_text(text, encoding="utf-8")
        else:
            print(text)
        return
    if fmt == "csv":
        import csv

        rows = []
        for s in sugg:
            if isinstance(s, dict):
                rows.append(
                    [
                        s.get("key", ""),
                        s.get("action", ""),
                        s.get("severity", ""),
                        s.get("value", ""),
                        s.get("note", ""),
                    ]
                )
        if output:
            with open(output, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["key", "action", "severity", "value", "note"])
                w.writerows(rows)
        else:
            import sys

            w = csv.writer(sys.stdout)
            w.writerow(["key", "action", "severity", "value", "note"])
            w.writerows(rows)
        return
    # text
    lines = ["[bold]Suggestions[/]"]
    for s in sugg:
        if isinstance(s, dict):
            key = s.get("key", "")
            act = s.get("action", "")
            sev = s.get("severity", "")
            val = s.get("value", None)
            if val is not None:
                lines.append(f" - [{sev}] {key} → {val} ({act})")
            else:
                lines.append(f" - [{sev}] {key} ({act})")
    rprint("\n".join(lines))


@app.command("plan-init")
def plan_init() -> None:
    path = ensure_plan()
    rprint(f"[green]✔ 计划文件已生成[/] {path}")


@app.command("plan-open")
def plan_open() -> None:
    print(read_plan())


@app.command("plan-update")
def plan_update(
    text: str = typer.Argument(..., help="计划内容 Markdown（可粘贴）")
) -> None:
    path = write_plan(text)
    rprint(f"[green]✔ 计划已更新[/] {path}")


@app.command("plan-set")
def plan_set(
    status: Optional[str] = typer.Option(None, help="计划状态，如 in_progress/done"),
    current: Optional[str] = typer.Option(None, help="当前步骤"),
    next_step: Optional[str] = typer.Option(None, help="下一步"),
) -> None:
    """快捷设置 .mcp/plan.md 的状态/当前/下一步。"""
    update_plan_fields(status=status, current=current, nxt=next_step)
    rprint("[green]✔ 计划已更新[/]")


@app.command("plan-current")
def plan_current(
    text: str = typer.Argument(..., help="设置当前步骤（覆盖原值）")
) -> None:
    update_plan_fields(current=text)
    rprint("[green]✔ 当前步骤已更新[/]")


@app.command("plan-next")
def plan_next(text: str = typer.Argument(..., help="设置下一步（覆盖原值）")) -> None:
    update_plan_fields(nxt=text)
    rprint("[green]✔ 下一步已更新[/]")


@app.command("plan-done")
def plan_done() -> None:
    update_plan_fields(status="done")
    rprint("[green]✔ 计划状态已设置为 done[/]")


@app.command("license-require-on")
def license_require_on() -> None:
    """在项目配置中启用 license.required: true（发布硬门禁，开发默认仍可关闭）。"""
    ensure_project_config()
    p = DEFAULT_PROJECT_CONFIG_PATH
    import yaml as _yaml

    try:
        data = _yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        data = {}
    lic = data.get("license", {}) if isinstance(data.get("license", {}), dict) else {}
    lic["required"] = True
    data["license"] = lic
    p.write_text(
        _yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    rprint("[green]✔ license.required 已启用（发布模式）[/]")


@app.command("license-require-off")
def license_require_off() -> None:
    """在项目配置中关闭 license.required（开发/本地模式）。"""
    ensure_project_config()
    p = DEFAULT_PROJECT_CONFIG_PATH
    import yaml as _yaml

    try:
        data = _yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        data = {}
    lic = data.get("license", {}) if isinstance(data.get("license", {}), dict) else {}
    lic["required"] = False
    data["license"] = lic
    p.write_text(
        _yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    rprint("[green]✔ license.required 已关闭（开发模式）[/]")


@app.command("ci-set")
def ci_set(
    hadolint: Optional[bool] = typer.Option(None, help="是否在 CI 中启用 hadolint"),
    semgrep_config: Optional[str] = typer.Option(
        None, help="semgrep 规则集（如 auto/p/ci 等）"
    ),
    hadolint_image: Optional[str] = typer.Option(None, help="hadolint 容器镜像"),
    hadolint_args: Optional[str] = typer.Option(None, help="hadolint 额外参数"),
    vscode_required: Optional[bool] = typer.Option(
        None, help="是否强制在 CI 中运行 VS Code 扩展测试（不再按文件存在性判断）"
    ),
) -> None:
    """更新项目配置文件 `.mcp/assistant.yaml` 中的 CI 相关字段。未传的字段保持不变。"""
    ensure_project_config()
    p = DEFAULT_PROJECT_CONFIG_PATH
    data: dict = {}
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        data = {}
    ci = data.get("ci", {}) if isinstance(data.get("ci", {}), dict) else {}
    changed = False
    if hadolint is not None:
        ci["hadolint"] = bool(hadolint)
        changed = True
    if semgrep_config is not None:
        ci["semgrep_config"] = semgrep_config
        changed = True
    if hadolint_image is not None:
        ci["hadolint_image"] = hadolint_image
        changed = True
    if hadolint_args is not None:
        ci["hadolint_args"] = hadolint_args
        changed = True
    if vscode_required is not None:
        ci["vscode_required"] = bool(vscode_required)
        changed = True
    if not changed:
        rprint({"ci": ci})
        raise typer.Exit(0)
    data["ci"] = ci
    p.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    rprint("[green]✔ CI 配置已更新[/]")


@app.command("ci-validate")
def ci_validate() -> None:
    """校验现有 CI 工作流是否包含关键步骤。"""
    ci_file = Path(".github/workflows/ci.yml")
    exists = ci_file.exists()
    content = ci_file.read_text(encoding="utf-8") if exists else ""
    checks = {
        "exists": exists,
        "has_precommit": "pre-commit run --all-files" in content,
        "has_hadolint": "hadolint" in content,
        "has_semgrep": "semgrep --error" in content,
        "has_tests": "pytest -q" in content,
        "has_bandit": "bandit -q" in content,
    }
    rprint(checks)


@app.command("ci-autofix")
def ci_autofix() -> None:
    """自修复 CI：按当前规则/配置覆盖生成标准 CI（若已有则备份）。"""
    res = hooks_mod.autofix_github_ci()
    rprint(
        {
            "path": res.get("path"),
            "changed": res.get("changed"),
            "backup": res.get("backup"),
        }
    )


@app.command("maintenance")
def maintenance() -> None:
    """一键维护：安装 Git hooks 并自修复/覆盖生成 CI。

    - 写入 .pre-commit-config.yaml、.git/hooks（commit-msg/pre-push/TDD gate）
    - 覆盖生成 .github/workflows/ci.yml（保留备份）
    """
    out_hooks = hooks_mod.install_git_hooks()
    out_ci = hooks_mod.autofix_github_ci()
    rprint("[green]✔ Maintenance completed[/]")
    rprint(
        {
            "hooks": out_hooks,
            "ci": {k: out_ci.get(k) for k in ("path", "changed", "backup")},
        }
    )


@app.command("enforce")
def enforce() -> None:
    """应用已编译规则到配置并输出门禁摘要（调用 rules.enforce）。"""
    srv = JsonRpcServer()
    out = srv._call_tool("rules.enforce", {})
    if not out.get("ok"):
        rprint("[red]✘ enforce 失败[/]")
        raise typer.Exit(1)
    changed = out.get("changed")
    enforced = out.get("enforced", [])
    rprint("[green]✔ enforce 成功[/] 配置已更新: " + ("是" if changed else "否"))
    if enforced:
        rprint("[bold]Enforced gates[/]")
        for e in enforced:
            rprint(f" - {e}")
    # 下一步建议
    next_steps = []
    if any(str(e).startswith("ci.") for e in enforced):
        next_steps.append("generate-ci")
    # 若已存在编译规则，建议安装 hooks
    next_steps.append("install-hooks")
    rprint("[bold]Next[/]")
    for n in next_steps:
        rprint(f" - {n}")


@app.command("insert-security-samples")
def insert_security_samples() -> None:
    """在项目根插入安全工具示例配置：.semgrep.yml 与 .hadolint.yaml"""
    semgrep = (
        "rules:\n"
        "  - id: py-no-eval\n"
        '    message: "Avoid eval() — security risk"\n'
        "    languages: [python]\n"
        "    severity: ERROR\n"
        "    pattern: eval(...)\n\n"
        "  - id: py-no-exec\n"
        '    message: "Avoid exec() — security risk"\n'
        "    languages: [python]\n"
        "    severity: ERROR\n"
        "    pattern: exec(...)\n"
    )
    hadolint = (
        "ignored:\n"
        "  - DL3008\n"
        "  - DL3059\n\n"
        "overrides:\n"
        "  DL3007: warning\n"
    )
    Path(".semgrep.yml").write_text(semgrep, encoding="utf-8")
    Path(".hadolint.yaml").write_text(hadolint, encoding="utf-8")
    rprint("[green]✔ 已插入示例规则[/] .semgrep.yml / .hadolint.yaml")


@app.command("rules-export")
def rules_export(
    out_dir: Optional[str] = typer.Option(
        None, "--out-dir", help="输出目录（为空时打印到标准输出）"
    ),
    format: str = typer.Option("all", "--format", help="md/json/all（默认 all）"),
) -> None:
    """导出编译规则与建议（用于交接/审阅）。"""
    root = Path.cwd()
    compiled_md = root / ".mcp/rules_compiled.md"
    compiled_json = root / ".mcp/rules_compiled.json"
    sugg_md = root / ".mcp/rules_suggestions.md"
    fmt = format.lower()
    want_md = fmt in ("md", "all")
    want_json = fmt in ("json", "all")
    if out_dir:
        outp = Path(out_dir).expanduser().resolve()
        outp.mkdir(parents=True, exist_ok=True)
        if want_md:
            if compiled_md.exists():
                (outp / "rules_compiled.md").write_text(
                    compiled_md.read_text(encoding="utf-8"), encoding="utf-8"
                )
            if sugg_md.exists():
                (outp / "rules_suggestions.md").write_text(
                    sugg_md.read_text(encoding="utf-8"), encoding="utf-8"
                )
        if want_json and compiled_json.exists():
            (outp / "rules_compiled.json").write_text(
                compiled_json.read_text(encoding="utf-8"), encoding="utf-8"
            )
        rprint({"ok": True, "out_dir": str(outp)})
        return
    # stdout
    if want_json and compiled_json.exists():
        print(compiled_json.read_text(encoding="utf-8"))
    if want_md:
        if compiled_md.exists():
            print("\n# Compiled Rules (Markdown)\n")
            print(compiled_md.read_text(encoding="utf-8"))
        if sugg_md.exists():
            print("\n# Suggestions (Markdown)\n")
            print(sugg_md.read_text(encoding="utf-8"))


@app.command("prepare-env")
def prepare_env(
    python: Optional[str] = typer.Option(None, help="Python 解释器路径（可选）"),
    create: bool = typer.Option(True, help="创建虚拟环境 .mcp/venv"),
    install: bool = typer.Option(False, help="在 venv 中安装工具链"),
    dry_run: bool = typer.Option(
        False, help="仅输出计划，不执行（等效于 --no-create --install False）"
    ),
    packages: Optional[str] = typer.Option(
        None, help="自定义安装包列表，逗号分隔（在 --install 时生效）"
    ),
) -> None:
    """准备本地开发环境（创建 venv 并安装工具）。

    示例：
    - dry-run: mcp-rules-assistant prepare-env --dry-run
    - 安装工具：mcp-rules-assistant prepare-env --install
    """
    srv = JsonRpcServer()
    args: dict = {}
    if python:
        args["python"] = python
    if dry_run:
        args["create"] = False
        args["install"] = False
    else:
        args["create"] = bool(create)
        args["install"] = bool(install)
    if install and packages:
        pkgs = [p.strip() for p in packages.split(",") if p.strip()]
        if pkgs:
            args["packages"] = pkgs
    out = srv._call_tool("env.prepare", args)
    if not out.get("ok"):
        rprint("[red]✘ env.prepare 失败[/]")
        raise typer.Exit(1)
    rprint(out)


@app.command("coverage-near-set")
def coverage_near_set(
    within: float = typer.Option(
        3.0, help="距阈值百分比（例如 3 = 3%），范围建议 1–10"
    ),
    top: int = typer.Option(50, help="显示前 N 个（默认 50）"),
) -> None:
    """更新项目配置中 coverage.near 窗口与 top。"""
    ensure_project_config(DEFAULT_PROJECT_CONFIG_PATH)
    p = DEFAULT_PROJECT_CONFIG_PATH
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        data = {}
    cov = data.get("coverage", {}) if isinstance(data.get("coverage", {}), dict) else {}
    cov["near"] = {"within": float(within) / 100.0, "top": int(top)}
    data["coverage"] = cov
    p.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    rprint({"coverage": {"near": cov.get("near")}})


if __name__ == "__main__":
    app()
