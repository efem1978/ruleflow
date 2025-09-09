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

class RuleFlowToolWindowFactory : ToolWindowFactory {
    override fun createToolWindowContent(project: Project, toolWindow: ToolWindow) {
        val panel = JPanel(BorderLayout())
        val top = JPanel(FlowLayout(FlowLayout.LEFT))
        top.add(JLabel("RuleFlow MCP (Preview) — plan/memory"))

        val btnPlan = JButton("加载计划 / Load Plan")
        val btnMemory = JButton("加载记忆 / Load Memory")
        top.add(btnPlan)
        top.add(btnMemory)

        val text = JTextArea(20, 80)
        text.isEditable = false
        val scroll = JScrollPane(text)

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

        panel.add(top, BorderLayout.NORTH)
        panel.add(scroll, BorderLayout.CENTER)

        val content = ContentFactory.getInstance().createContent(panel, "", false)
        toolWindow.contentManager.addContent(content)
    }
}
