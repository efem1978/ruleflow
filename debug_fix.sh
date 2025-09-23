#!/bin/bash

echo "=== 完整诊断和修复脚本 ==="

# 1. 停止所有MCP进程
echo "1. 停止现有MCP进程..."
pkill -f mcp_rules_assistant || true

# 2. 完全清理VSCode扩展
echo "2. 清理VSCode扩展..."
code --uninstall-extension ruleflow.mcp-rules-assistant || true
rm -rf ~/.vscode/extensions/ruleflow.mcp-rules-assistant* || true

# 3. 重新构建MCP环境
echo "3. 重建MCP环境..."
cd "/Users/aifei/Desktop/人工智能编程/Contextual-Cohesion-and-Programming-Rules-Assistant-MCP-Tool"
rm -rf .mcp/venv || true
python3 -m venv .mcp/venv
source .mcp/venv/bin/activate
pip install --upgrade pip
pip install -e .

# 4. 测试MCP服务
echo "4. 测试MCP服务..."
python -m mcp_rules_assistant.cli diagnose || echo "诊断命令执行完成"

# 5. 重建VSCode扩展
echo "5. 重建VSCode扩展..."
cd extensions/vscode
npm install
npm run compile
npm run package

# 6. 安装扩展
echo "6. 安装扩展..."
LATEST_VSIX=$(ls -t mcp-rules-assistant-*.vsix | head -n 1)
code --install-extension "$LATEST_VSIX" --force

# 7. 启动MCP服务
echo "7. 启动MCP后端服务..."
cd ../..
source .mcp/venv/bin/activate
nohup python -m mcp_rules_assistant.cli start > .mcp/mcp_server.log 2>&1 &
sleep 3

echo "8. 检查进程状态..."
ps aux | grep mcp_rules_assistant | grep -v grep

echo "完成！请重启VSCode并打开面板测试。"
echo "如果仍有问题，请查看:"
echo "- .mcp/mcp_server.log (MCP服务日志)"
echo "- VSCode开发者工具控制台 (前端错误)"
echo "- VSCode输出面板 'MCP Rules Assistant' 选项"
