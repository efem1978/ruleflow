安全工具示例 / Security Tools Samples

目的
- 提供可直接落地的 hadolint 与 semgrep 示例配置，便于在 CI 中启用安全扫描。
- 示例均为“轻量默认”，可按需扩展，不影响保存阶段性能。

示例 1：.hadolint.yaml（Dockerfile 规则）
```yaml
ignored:
  - DL3008   # Pin versions in apk add — 可按团队策略选择
  - DL3059   # Multiple consecutive RUN — 可根据镜像层策略调整

overrides:
  DL3007: warning   # 使用最新 apk 索引仅警告
```

示例 2：.semgrep.yml（Python 轻量规则）
```yaml
rules:
  - id: py-no-eval
    message: "Avoid eval() — security risk"
    languages: [python]
    severity: ERROR
    pattern: eval(...)

  - id: py-no-exec
    message: "Avoid exec() — security risk"
    languages: [python]
    severity: ERROR
    pattern: exec(...)
```

集成方式
- VS Code 面板：点击“插入示例规则”即可在项目根生成 `.hadolint.yaml` 与 `.semgrep.yml`（可编辑）。
- CI：
  - hadolint：`mcp-rules-assistant ci-set --hadolint`（可用 `--hadolint-image/--hadolint-args` 定制）
  - semgrep：`mcp-rules-assistant ci-set --semgrep-config p/ci`（或使用仓库根的 `.semgrep.yml`）
 - CLI：`mcp-rules-assistant insert-security-samples` 可快速插入示例 `.semgrep.yml` 与 `.hadolint.yaml`

注意
- 示例仅作参考，请结合同步安全策略与合规要求进行调整。
