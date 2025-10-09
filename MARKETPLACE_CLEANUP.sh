#!/bin/bash
# VS Code Marketplace 清理脚本

set -e

echo "🔍 检查 VS Code Marketplace 上的 RuleFlow 扩展"
echo "================================================"
echo ""

cd extensions/vscode

# 检查可能的 publisher 名称
PUBLISHERS=(
    "ruleflow"
    "efem1978"
    "mcp-rules-assistant"
)

echo "📋 检查可能的 publisher..."
echo ""

for publisher in "${PUBLISHERS[@]}"; do
    echo "检查: ${publisher}.mcp-rules-assistant"
    vsce show "${publisher}.mcp-rules-assistant" 2>&1 | grep -q "not found" && {
        echo "  ❌ 未找到"
    } || {
        echo "  ✅ 找到！"
        echo ""
        echo "扩展详情:"
        vsce show "${publisher}.mcp-rules-assistant"
        echo ""
        echo "---"
        echo ""
        echo "⚠️  发现旧版本扩展: ${publisher}.mcp-rules-assistant"
        echo ""
        read -p "是否删除此扩展？(y/N): " confirm
        if [[ "$confirm" =~ ^[Yy]$ ]]; then
            echo "🗑️  删除扩展..."
            vsce unpublish "${publisher}.mcp-rules-assistant" --force
            echo "✅ 删除成功"
        else
            echo "⏭️  跳过删除"
        fi
        echo ""
    }
done

echo ""
echo "✅ 检查完成"
echo ""
echo "📝 下一步:"
echo "  1. 如果没有找到旧版本,可以直接发布新版本"
echo "  2. 发布新版本: cd extensions/vscode && vsce publish"
