#!/bin/bash

echo "=== 修复VSCode扩展安装问题 ==="

# 1. 确保VSCode完全关闭
echo "1. 检查VSCode进程..."
pkill -f "Visual Studio Code" || true
sleep 2

# 2. 清理扩展缓存和残留
echo "2. 清理扩展残留..."
rm -rf ~/.vscode/extensions/ruleflow.mcp-rules-assistant* || true
rm -rf ~/.vscode/extensions/.obsolete || true

# 3. 卸载扩展（如果存在）
echo "3. 卸载现有扩展..."
/Applications/Visual\ Studio\ Code.app/Contents/Resources/app/bin/code --uninstall-extension ruleflow.mcp-rules-assistant || true

# 4. 安装扩展
echo "4. 安装扩展..."
cd "/Users/aifei/Desktop/人工智能编程/Contextual-Cohesion-and-Programming-Rules-Assistant-MCP-Tool/extensions/vscode"
/Applications/Visual\ Studio\ Code.app/Contents/Resources/app/bin/code --install-extension mcp-rules-assistant-0.2.6.vsix --force

# 5. 验证安装
echo "5. 验证安装..."
/Applications/Visual\ Studio\ Code.app/Contents/Resources/app/bin/code --list-extensions | grep ruleflow

# 6. 打开VSCode到工作区
echo "6. 启动VSCode..."
cd "/Users/aifei/Desktop/人工智能编程/Contextual-Cohesion-and-Programming-Rules-Assistant-MCP-Tool"
/Applications/Visual\ Studio\ Code.app/Contents/Resources/app/bin/code .

echo ""
echo "✅ 完成！"
echo ""
echo "请在VSCode中检查："
echo "1. 状态栏左下角应该显示 'RuleFlow'"
echo "2. 命令面板中搜索 'RuleFlow' 应该有可用命令"
echo "3. 查看 → 输出 → 选择 'MCP Rules Assistant' 查看日志"
echo ""
echo "如果状态栏仍然没有显示，请尝试："
echo "- 按 Cmd+Shift+P 输入 'RuleFlow: Open Panel'"
echo "- 或使用快捷键 Cmd+Shift+R"
