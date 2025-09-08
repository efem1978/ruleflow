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
import javax.swing.JPanel
import javax.swing.JScrollPane
import javax.swing.JTextArea

class RuleFlowToolWindowFactory : ToolWindowFactory {
    override fun createToolWindowContent(project: Project, toolWindow: ToolWindow) {
        val contentFactory = ContentFactory.getInstance()
        val panel = JPanel(BorderLayout())
        val ta = JTextArea()
        ta.lineWrap = true
        ta.wrapStyleWord = true
        ta.isEditable = false
        val sp = JScrollPane(ta)

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
        listOf(btnRefresh, btnOpenPlan, btnStatusUpdate, btnIngest, btnCovReport, btnCovSummary, btnCiGen, btnCiValidate, btnRules, btnSugg, btnRulesSummary).forEach { bar.add(it) }

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

        fun pyBin(): String {
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

        btnRefresh.addActionListener {
            ta.text = readStatus()
        }
        btnOpenPlan.addActionListener {
            val plan = File(basePath, ".mcp/plan.md")
            if (!plan.exists()) {
                Messages.showWarningDialog(project, "未找到 .mcp/plan.md", "RuleFlow")
            } else {
                try {
                    val content = plan.readText(StandardCharsets.UTF_8)
                    ta.text = content
                } catch (e: Exception) {
                    Messages.showErrorDialog(project, "读取计划失败: ${e.message}", "RuleFlow")
                }
            }
        }

        btnStatusUpdate.addActionListener {
            ta.text = runCli("status-update")
        }
        btnIngest.addActionListener {
            val hint = Messages.showInputDialog(project, "输入要摄取的文件或目录（逗号分隔）", "规则摄取", null)
            if (hint != null && hint.trim().isNotEmpty()) {
                val parts = hint.split(',').map { it.trim() }.filter { it.isNotEmpty() }
                if (parts.isNotEmpty()) {
                    val args = ArrayList<String>()
                    args.add("ingest-rules"); args.addAll(parts)
                    ta.text = runCli(*args.toTypedArray())
                }
            }
        }
        btnCovReport.addActionListener {
            ta.text = runCli("coverage-report", "--json")
        }
        btnCiGen.addActionListener {
            ta.text = runCli("generate-ci")
        }
        btnCiValidate.addActionListener {
            ta.text = runCli("ci-validate")
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
                return sb.toString()
            } catch (e: Exception) {
                return "解析失败：${e.message}\n原始：\n$json"
            }
        }

        btnCovSummary.addActionListener {
            val raw = runCli("coverage-report", "--json")
            val json = extractFirstJsonBlock(raw) ?: raw
            ta.text = formatCoverage(json)
        }

        btnRules.addActionListener {
            val f = File(basePath, ".mcp/rules_compiled.md")
            if (!f.exists()) {
                ta.text = "未找到 .mcp/rules_compiled.md\n请先执行 摄取规则（Ingest）"
            } else {
                try { ta.text = f.readText(StandardCharsets.UTF_8) } catch (e: Exception) { ta.text = "读取失败: ${e.message}" }
            }
        }
        btnSugg.addActionListener {
            val f = File(basePath, ".mcp/rules_suggestions.md")
            if (!f.exists()) {
                ta.text = "未找到 .mcp/rules_suggestions.md\n请先执行 摄取规则（Ingest）"
            } else {
                try { ta.text = f.readText(StandardCharsets.UTF_8) } catch (e: Exception) { ta.text = "读取失败: ${e.message}" }
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
                sb.toString()
            } catch (e: Exception) {
                "解析失败: ${e.message}"
            }
        }

        btnRulesSummary.addActionListener {
            val jf = File(basePath, ".mcp/rules_compiled.json")
            val mf = File(basePath, ".mcp/rules_compiled.md")
            if (jf.exists()) {
                try {
                    val text = jf.readText(StandardCharsets.UTF_8)
                    ta.text = rulesSummaryFromJson(text)
                } catch (e: Exception) { ta.text = "读取失败: ${e.message}" }
            } else if (mf.exists()) {
                try { ta.text = mf.readText(StandardCharsets.UTF_8) } catch (e: Exception) { ta.text = "读取失败: ${e.message}" }
            } else {
                ta.text = "未找到 .mcp/rules_compiled.json/.md\n请先执行 摄取规则（Ingest）"
            }
        }

        panel.add(bar, BorderLayout.NORTH)
        panel.add(sp, BorderLayout.CENTER)

        // 初始刷新
        ta.text = readStatus()

        val content = contentFactory.createContent(panel, "", false)
        toolWindow.contentManager.addContent(content)
    }
}
