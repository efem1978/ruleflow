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
        bar.add(btnRefresh)
        bar.add(btnOpenPlan)

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

        panel.add(bar, BorderLayout.NORTH)
        panel.add(sp, BorderLayout.CENTER)

        // 初始刷新
        ta.text = readStatus()

        val content = contentFactory.createContent(panel, "", false)
        toolWindow.contentManager.addContent(content)
    }
}
