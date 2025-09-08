package com.ruleflow

import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.Messages
import com.intellij.openapi.wm.ToolWindow
import com.intellij.openapi.wm.ToolWindowFactory
import com.intellij.ui.content.ContentFactory
import java.awt.BorderLayout
import java.io.File
import java.nio.charset.StandardCharsets
import javax.swing.JButton
import javax.swing.JEditorPane
import javax.swing.JPanel
import javax.swing.JScrollPane
import javax.swing.event.HyperlinkEvent
import com.intellij.openapi.fileEditor.FileEditorManager
import com.intellij.openapi.fileEditor.OpenFileDescriptor
import com.intellij.openapi.vfs.LocalFileSystem

class RuleFlowToolWindowFactory : ToolWindowFactory {
    override fun createToolWindowContent(project: Project, toolWindow: ToolWindow) {
        val contentFactory = ContentFactory.getInstance()
        val panel = JPanel(BorderLayout())
        val viewer = JEditorPane()
        viewer.isEditable = false
        viewer.contentType = "text/html"
        viewer.addHyperlinkListener { e ->
            if (e.eventType == HyperlinkEvent.EventType.ACTIVATED) {
                try {
                    val url = e.url
                    if (url != null && url.protocol == "file") {
                        val line = try { url.ref?.removePrefix("L")?.toInt() ?: 1 } catch (ex: Exception) { 1 }
                        val p = File(basePath, url.path)
                        val vfile = LocalFileSystem.getInstance().findFileByIoFile(p)
                        if (vfile != null) {
                            OpenFileDescriptor(project, vfile, (line - 1).coerceAtLeast(0), 0).navigate(true)
                        } else {
                            Messages.showWarningDialog(project, "文件未找到: " + p.path, "RuleFlow")
                        }
                    }
                } catch (_: Exception) { }
            }
        }
        val sp = JScrollPane(viewer)

        val bar = JPanel()
        val btnRefresh = JButton("刷新 / Refresh")
        val btnOpenPlan = JButton("打开计划 / Open Plan")
        val btnStatusUpdate = JButton("写入状态 / Status Update")
        val btnIngest = JButton("摄取规则 / Ingest")
        val btnCovReport = JButton("覆盖率报告 / Coverage Report")
        val btnCovSummary = JButton("覆盖率摘要 / Coverage Summary")
        val btnCiGen = JButton("生成 CI / Generate CI")
        val btnCiValidate = JButton("校验 CI / Validate CI")
        val btnRules = JButton("规则 / Rules")
        val btnSugg = JButton("建议 / Suggestions")
        val btnRulesSummary = JButton("规则摘要 / Rules Summary")
        val btnEnvPreview = JButton("环境计划 / Env (dry-run)")
        val btnSetPy = JButton("设置 Python / Set Python")
        listOf(btnRefresh, btnOpenPlan, btnStatusUpdate, btnIngest, btnCovReport, btnCovSummary, btnCiGen, btnCiValidate, btnRules, btnSugg, btnRulesSummary, btnEnvPreview, btnSetPy).forEach { bar.add(it) }

        val basePath = project.basePath ?: ""
        fun readStatus(): String {
            if (basePath.isEmpty()) return "(no project basePath)"
            val p = File(basePath, ".mcp/dashboard/status.json")
            if (!p.exists()) return "未找到 .mcp/dashboard/status.json\n建议：运行 mcp-rules-assistant status-update 或启动 dev_agent（compose dev-agent）"
            return try {
                p.readText(StandardCharsets.UTF_8)
            } catch (e: Exception) {
                "读取失败: ${e.message}"
            }
        }

        var pyOverride: String? = null
        fun pyBin(): String {
            if (pyOverride != null && pyOverride!!.isNotEmpty()) return pyOverride!!
            val env = System.getenv("MCP_PYTHON_BIN")
            if (env != null && env.trim().isNotEmpty()) return env.trim()
            return if (System.getProperty("os.name").lowerCase().contains("win")) "python" else "python3"
        }

        fun runCli(vararg args: String): String {
            if (basePath.isEmpty()) return "(no project basePath)"
            return try {
                val cmd = ArrayList<String>()
                cmd.add(pyBin()); cmd.add("-m"); cmd.add("mcp_rules_assistant.cli")
                cmd.addAll(args.toList())
                val pb = ProcessBuilder(cmd)
                pb.directory(File(basePath))
                pb.redirectErrorStream(true)
                val p = pb.start()
                val out = p.inputStream.readAllBytes().toString(StandardCharsets.UTF_8)
                val code = p.waitFor()
                "$ ${cmd.joinToString(" ")}\n(exit $code)\n" + out
            } catch (e: Exception) {
                "执行失败: ${e.message}"
            }
        }

        fun escapeHtml(s: String): String = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        fun showPlain(text: String) { viewer.text = "<html><body style='font-family:sans-serif'><pre>" + escapeHtml(text) + "</pre></body></html>" }
        fun showHtml(html: String) { viewer.text = "<html><body style='font-family:sans-serif'>" + html + "</body></html>" }
        fun linkifyPyPaths(text: String): String {
            // 将形如 path/to/file.py 或 file.py:123 替换为可点击链接 file://path#Lline
            val esc = escapeHtml(text)
            val regex = Regex("([A-Za-z0-9_./\\\\-]+\\.py)(?::(\\d+))?")
            return regex.replace(esc) { m ->
                val path = m.groupValues[1]
                val line = m.groupValues.getOrNull(2)
                val href = if (line != null && line.isNotEmpty()) "file://$path#L$line" else "file://$path"
                "<a href='${href}'>${m.value}</a>"
            }.replace("\n", "<br/>")
        }

        fun renderMdWithToc(md: String): String {
            val lines = md.split("\n")
            val anchors = mutableListOf<Pair<String,String>>()
            val body = StringBuilder()
            var idx = 1
            for (raw in lines) {
                if (raw.startsWith("## ")) {
                    val title = raw.removePrefix("## ").trim()
                    val id = "S$idx"; idx += 1
                    anchors.add(Pair(id, title))
                    body.append("<a name='").append(id).append("'></a><b>")
                        .append(escapeHtml(title)).append("</b><br/>")
                } else {
                    body.append(linkifyPyPaths(raw))
                }
            }
            val toc = if (anchors.isNotEmpty()) {
                val b = StringBuilder()
                b.append("<div><b>目录:</b><br/>")
                anchors.forEach { p ->
                    b.append("<a href='#").append(p.first).append("'>")
                        .append(escapeHtml(p.second)).append("</a><br/>")
                }
                b.append("</div><hr/>").toString()
            } else ""
            return "<div>" + toc + body.toString() + "</div>"
        }

        btnRefresh.addActionListener { showPlain(readStatus()) }
        btnOpenPlan.addActionListener {
            val plan = File(basePath, ".mcp/plan.md")
            if (!plan.exists()) {
                Messages.showWarningDialog(project, "未找到 .mcp/plan.md", "RuleFlow")
            } else {
                try {
                    val content = plan.readText(StandardCharsets.UTF_8)
                    showPlain(content)
                } catch (e: Exception) {
                    Messages.showErrorDialog(project, "读取计划失败: ${e.message}", "RuleFlow")
                }
            }
        }

        btnStatusUpdate.addActionListener {
            showPlain(runCli("status-update"))
        }
        btnIngest.addActionListener {
            val hint = Messages.showInputDialog(project, "输入要摄取的文件或目录（逗号分隔）", "规则摄取", null)
            if (hint != null && hint.trim().isNotEmpty()) {
                val parts = hint.split(',').map { it.trim() }.filter { it.isNotEmpty() }
                if (parts.isNotEmpty()) {
                    val args = ArrayList<String>()
                    args.add("ingest-rules"); args.addAll(parts)
                    showPlain(runCli(*args.toTypedArray()))
                }
            }
        }
        btnCovReport.addActionListener {
            showPlain(runCli("coverage-report", "--json"))
        }
        btnCiGen.addActionListener {
            showPlain(runCli("generate-ci"))
        }
        btnCiValidate.addActionListener {
            showPlain(runCli("ci-validate"))
        }

        btnEnvPreview.addActionListener {
            showPlain(runCli("prepare-env"))
        }
        btnSetPy.addActionListener {
            val cur = pyOverride ?: System.getenv("MCP_PYTHON_BIN") ?: ""
            val v = Messages.showInputDialog(project, "输入 Python 解释器路径 (优先于 MCP_PYTHON_BIN)", "设置 Python", null, cur, null)
            if (v != null) {
                pyOverride = v.trim()
                Messages.showInfoMessage(project, "已设置 Python: $pyOverride", "RuleFlow")
            }
        }

        fun extractFirstJsonBlock(s: String): String? {
            val m = Regex("(?s)\\{.*?\\}").find(s)
            return m?.value
        }

        fun fmtPercent(v: Double): String {
            val p = (v * 100.0)
            return String.format("%.1f%%", p)
        }

        fun formatCoverage(json: String): String {
            // 非严格 JSON 解析：用正则提取关键字段
            try {
                val weakCount = Regex("\\\"weak\\\"\\s*:\\s*\\[(.*?)\\]", RegexOption.DOT_MATCHES_ALL)
                    .find(json)?.groupValues?.get(1)?.let { inner -> Regex("\\{", RegexOption.DOT_MATCHES_ALL).findAll(inner).count() } ?: 0
                val groups = Regex("\\{\\s*\\\"prefix\\\"\\s*:\\s*\\\"(.*?)\\\",\\s*\\\"coverage\\\"\\s*:\\s*([0-9.]+).*?\\\"threshold\\\"\\s*:\\s*([0-9.]+).*?\\\"weak_count\\\"\\s*:\\s*([0-9]+).*?\\\"files_count\\\"\\s*:\\s*([0-9]+).*?\\}", RegexOption.DOT_MATCHES_ALL)
                    .findAll(json)
                    .map { it.groupValues }
                    .map { vals ->
                        val name = vals[1]
                        val cov = vals[2].toDoubleOrNull() ?: 0.0
                        val th = vals[3].toDoubleOrNull() ?: 0.0
                        val wk = vals[4]; val fc = vals[5]
                        "- %s: %s (≥ %s) — 弱项 %s/%s".format(name, fmtPercent(cov), fmtPercent(th), wk, fc)
                    }.toList()
                val nearCount = Regex("\\\"near\\\"\\s*:\\s*\\[(.*?)\\]", RegexOption.DOT_MATCHES_ALL)
                    .find(json)?.groupValues?.get(1)?.let { inner -> Regex("\\{", RegexOption.DOT_MATCHES_ALL).findAll(inner).count() } ?: 0
                val sb = StringBuilder()
                sb.appendLine("覆盖率摘要：")
                sb.appendLine("- 弱项文件：$weakCount")
                sb.appendLine("- 近阈值：$nearCount")
                if (groups.isNotEmpty()) {
                    sb.appendLine("- 分组：")
                    groups.forEach { sb.appendLine(it) }
                }
                return escapeHtml(sb.toString()).replace("\n", "<br/>")
            } catch (e: Exception) {
                return escapeHtml("解析失败：${e.message}\n原始：\n$json").replace("\n", "<br/>")
            }
        }

        btnCovSummary.addActionListener {
            val raw = runCli("coverage-report", "--json")
            val json = extractFirstJsonBlock(raw) ?: raw
            showHtml(formatCoverage(json))
        }

        btnRules.addActionListener {
            val f = File(basePath, ".mcp/rules_compiled.md")
            if (!f.exists()) {
                showPlain("未找到 .mcp/rules_compiled.md\n请先执行 摄取规则（Ingest）")
            } else {
                try { showHtml(renderMdWithToc(f.readText(StandardCharsets.UTF_8))) } catch (e: Exception) { showPlain("读取失败: ${e.message}") }
            }
        }
        btnSugg.addActionListener {
            val f = File(basePath, ".mcp/rules_suggestions.md")
            if (!f.exists()) {
                showPlain("未找到 .mcp/rules_suggestions.md\n请先执行 摄取规则（Ingest）")
            } else {
                try { showHtml(renderMdWithToc(f.readText(StandardCharsets.UTF_8))) } catch (e: Exception) { showPlain("读取失败: ${e.message}") }
            }
        }

        fun rulesSummaryFromJson(s: String): String {
            return try {
                val minMod = Regex("\\\"coverage.min_module\\\"\\s*:\\s*([0-9.]+)").find(s)?.groupValues?.get(1)?.toDoubleOrNull() ?: 0.0
                val minCore = Regex("\\\"coverage.min_core\\\"\\s*:\\s*([0-9.]+)").find(s)?.groupValues?.get(1)?.toDoubleOrNull() ?: 0.0
                val conflictsInner = Regex("\\\"conflicts\\\"\\s*:\\s*\\[(.*?)\\]", RegexOption.DOT_MATCHES_ALL).find(s)?.groupValues?.get(1) ?: ""
                val confCount = if (conflictsInner.isNotEmpty()) Regex("\\{", RegexOption.DOT_MATCHES_ALL).findAll(conflictsInner).count() else 0
                val suggInner = Regex("\\\"suggestions\\\"\\s*:\\s*\\[(.*?)\\]", RegexOption.DOT_MATCHES_ALL).find(s)?.groupValues?.get(1) ?: ""
                val suggCount = if (suggInner.isNotEmpty()) Regex("\\{", RegexOption.DOT_MATCHES_ALL).findAll(suggInner).count() else 0
                val sb = StringBuilder()
                sb.appendLine("规则摘要：")
                sb.appendLine("- 覆盖率（模块最低）: ${fmtPercent(minMod)}")
                sb.appendLine("- 覆盖率（核心最低）: ${fmtPercent(minCore)}")
                sb.appendLine("- 冲突条目: $confCount")
                sb.appendLine("- 建议条目: $suggCount")
                // 额外：展示前 5 条冲突 (key/keep→old/new)
                val confRe = Regex("\\{.*?\\\"key\\\"\\s*:\\s*\\\"(.*?)\\\".*?\\\"keep\\\"\\s*:\\s*(.*?),.*?\\\"old\\\"\\s*:\\s*(.*?),.*?\\\"new\\\"\\s*:\\s*(.*?),.*?\\}", RegexOption.DOT_MATCHES_ALL)
                val top = confRe.findAll(s).take(5).toList()
                if (top.isNotEmpty()) {
                    sb.appendLine("- 冲突示例 (Top 5):")
                    for (m in top) {
                        val key = m.groupValues[1]
                        val keep = m.groupValues[2]
                        val oldv = m.groupValues[3]
                        val newv = m.groupValues[4]
                        sb.appendLine("  • "+key+": keep="+keep+" ; old="+oldv+" ; new="+newv)
                    }
                }
                escapeHtml(sb.toString()).replace("\n", "<br/>")
            } catch (e: Exception) {
                escapeHtml("解析失败: ${e.message}")
            }
        }

        btnRulesSummary.addActionListener {
            val jf = File(basePath, ".mcp/rules_compiled.json")
            val mf = File(basePath, ".mcp/rules_compiled.md")
            if (jf.exists()) {
                try {
                    val text = jf.readText(StandardCharsets.UTF_8)
                    showHtml(rulesSummaryFromJson(text))
                } catch (e: Exception) { ta.text = "读取失败: ${e.message}" }
            } else if (mf.exists()) {
                try { showHtml(linkifyPyPaths(mf.readText(StandardCharsets.UTF_8))) } catch (e: Exception) { showPlain("读取失败: ${e.message}") }
            } else {
                showPlain("未找到 .mcp/rules_compiled.json/.md\n请先执行 摄取规则（Ingest）")
            }
        }

        panel.add(bar, BorderLayout.NORTH)
        panel.add(sp, BorderLayout.CENTER)

        // 初始刷新
        showPlain(readStatus())

        val content = contentFactory.createContent(panel, "", false)
        toolWindow.contentManager.addContent(content)
    }
}
