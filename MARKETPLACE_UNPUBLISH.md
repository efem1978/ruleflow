# 删除/下架 VS Code Marketplace 扩展

## 📦 检查现有扩展

首先确认您在 Marketplace 上已发布的扩展：

```bash
# 登录（如果还没登录）
vsce login ruleflow

# 查看已发布的扩展
vsce show ruleflow.mcp-rules-assistant
```

---

## 🗑️ 下架扩展（两种方式）

### 方式 1：完全删除（不可恢复）

**警告**：此操作**不可撤销**，将永久删除扩展及其所有版本和统计数据。

```bash
cd extensions/vscode

# 删除扩展
vsce unpublish ruleflow.mcp-rules-assistant --force
```

### 方式 2：下架特定版本（推荐）

如果只想下架特定版本，保留其他版本：

```bash
# 下架指定版本
vsce unpublish ruleflow.mcp-rules-assistant@0.3.1
```

---

## 🤔 是否应该删除？

### 建议：**保留在 Marketplace**

**原因**：

1. **双渠道分发**：
   - ✅ Marketplace：方便发现和自动更新
   - ✅ 本地 .vsix：完全控制，适合企业/内网环境

2. **用户选择**：
   - 技术用户：可以用一键安装脚本（包含 .vsix）
   - 普通用户：可以在 Marketplace 搜索安装

3. **可见性**：
   - Marketplace 是 VS Code 用户发现新工具的主要途径
   - 下载数和评分对项目可信度有帮助

4. **无额外成本**：
   - Marketplace 托管完全免费
   - 不影响本地安装的用户

### 折中方案：**同时提供两种方式**

**在 README 中说明**：

```markdown
## 安装方式

### 方式 1：一键安装（推荐，包含 CLI + 扩展）
\`\`\`bash
bash install.sh
\`\`\`

### 方式 2：仅安装 VS Code 扩展
- **商店安装**：在 VS Code 扩展商店搜索 "RuleFlow"
- **本地安装**：`code --install-extension extensions/vscode/mcp-rules-assistant-0.3.2.vsix`
```

---

## 🔄 如果确实要删除

### 删除前的准备

1. **备份统计数据**：
   - 下载量、评分、评论等信息将永久丢失
   - 可以截图保存

2. **通知现有用户**（如果有）：
   - 在仓库 README 中说明
   - 在最后一个版本的更新说明中提示

3. **提供替代方案**：
   - 在 README 中突出显示本地安装方式

### 删除步骤

```bash
# 1. 登录
vsce login ruleflow

# 2. 确认要删除的扩展
vsce show ruleflow.mcp-rules-assistant

# 3. 执行删除
vsce unpublish ruleflow.mcp-rules-assistant --force

# 4. 验证
vsce show ruleflow.mcp-rules-assistant
# 应该返回 "Extension not found"
```

---

## 💡 我的建议

**不要删除，理由如下**：

1. ✅ **OSS 项目最大化触达**：Marketplace + 一键安装双渠道
2. ✅ **零成本维护**：发布后无需额外维护
3. ✅ **自动更新**：Marketplace 用户可自动获取更新
4. ✅ **社区发现**：更容易被新用户发现

**只需在 README 中明确两种安装方式即可**。
