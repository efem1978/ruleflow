package com.ruleflow.mcp

import com.intellij.openapi.project.Project
import com.intellij.openapi.wm.ToolWindow
import com.intellij.openapi.wm.ToolWindowFactory
import com.intellij.ui.content.ContentFactory
import java.awt.BorderLayout
import java.awt.GridLayout
import java.io.File
import javax.swing.*

class MCPToolWindowFactory : ToolWindowFactory {
    override fun createToolWindowContent(project: Project, toolWindow: ToolWindow) {
        val mcpToolWindow = MCPToolWindow(project)
        val content = ContentFactory.SERVICE.getInstance().createContent(mcpToolWindow.getContent(), "", false)
        toolWindow.contentManager.addContent(content)
    }
}

class MCPToolWindow(private val project: Project) {
    private val panel = JPanel(BorderLayout())
    
    fun getContent(): JComponent {
        setupUI()
        return panel
    }
    
    private fun setupUI() {
        // Title
        val titleLabel = JLabel("MCP Rules Assistant", SwingConstants.CENTER)
        titleLabel.font = titleLabel.font.deriveFont(16f)
        panel.add(titleLabel, BorderLayout.NORTH)
        
        // Main content
        val mainPanel = JPanel(GridLayout(0, 1, 5, 5))
        mainPanel.border = BorderFactory.createEmptyBorder(10, 10, 10, 10)
        
        // Status section
        val statusPanel = createSection("Status & Coverage")
        statusPanel.add(createButton("Status Update") { executeCommand("status-update") })
        statusPanel.add(createButton("Coverage Report") { executeCommand("coverage") })
        statusPanel.add(createButton("Coverage Groups") { executeCommand("coverage-groups") })
        mainPanel.add(statusPanel)
        
        // Rules section
        val rulesPanel = createSection("Rules Management")
        rulesPanel.add(createButton("Ingest Rules") { executeCommand("ingest-rules README.md docs/") })
        rulesPanel.add(createButton("List Rules") { executeCommand("list-rules") })
        mainPanel.add(rulesPanel)
        
        // CI/CD section
        val ciPanel = createSection("CI/CD")
        ciPanel.add(createButton("Generate CI") { executeCommand("generate-ci") })
        ciPanel.add(createButton("Install Hooks") { executeCommand("install-hooks") })
        ciPanel.add(createButton("CI Validate") { executeCommand("ci-validate") })
        mainPanel.add(ciPanel)
        
        // Memory section
        val memoryPanel = createSection("Memory & Context")
        memoryPanel.add(createButton("Memory Status") { executeCommand("memory-status") })
        memoryPanel.add(createButton("Memory Compress") { executeCommand("memory-compress") })
        mainPanel.add(memoryPanel)
        
        panel.add(JScrollPane(mainPanel), BorderLayout.CENTER)
        
        // Status bar
        val statusBar = JLabel("Ready")
        statusBar.border = BorderFactory.createEmptyBorder(5, 10, 5, 10)
        panel.add(statusBar, BorderLayout.SOUTH)
    }
    
    private fun createSection(title: String): JPanel {
        val panel = JPanel(GridLayout(0, 2, 5, 5))
        panel.border = BorderFactory.createTitledBorder(title)
        return panel
    }
    
    private fun createButton(text: String, action: () -> Unit): JButton {
        val button = JButton(text)
        button.addActionListener { action() }
        return button
    }
    
    private fun executeCommand(command: String) {
        SwingUtilities.invokeLater {
            try {
                val projectPath = project.basePath ?: return@invokeLater
                val mcpDir = File(projectPath, ".mcp")
                
                if (!mcpDir.exists()) {
                    showError("MCP project not found (.mcp directory missing)")
                    return@invokeLater
                }
                
                val pythonBin = when {
                    System.getProperty("os.name").lowercase().contains("windows") -> 
                        File(mcpDir, "venv/Scripts/python.exe")
                    else -> 
                        File(mcpDir, "venv/bin/python")
                }
                
                if (!pythonBin.exists()) {
                    showError("MCP not installed (run install script)")
                    return@invokeLater
                }
                
                val processBuilder = ProcessBuilder(
                    pythonBin.absolutePath,
                    "-m", "mcp_rules_assistant.cli",
                    *command.split(" ").toTypedArray()
                )
                processBuilder.directory(File(projectPath))
                processBuilder.redirectErrorStream(true)
                
                val process = processBuilder.start()
                val output = process.inputStream.bufferedReader().readText()
                val exitCode = process.waitFor()
                
                if (exitCode == 0) {
                    showInfo("Command completed successfully:\n$output")
                } else {
                    showError("Command failed (exit code: $exitCode):\n$output")
                }
                
            } catch (e: Exception) {
                showError("Failed to execute command: ${e.message}")
            }
        }
    }
    
    private fun showInfo(message: String) {
        JOptionPane.showMessageDialog(panel, message, "MCP Rules Assistant", JOptionPane.INFORMATION_MESSAGE)
    }
    
    private fun showError(message: String) {
        JOptionPane.showMessageDialog(panel, message, "MCP Rules Assistant - Error", JOptionPane.ERROR_MESSAGE)
    }
}
