#!/usr/bin/env bash
# Environment self-diagnostics for RuleFlow (multi‑IDE, multi‑env, container aware)
# Produces:
#  - .mcp/dashboard/install_report.json
#  - .mcp/dashboard/install_report.md
#  - .mcp/dashboard/smoke.json (RPC smoke output, if succeeded)

set -uo pipefail

WS_ROOT="$(pwd)"
DASH="${WS_ROOT}/.mcp/dashboard"
mkdir -p "${DASH}" || true

log(){ printf "%s\n" "$*"; }

is_in_container(){
  if [[ -f "/.dockerenv" ]]; then return 0; fi
  if grep -qaE 'docker|containerd|kubepods' /proc/1/cgroup 2>/dev/null; then return 0; fi
  if [[ -n "${REMOTE_CONTAINERS-}" ]] || [[ -n "${DEVCONTAINER-}" ]]; then return 0; fi
  return 1
}

OS_NAME="$(uname -s 2>/dev/null || echo unknown)"
CONTAINER=0; if is_in_container; then CONTAINER=1; fi

# Python resolution
VENV_PY="${WS_ROOT}/.mcp/venv/bin/python"
PY="python3"
if [[ -x "${VENV_PY}" ]]; then PY="${VENV_PY}"; fi
VENV_EXISTS=0; [[ -x "${VENV_PY}" ]] && VENV_EXISTS=1

PY_OK=0
PKG_OK=0
PY_VER="$(${PY} -c 'import sys;print("%d.%d.%d"%sys.version_info[:3])' 2>/dev/null || true)"
if [[ -n "${PY_VER}" ]]; then PY_OK=1; fi
if ${PY} - <<'PY' >/dev/null 2>&1; then PKG_OK=1; fi
import importlib
import sys
m=None
try:
  m=importlib.import_module('mcp_rules_assistant')
except Exception:
  pass
print('ok' if m else 'no')
PY

# Node/npm
NODE_PRESENT=0; NODE_VER=""
if command -v node >/dev/null 2>&1; then NODE_PRESENT=1; NODE_VER="$(node -v 2>/dev/null || true)"; fi
NPM_PRESENT=0; NPM_VER=""
if command -v npm >/dev/null 2>&1; then NPM_PRESENT=1; NPM_VER="$(npm -v 2>/dev/null || true)"; fi

# IDE CLIs
VSCODE_CLI=0; command -v code >/dev/null 2>&1 && VSCODE_CLI=1
CURSOR_CLI=0; command -v cursor >/dev/null 2>&1 && CURSOR_CLI=1
WINDSURF_CLI=0; command -v windsurf >/dev/null 2>&1 && WINDSURF_CLI=1

# VS Code extension presence (if CLI available)
VSCODE_EXT_INSTALLED="null"
if [[ "${VSCODE_CLI}" -eq 1 ]]; then
  if code --list-extensions 2>/dev/null | grep -qi 'ruleflow.mcp-rules-assistant'; then
    VSCODE_EXT_INSTALLED="true"
  else
    VSCODE_EXT_INSTALLED="false"
  fi
fi

# Run RPC smoke (best effort)
SMOKE_PATH="${DASH}/smoke.json"
SMOKE_STATUS="fail"
if ${PY} scripts/mcp-rpc-smoke.py >"${SMOKE_PATH}" 2>"${DASH}/smoke.stderr"; then
  SMOKE_STATUS="ok"
fi

# Discover latest VSIX artifacts (both build dir and consolidated artifacts)
VSIX_LATEST=""
if ls -1 "${WS_ROOT}/extensions/vscode/mcp-rules-assistant-"*.vsix >/dev/null 2>&1; then
  VSIX_LATEST="$(ls -1 "${WS_ROOT}/extensions/vscode"/mcp-rules-assistant-*.vsix | sort -V | tail -n1)"
fi
if ls -1 "${WS_ROOT}/extensions/artifacts/mcp-rules-assistant-"*.vsix >/dev/null 2>&1; then
  VSIX_LATEST="$(ls -1 "${WS_ROOT}/extensions/artifacts"/mcp-rules-assistant-*.vsix | sort -V | tail -n1)"
fi

# WSL detection for tailored hints
WSL=0
if grep -qi 'microsoft\\|wsl' /proc/sys/kernel/osrelease 2>/dev/null; then WSL=1; fi
if [[ -n "${WSL_DISTRO_NAME-}" ]]; then WSL=1; fi

# Build JSON report
REPORT_JSON="${DASH}/install_report.json"
cat >"${REPORT_JSON}" <<JSON
{
  "ok": true,
  "os": "${OS_NAME}",
  "container": ${CONTAINER},
  "workspace": "${WS_ROOT}",
  "python": {
    "path": "${PY}",
    "version": "${PY_VER}",
    "ok": ${PY_OK},
    "venv": ${VENV_EXISTS},
    "has_mcp_rules_assistant": ${PKG_OK}
  },
  "node": {
    "present": ${NODE_PRESENT},
    "node": "${NODE_VER}",
    "npm_present": ${NPM_PRESENT},
    "npm": "${NPM_VER}"
  },
  "ides": {
    "vscode_cli": ${VSCODE_CLI},
    "cursor_cli": ${CURSOR_CLI},
    "windsurf_cli": ${WINDSURF_CLI},
    "vscode_extension_installed": ${VSCODE_EXT_INSTALLED}
  },
  "smoke": {
    "status": "${SMOKE_STATUS}",
    "path": "${SMOKE_PATH}"
  },
  "artifacts": {
    "vsix_latest": "${VSIX_LATEST}",
    "compat_report": "${WS_ROOT}/extensions/artifacts/compat_report.json",
    "near_list": "${WS_ROOT}/near_vscode.txt"
  }
}
JSON

# Build Markdown summary
REPORT_MD="${DASH}/install_report.md"
cat >"${REPORT_MD}" <<MD
# RuleFlow 安装与环境诊断报告

- **OS**: ${OS_NAME}
- **容器/Devcontainer**: $([[ ${CONTAINER} -eq 1 ]] && echo yes || echo no)
- **工作区**: ${WS_ROOT}

## Python
- **解释器**: ${PY}
- **版本**: ${PY_VER:-N/A}
- **venv 就绪**: $([[ ${VENV_EXISTS} -eq 1 ]] && echo yes || echo no)
- **mcp_rules_assistant 可导入**: $([[ ${PKG_OK} -eq 1 ]] && echo yes || echo no)

## Node / NPM
- **node**: $([[ ${NODE_PRESENT} -eq 1 ]] && echo ${NODE_VER} || echo not found)
- **npm**: $([[ ${NPM_PRESENT} -eq 1 ]] && echo ${NPM_VER} || echo not found)

## IDE CLI
- **VS Code**: $([[ ${VSCODE_CLI} -eq 1 ]] && echo yes || echo no)
- **Cursor**: $([[ ${CURSOR_CLI} -eq 1 ]] && echo yes || echo no)
- **Windsurf**: $([[ ${WINDSURF_CLI} -eq 1 ]] && echo yes || echo no)
- **VS Code 扩展已安装**: $(
  if [[ "${VSCODE_EXT_INSTALLED}" == "true" ]]; then echo yes; 
  elif [[ "${VSCODE_EXT_INSTALLED}" == "false" ]]; then echo no; 
  else echo unknown; fi)

## RPC 烟雾
- **状态**: ${SMOKE_STATUS}
- **结果文件**: ${SMOKE_PATH}

## 产物
- **最新 VSIX**: $( [[ -n "${VSIX_LATEST}" ]] && echo "${VSIX_LATEST}" || echo "(未发现 VSIX，请先构建或在宿主运行 one_click 脚本)" )
- **打包目录**: ${WS_ROOT}/extensions/vscode
- **归档目录**: ${WS_ROOT}/extensions/artifacts
- **VS Code 兼容报告**: $( [[ -f "${WS_ROOT}/extensions/artifacts/compat_report.json" ]] && echo "${WS_ROOT}/extensions/artifacts/compat_report.json" || echo "(未生成)" )
- **VS Code near 清单**: $( [[ -f "${WS_ROOT}/near_vscode.txt" ]] && echo "${WS_ROOT}/near_vscode.txt" || echo "(未生成)" )

## 下一步建议（自适应）
$(
  # 容器内的下一步：提示宿主安装 VSIX
  if [[ ${CONTAINER} -eq 1 ]]; then
    cat <<'S1'
- 容器内已完成后端与扩展（远端）安装。如需在宿主 VS Code 使用：
  - 在宿主执行：`bash scripts/one_click_vscode_setup.sh`
  - 或在宿主 VS Code 中“Install from VSIX…”并选择上面“最新 VSIX”。
S1
  fi
  # 宿主 + VS Code CLI 存在：直接命令安装 VSIX
  if [[ ${CONTAINER} -eq 0 && ${VSCODE_CLI} -eq 1 && -n "${VSIX_LATEST}" ]]; then
    echo "- 宿主 VS Code 安装扩展（命令行）：\n  - \`code --install-extension \"${VSIX_LATEST}\" --force\`"
  fi
  # 宿主 + 无 VS Code CLI（macOS）：用 GUI 打开 .vsix
  if [[ ${CONTAINER} -eq 0 && ${OS_NAME} == "Darwin" && ${VSCODE_CLI} -eq 0 && -n "${VSIX_LATEST}" ]]; then
    echo "- 宿主 VS Code 未检测到 CLI，可直接双击 VSIX 或：\n  - \`open -a \"Visual Studio Code\" \"${VSIX_LATEST}\"\`"
  fi
  # WSL 提示
  if [[ ${WSL} -eq 1 ]]; then
    cat <<'S2'
- 检测到 WSL：
  - 若 `code` 不可用，请在 Windows VS Code 安装“Remote - WSL”并启用“从 WSL 打开”，或在 Windows 侧 VS Code 执行“Install from VSIX…”。
S2
  fi
  # Cursor/Windsurf 指引
  if [[ -n "${VSIX_LATEST}" ]]; then
    echo "- Cursor/Windsurf：若 CLI 不可用，可在 macOS 直接双击 VSIX 或使用 Finder 右键 \'打开方式\' 选择对应应用安装。"
  fi
  # Python 包不可导入时的修复建议
  if [[ ${PKG_OK} -eq 0 ]]; then
    echo "- Python 包缺失：在工作区执行：\n  - \`${PY} -m pip install -U pip setuptools wheel\`\n  - \`${PY} -m pip install -e .\`"
  fi
  # 烟雾失败时的提示
  if [[ "${SMOKE_STATUS}" != "ok" ]]; then
    echo "- RPC 烟雾未通过：查看日志 \`.mcp/dashboard/server.log\` 和 \`.mcp/dashboard/smoke.stderr\`；在 VS Code 面板执行“RuleFlow: Load Coverage”验证后端响应。"
  fi
)

> 完整 JSON 报告: ${REPORT_JSON}
MD

log "[diagnose] 报告已生成：${REPORT_JSON} 与 ${REPORT_MD}"
exit 0
