# 环境自适应（env-autotune）

env-autotune 根据本地开发环境与已编译项目规则，自动给出/应用 `.mcp/assistant.yaml` 的配置建议，以实现“规则—环境—配置”的闭环。

- 探测项：
  - docker / code / code-insiders / node（CLI 是否可用）
  - OS（windows/linux/darwin）、WSL
  - 项目根是否存在 `Dockerfile`
  - `.mcp/rules_compiled.json` 中的关键策略（如 `container.required`、`container.policy.baseline`）

- 调整逻辑（非破坏式，优先保留显式配置）：
  - 当本机有 docker 且启用了容器策略或存在 `Dockerfile` 时，建议开启 `ci.hadolint: true`
  - 当本机无 `code/code-insiders` CLI 时，建议 `ci.vscode_required: false`（避免 CI 强依赖 VS Code Job）
  - 其余仅给出“建议/提示”，不直接改写

## 用法

- 预览（不写入文件）：

```bash
python -m mcp_rules_assistant.cli env-autotune
```

- 应用（写入 `.mcp/assistant.yaml`）：

```bash
python -m mcp_rules_assistant.cli env-autotune --apply
```

- 输出格式：JSON（包含环境快照、策略标志、拟议变更、是否已应用）。

## 常见问题

- 没有 docker 但想在 CI 上执行 hadolint？
  - 本地保持默认即可；在 CI 的 `ci.yml` 中会按策略/配置启用 hadolint（可通过 `ci.hadolint_image/ci.hadolint_args` 调整）。
- 没有 VS Code CLI？
  - 在 Windows 侧安装“Remote - WSL”或直接用 VSIX 安装扩展；`env-autotune` 会建议设置 `ci.vscode_required=false`，避免 CI 强制 VS Code Job。
