package com.ruleflow

import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.Messages
import com.intellij.openapi.wm.ToolWindow
import com.intellij.openapi.wm.ToolWindowFactory
import com.intellij.ui.content.ContentFactory
import java.awt.BorderLayout
import java.awt.FlowLayout
import java.io.File
import javax.swing.JButton
import javax.swing.JLabel
import javax.swing.JPanel
import javax.swing.JScrollPane
import javax.swing.JTextArea
import javax.swing.JList
import javax.swing.DefaultListModel
import javax.swing.JCheckBox
import java.awt.event.MouseAdapter
import java.awt.event.MouseEvent

class RuleFlowToolWindowFactory : ToolWindowFactory {
    override fun createToolWindowContent(project: Project, toolWindow: ToolWindow) {
        val panel = JPanel(BorderLayout())
        val top = JPanel(FlowLayout(FlowLayout.LEFT))
        val lblStatus = JLabel("RuleFlow MCP (Preview) — plan/memory")
        top.add(lblStatus)

        val btnPlan = JButton("加载计划 / Load Plan")
        val btnMemory = JButton("加载记忆 / Load Memory")
        val btnCoverage = JButton("加载覆盖率摘要 / Load Coverage Summary")
        val btnMcpStart = JButton("启动 MCP")
        val btnMcpStop = JButton("停止 MCP")
        val btnMcpPing = JButton("MCP: Ping")
        val btnMcpList = JButton("MCP: 资源列表")
        val btnMcpPlan = JButton("MCP: 加载计划")
        val btnCfgYaml = JButton("MCP: 配置 YAML")
        val btnCiYaml = JButton("MCP: CI 工作流")
        val btnCiGen = JButton("CI: 生成")
        val btnCiVal = JButton("CI: 校验")
        val btnHooks = JButton("Git: 安装 hooks")
        val btnMcpIngest = JButton("MCP: 规则摄取")
        val btnMcpCovReport = JButton("MCP: 覆盖率报告")
        val btnFsDry = JButton("MCP: 受控写入(dry-run)")
        val btnFsWrite = JButton("MCP: 受控写入(严格写入)")
        val cbFsPost = JCheckBox("写入后检查(fs_guard_post_checks)", false)
        val cbFsStrict = JCheckBox("严格(fs_guard_strict)", false)
        val btnFsApplyCfg = JButton("应用受控写入配置")
        val btnFsDryMulti = JButton("MCP: 多文件(dry-run)")
        val btnFsWriteMulti = JButton("MCP: 多文件(严格)")
        val btnOpenPlan = JButton("在编辑器打开计划")
        val btnOpenMemory = JButton("在编辑器打开记忆")
        top.add(btnPlan)
        top.add(btnMemory)
        top.add(btnCoverage)
        top.add(btnOpenPlan)
        top.add(btnOpenMemory)
        top.add(btnMcpStart)
        top.add(btnMcpList)
        top.add(btnMcpPlan)
        top.add(btnMcpIngest)
        top.add(btnMcpCovReport)
        top.add(btnMcpPing)
        top.add(btnMcpStop)
        top.add(btnCiGen)
        top.add(btnCiVal)
        top.add(btnHooks)
        top.add(btnCfgYaml)
        top.add(btnCiYaml)
        top.add(cbFsPost)
        top.add(cbFsStrict)
        top.add(btnFsApplyCfg)
        top.add(btnFsDry)
        top.add(btnFsWrite)
        top.add(btnFsDryMulti)
        top.add(btnFsWriteMulti)

        val text = JTextArea(20, 80)
        text.isEditable = false
        val scroll = JScrollPane(text)
        val chkPretty = JCheckBox("JSON 美化", true)
        val chkFold = JCheckBox("折叠长输出", true)
        top.add(chkPretty)
        top.add(chkFold)

        fun readFile(rel: String): String {
            val base = project.basePath ?: return "(no project base)"
            val f = File(base, rel)
            if (!f.exists()) return "$rel not found"
            return try {
                val raw = f.readText()
                if (raw.length > 60_000) raw.substring(0, 60_000) + "\n... (truncated)" else raw
            } catch (e: Exception) {
                "read error: ${e.message}"
            }
        }

        btnPlan.addActionListener {
            val content = readFile(".mcp/plan.md")
            text.text = content
        }
        btnMemory.addActionListener {
            val content = readFile(".mcp/memory.json")
            text.text = content
        }

        // Models and lists for weak/near coverage, defined before handlers to satisfy Kotlin scoping
        val weakModel = DefaultListModel<String>()
        val nearModel = DefaultListModel<String>()
        val weakJList = JList(weakModel)
        val nearJList = JList(nearModel)

        fun extractArray(json: String, key: String): String? {
            val anchor = "\"$key\""
            val i = json.indexOf(anchor)
            if (i < 0) return null
            var j = json.indexOf('[', i)
            if (j < 0) return null
            var depth = 0
            var k = j
            while (k < json.length) {
                val ch = json[k]
                if (ch == '[') depth++
                if (ch == ']') {
                    depth--
                    if (depth == 0) {
                        return json.substring(j, k + 1)
                    }
                }
                k++
            }
            return null
        }

        btnCoverage.addActionListener {
            val raw = readFile(".mcp/dashboard/status.json")
            try {
                val weakArr = extractArray(raw, "weak") ?: "[]"
                val nearArr = extractArray(raw, "near") ?: "[]"
                val weakList = mutableListOf<String>()
                val nearList = mutableListOf<String>()
                val itemRegex = "\"file\"\\s*:\\s*\"([^\"]+)\"[\\s\\S]*?\"coverage\"\\s*:\\s*([0-9.]+)".toRegex()
                for (m in itemRegex.findAll(weakArr)) {
                    val f = m.groupValues[1]
                    val c = (m.groupValues[2].toDoubleOrNull() ?: 0.0) * 100.0
                    weakList.add(String.format("- %.1f%% — %s", c, f))
                }
                for (m in itemRegex.findAll(nearArr)) {
                    val f = m.groupValues[1]
                    val c = (m.groupValues[2].toDoubleOrNull() ?: 0.0) * 100.0
                    nearList.add(String.format("- %.1f%% — %s", c, f))
                }
                val sb = StringBuilder()
                sb.append("Weak: ").append(weakList.size).append('\n')
                // update model
                weakModel.removeAllElements()
                weakList.forEach { sb.append(it).append('\n'); weakModel.addElement(it) }
                sb.append('\n')
                sb.append("Near: ").append(nearList.size).append('\n')
                nearModel.removeAllElements()
                nearList.take(20).forEach { sb.append(it).append('\n'); nearModel.addElement(it) }
                sb.append('\n').append(raw)
                text.text = sb.toString()
            } catch (e: Exception) {
                text.text = raw
            }
        }

        fun openInEditor(rel: String) {
            val base = project.basePath
            if (base == null) {
                Messages.showWarningDialog(project, "Unknown base path", "RuleFlow")
                return
            }
            val f = File(base, rel)
            if (!f.exists()) {
                Messages.showInfoMessage(project, "$rel not found", "RuleFlow")
                return
            }
            val v = com.intellij.openapi.vfs.LocalFileSystem.getInstance().refreshAndFindFileByIoFile(f)
            if (v == null) {
                Messages.showWarningDialog(project, "Cannot locate VFS file", "RuleFlow")
                return
            }
            com.intellij.openapi.fileEditor.FileEditorManager.getInstance(project).openFile(v, true)
        }
        btnOpenPlan.addActionListener { openInEditor(".mcp/plan.md") }
        btnOpenMemory.addActionListener { openInEditor(".mcp/memory.json") }

        // ---- MCP integration (minimal) ----
        val mcp = McpClient()
        btnMcpStart.addActionListener {
            if (!mcp.isRunning()) mcp.start(project)
            lblStatus.text = if (mcp.isRunning()) "MCP 运行中" else "MCP 启动失败"
        }
        btnMcpStop.addActionListener {
            mcp.stop()
            lblStatus.text = "MCP 已停止"
        }
        btnMcpPing.addActionListener {
            try {
                if (!mcp.isRunning()) mcp.start(project)
                val out = mcp.request("ping")
                text.text = out
            } catch (e: Exception) {
                text.text = "MCP 请求失败: ${e.message}"
            }
        }
        btnMcpList.addActionListener {
            try {
                if (!mcp.isRunning()) mcp.start(project)
                val out = mcp.request("resources/list")
                text.text = if (chkPretty.isSelected) prettyJson(out) else out
            } catch (e: Exception) {
                text.text = "MCP 请求失败: ${e.message}"
            }
        }

        // 受控写入：将 UI 勾选映射到项目配置（execution.fs_guard_post_checks / fs_guard_strict）
        btnFsApplyCfg.addActionListener {
            try {
                if (!mcp.isRunning()) mcp.start(project)
                val payload = "{\"data\":{\"execution\":{\"fs_guard_post_checks\":" + (if (cbFsPost.isSelected) "true" else "false") + ",\"fs_guard_strict\":" + (if (cbFsStrict.isSelected) "true" else "false") + "}}}"
                val out = mcp.request("tools/call", "{\"name\":\"config.update\",\"arguments\":$payload}", 8000)
                text.text = if (chkPretty.isSelected) prettyJson(out) else out
            } catch (e: Exception) {
                text.text = "MCP 请求失败: ${e.message}"
            }
        }
        btnMcpPlan.addActionListener {
            try {
                if (!mcp.isRunning()) mcp.start(project)
                val resList = mcp.request("resources/list")
                val planUri = extractFirstUri(resList, "progress://", "/plan")
                if (planUri == null) {
                    text.text = resList
                } else {
                    val params = "{\"uri\":\"${planUri}\"}"
                    val out = mcp.request("resources/read", params)
                    val mime = extractString(out, "mimeType") ?: "text/plain"
                    val body = extractString(out, "text") ?: out
                    text.text = if (mime.contains("json")) (if (chkPretty.isSelected) prettyJson(body) else body) else "[$mime]\n\n$body"
                }
            } catch (e: Exception) {
                text.text = "MCP 请求失败: ${e.message}"
            }
        }

        btnCiGen.addActionListener {
            try {
                if (!mcp.isRunning()) mcp.start(project)
                val out = mcp.request("tools/call", "{\"name\":\"ci.generate\",\"arguments\":{}}", 12000)
                text.text = if (chkPretty.isSelected) prettyJson(out) else out
            } catch (e: Exception) {
                text.text = "MCP 请求失败: ${e.message}"
            }
        }
        btnCiVal.addActionListener {
            try {
                if (!mcp.isRunning()) mcp.start(project)
                val out = mcp.request("tools/call", "{\"name\":\"ci.validate\",\"arguments\":{}}", 8000)
                text.text = if (chkPretty.isSelected) prettyJson(out) else out
            } catch (e: Exception) {
                text.text = "MCP 请求失败: ${e.message}"
            }
        }
        btnHooks.addActionListener {
            try {
                if (!mcp.isRunning()) mcp.start(project)
                val out = mcp.request("tools/call", "{\"name\":\"git.install_hooks\",\"arguments\":{}}", 12000)
                text.text = prettyJson(out)
            } catch (e: Exception) {
                text.text = "MCP 请求失败: ${e.message}"
            }
        }

        btnMcpIngest.addActionListener {
            try {
                if (!mcp.isRunning()) mcp.start(project)
                val input = javax.swing.JOptionPane.showInputDialog(
                    null,
                    "输入要摄取的文件或目录（逗号分隔）",
                    "README.md, docs/"
                ) ?: return@addActionListener
                val items = input.split(',').map { it.trim() }.filter { it.isNotEmpty() }
                if (items.isEmpty()) return@addActionListener
                val pathsJson = items.joinToString(",") { "\"" + it.replace("\\", "\\\\").replace("\"", "\\\"") + "\"" }
                val params = "{\"name\":\"rules.ingest\",\"arguments\":{\"paths\":[" + pathsJson + "]}}"
                val out = mcp.request("tools/call", params, 15000)
                text.text = prettyJson(out)
            } catch (e: Exception) {
                text.text = "MCP 请求失败: ${e.message}"
            }
        }

        btnCfgYaml.addActionListener {
            try {
                if (!mcp.isRunning()) mcp.start(project)
                val resList = mcp.request("resources/list")
                val uri = extractFirstUri(resList, "config://", "/assistant.yaml")
                val out = if (uri != null) {
                    val params = "{\"uri\":\"${uri}\"}"
                    mcp.request("resources/read", params, 5000)
                } else "{\"error\":\"config resource not found\"}"
                text.text = prettyJson(out)
            } catch (e: Exception) {
                text.text = "MCP 请求失败: ${e.message}"
            }
        }

        btnCiYaml.addActionListener {
            try {
                if (!mcp.isRunning()) mcp.start(project)
                val resList = mcp.request("resources/list")
                val uri = extractFirstUri(resList, "ci://", "/workflow")
                val out = if (uri != null) {
                    val params = "{\"uri\":\"${uri}\"}"
                    mcp.request("resources/read", params, 5000)
                } else "{\"error\":\"ci workflow not found\"}"
                text.text = prettyJson(out)
            } catch (e: Exception) {
                text.text = "MCP 请求失败: ${e.message}"
            }
        }

        btnMcpCovReport.addActionListener {
            try {
                if (!mcp.isRunning()) mcp.start(project)
                val resList = mcp.request("resources/list")
                val uri = extractFirstUri(resList, "coverage://", "/report")
                val out = if (uri != null) {
                    val params = "{\"uri\":\"${uri}\"}"
                    mcp.request("resources/read", params, 8000)
                } else {
                    mcp.request("tools/call", "{\"name\":\"coverage.report\",\"arguments\":{}}", 10000)
                }
                text.text = maybePrettyAndFold(out, chkPretty.isSelected, chkFold.isSelected)
            } catch (e: Exception) {
                text.text = "MCP 请求失败: ${e.message}"
            }
        }

        fun promptFsApplyPatch(strict: Boolean, dryRun: Boolean) {
            try {
                if (!mcp.isRunning()) mcp.start(project)
                val p = javax.swing.JOptionPane.showInputDialog(
                    null,
                    if (dryRun) "受控写入（dry-run）：输入相对路径" else "受控写入（严格）：输入相对路径",
                    "mcp_rules_assistant/tmp_demo.py"
                ) ?: return
                val area = javax.swing.JTextArea(16, 64)
                val scroll = javax.swing.JScrollPane(area)
                val res = javax.swing.JOptionPane.showConfirmDialog(
                    null, scroll, "输入文件内容", javax.swing.JOptionPane.OK_CANCEL_OPTION, javax.swing.JOptionPane.PLAIN_MESSAGE
                )
                if (res != javax.swing.JOptionPane.OK_OPTION) return
                val pathEsc = p.replace("\\", "\\\\").replace("\"", "\\\"")
                val contentEsc = area.text.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n")
                val argsJson = "{\"files\":[{\"path\":\"$pathEsc\",\"content\":\"$contentEsc\"}],\"runChecks\":true,\"strict\":" + (if (strict) "true" else "false") + ",\"dryRun\":" + (if (dryRun) "true" else "false") + "}"
                val req = "{\"name\":\"fs.apply_patch\",\"arguments\":$argsJson}"
                val out = mcp.request("tools/call", req, if (dryRun) 8000 else 15000)
                text.text = out
            } catch (e: Exception) {
                text.text = "MCP 请求失败: ${e.message}"
            }
        }

        btnFsDry.addActionListener {
            try {
                val dlg = FsApplyPatchDialog(project, project.basePath?.let { java.io.File(it) })
                dlg.preset(path = "mcp_rules_assistant/tmp_demo.py", strict = true, dryRun = true)
                val params = dlg.showAndGet() ?: return@addActionListener
                if (!mcp.isRunning()) mcp.start(project)
                val pe = params.path.replace("\\", "\\\\").replace("\"", "\\\"")
                val ce = params.content.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n")
                val argsJson = "{\"files\":[{\"path\":\"$pe\",\"content\":\"$ce\"}],\"runChecks\":" + (if (params.runChecks) "true" else "false") + ",\"strict\":" + (if (params.strict) "true" else "false") + ",\"dryRun\":" + (if (params.dryRun) "true" else "false") + "}"
                val req = "{\"name\":\"fs.apply_patch\",\"arguments\":$argsJson}"
                val out = mcp.request("tools/call", req, if (params.dryRun) 8000 else 15000)
                text.text = maybePrettyAndFold(out, chkPretty.isSelected, chkFold.isSelected)
            } catch (e: Exception) {
                text.text = "MCP 请求失败: ${e.message}"
            }
        }
        btnFsWrite.addActionListener {
            try {
                val dlg = FsApplyPatchDialog(project, project.basePath?.let { java.io.File(it) })
                dlg.preset(path = "mcp_rules_assistant/tmp_demo.py", strict = true, dryRun = false)
                val params = dlg.showAndGet() ?: return@addActionListener
                if (!mcp.isRunning()) mcp.start(project)
                val pe = params.path.replace("\\", "\\\\").replace("\"", "\\\"")
                val ce = params.content.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n")
                val argsJson = "{\"files\":[{\"path\":\"$pe\",\"content\":\"$ce\"}],\"runChecks\":" + (if (params.runChecks) "true" else "false") + ",\"strict\":" + (if (params.strict) "true" else "false") + ",\"dryRun\":" + (if (params.dryRun) "true" else "false") + "}"
                val req = "{\"name\":\"fs.apply_patch\",\"arguments\":$argsJson}"
                val out = mcp.request("tools/call", req, if (params.dryRun) 8000 else 15000)
                text.text = maybePrettyAndFold(out, chkPretty.isSelected, chkFold.isSelected)
            } catch (e: Exception) {
                text.text = "MCP 请求失败: ${e.message}"
            }
        }

        fun promptFsApplyPatchMulti(strict: Boolean, dryRun: Boolean) {
            try {
                if (!mcp.isRunning()) mcp.start(project)
                val nStr = javax.swing.JOptionPane.showInputDialog(null, "输入文件数量(1-10)", "2") ?: return
                val n = nStr.toIntOrNull() ?: return
                val files = mutableListOf<Pair<String,String>>()
                val count = n.coerceIn(1, 10)
                for (i in 1..count) {
                    val p = javax.swing.JOptionPane.showInputDialog(null, "第 ${i} 个路径(相对)", "mcp_rules_assistant/tmp_${i}.py") ?: break
                    val area = javax.swing.JTextArea(10, 64)
                    val scroll2 = javax.swing.JScrollPane(area)
                    val res = javax.swing.JOptionPane.showConfirmDialog(null, scroll2, "第 ${i} 个文件内容", javax.swing.JOptionPane.OK_CANCEL_OPTION, javax.swing.JOptionPane.PLAIN_MESSAGE)
                    if (res != javax.swing.JOptionPane.OK_OPTION) break
                    files.add(Pair(p, area.text))
                }
                if (files.isEmpty()) return
                val itemsJson = files.joinToString(",") { (p, c) ->
                    val pe = p.replace("\\", "\\\\").replace("\"", "\\\"")
                    val ce = c.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n")
                    "{\"path\":\"$pe\",\"content\":\"$ce\"}"
                }
                val argsJson = "{\"files\":[" + itemsJson + "],\"runChecks\":true,\"strict\":" + (if (strict) "true" else "false") + ",\"dryRun\":" + (if (dryRun) "true" else "false") + "}"
                val req = "{\"name\":\"fs.apply_patch\",\"arguments\":$argsJson}"
                val out = mcp.request("tools/call", req, if (dryRun) 8000 else 15000)
                text.text = maybePrettyAndFold(out, chkPretty.isSelected, chkFold.isSelected)
            } catch (e: Exception) {
                text.text = "MCP 请求失败: ${e.message}"
            }
        }
        btnFsDryMulti.addActionListener { promptFsApplyPatchMulti(true, true) }
        btnFsWriteMulti.addActionListener { promptFsApplyPatchMulti(true, false) }

        panel.add(top, BorderLayout.NORTH)
        panel.add(scroll, BorderLayout.CENTER)

        // Clickable lists for weak/near (double-click to open file) — models defined earlier
        fun openFileSpec(spec: String) {
            val idx = spec.indexOf(" — ")
            val path = if (idx >= 0) spec.substring(idx + 3).trim() else spec.trim()
            openInEditor(path)
        }
        weakJList.addMouseListener(object: MouseAdapter() {
            override fun mouseClicked(e: MouseEvent) {
                if (e.clickCount == 2) {
                    val sel = weakJList.selectedValue ?: return
                    openFileSpec(sel)
                }
            }
        })
        nearJList.addMouseListener(object: MouseAdapter() {
            override fun mouseClicked(e: MouseEvent) {
                if (e.clickCount == 2) {
                    val sel = nearJList.selectedValue ?: return
                    openFileSpec(sel)
                }
            }
        })
        val bottom = JPanel(FlowLayout(FlowLayout.LEFT))
        bottom.add(JLabel("Weak:"))
        bottom.add(JScrollPane(weakJList))
        bottom.add(JLabel("Near:"))
        bottom.add(JScrollPane(nearJList))
        panel.add(bottom, BorderLayout.SOUTH)

        val content = ContentFactory.getInstance().createContent(panel, "", false)
        toolWindow.contentManager.addContent(content)
    }

    private fun extractFirstUri(json: String, prefix: String, suffix: String): String? {
        val re = "\\\"uri\\\"\\s*:\\s*\\\"([^\\\"]+)\\\"".toRegex()
        for (m in re.findAll(json)) {
            val u = m.groupValues[1]
            if (u.startsWith(prefix) && u.endsWith(suffix)) return u
        }
        return null
    }

    private fun extractString(json: String, key: String): String? {
        val re = ("\\\"" + key + "\\\"\\s*:\\s*\\\"([^\\\"]*)\\\"").toRegex()
        val m = re.find(json) ?: return null
        return m.groupValues[1]
    }

    private fun prettyJson(s: String): String {
        val t = s.trim()
        if (!(t.startsWith("{") || t.startsWith("["))) return s
        val sb = StringBuilder()
        var indent = 0
        var inStr = false
        var esc = false
        for (ch in t) {
            if (inStr) {
                sb.append(ch)
                if (esc) {
                    esc = false
                } else if (ch == '\\') {
                    esc = true
                } else if (ch == '"') {
                    inStr = false
                }
                continue
            }
            when (ch) {
                '"' -> { inStr = true; sb.append(ch) }
                '{', '[' -> { sb.append(ch).append('\n'); indent++; sb.append("  ".repeat(indent)) }
                '}', ']' -> { sb.append('\n'); indent = (indent-1).coerceAtLeast(0); sb.append("  ".repeat(indent)).append(ch) }
                ',' -> { sb.append(ch).append('\n'); sb.append("  ".repeat(indent)) }
                ':' -> { sb.append(": ") }
                else -> sb.append(ch)
            }
        }
        return sb.toString()
    }

    private fun maybePrettyAndFold(s: String, pretty: Boolean, fold: Boolean): String {
        var out = if (pretty) prettyJson(s) else s
        if (!fold) return out
        val lines = out.split('\n')
        val limit = 300
        return if (lines.size > limit) lines.take(limit).joinToString("\n") + "\n... (truncated)" else out
    }
}
