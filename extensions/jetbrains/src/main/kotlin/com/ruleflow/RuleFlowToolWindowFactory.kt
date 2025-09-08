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
        val btnCiGen = JButton("生成 CI / Generate CI")
        val btnCiValidate = JButton("校验 CI / Validate CI")
        listOf(btnRefresh, btnOpenPlan, btnStatusUpdate, btnIngest, btnCovReport, btnCiGen, btnCiValidate).forEach { bar.add(it) }

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

        panel.add(bar, BorderLayout.NORTH)
        panel.add(sp, BorderLayout.CENTER)

        // 初始刷新
        ta.text = readStatus()

        val content = contentFactory.createContent(panel, "", false)
        toolWindow.contentManager.addContent(content)
    }
}
