package com.ruleflow

import com.intellij.openapi.components.PersistentStateComponent
import com.intellij.openapi.components.Service
import com.intellij.openapi.components.State
import com.intellij.openapi.components.Storage
import com.intellij.openapi.components.service
import com.intellij.openapi.options.Configurable
import javax.swing.JCheckBox
import javax.swing.JComponent
import javax.swing.JLabel
import javax.swing.JPanel
import javax.swing.JTextField
import java.awt.GridBagLayout
import java.awt.GridBagConstraints
import java.awt.Insets
import java.io.File
import javax.swing.JButton
import javax.swing.JFileChooser
import com.intellij.openapi.project.ProjectManager
import com.intellij.openapi.ui.Messages

@State(name = "RuleFlowSettings", storages = [Storage("RuleFlowSettings.xml")])
@Service(Service.Level.APP)
class RuleFlowSettingsState : PersistentStateComponent<RuleFlowSettingsState> {
    var pythonBin: String = ""
    var timeoutMs: Long = 8000
    var defaultRunChecks: Boolean = true
    var defaultStrict: Boolean = true
    var defaultDryRun: Boolean = true

    override fun getState(): RuleFlowSettingsState = this
    override fun loadState(state: RuleFlowSettingsState) {
        this.pythonBin = state.pythonBin
        this.timeoutMs = state.timeoutMs
        this.defaultRunChecks = state.defaultRunChecks
        this.defaultStrict = state.defaultStrict
        this.defaultDryRun = state.defaultDryRun
    }

    companion object {
        fun getInstance(): RuleFlowSettingsState = service()
    }
}

class RuleFlowConfigurable : Configurable {
    private val panel = JPanel(GridBagLayout())
    private val tfPython = JTextField(24)
    private val tfTimeout = JTextField(10)
    private val cbRunChecks = JCheckBox("Run checks", true)
    private val cbStrict = JCheckBox("Strict", true)
    private val cbDryRun = JCheckBox("Dry-run", true)
    private val btnTest = JButton("Test Connection (ping)")

    init {
        val c = GridBagConstraints()
        c.insets = Insets(4, 4, 4, 4)
        c.anchor = GridBagConstraints.WEST
        c.gridx = 0; c.gridy = 0; panel.add(JLabel("MCP Python bin (optional)"), c)
        c.gridx = 1; panel.add(tfPython, c)
        c.gridx = 0; c.gridy = 1; panel.add(JLabel("Request timeout (ms)"), c)
        c.gridx = 1; panel.add(tfTimeout, c)
        c.gridx = 0; c.gridy = 2; panel.add(cbRunChecks, c)
        c.gridx = 1; panel.add(cbStrict, c)
        c.gridx = 2; panel.add(cbDryRun, c)
        c.gridx = 0; c.gridy = 3; panel.add(btnTest, c)
        btnTest.addActionListener {
            try {
                val prj = ProjectManager.getInstance().openProjects.firstOrNull()
                if (prj == null) {
                    Messages.showInfoMessage("No open project to run MCP.", "RuleFlow")
                    return@addActionListener
                }
                val cli = McpClient()
                cli.start(prj)
                val out = cli.request("ping", "{}", 4000)
                Messages.showInfoMessage("Ping response: $out", "RuleFlow")
                cli.stop()
            } catch (e: Exception) {
                Messages.showErrorDialog("Ping failed: ${e.message}", "RuleFlow")
            }
        }
    }

    override fun getDisplayName(): String = "RuleFlow MCP"
    override fun createComponent(): JComponent = panel

    override fun isModified(): Boolean {
        val s = RuleFlowSettingsState.getInstance()
        return tfPython.text != s.pythonBin ||
                tfTimeout.text != s.timeoutMs.toString() ||
                cbRunChecks.isSelected != s.defaultRunChecks ||
                cbStrict.isSelected != s.defaultStrict ||
                cbDryRun.isSelected != s.defaultDryRun
    }

    override fun apply() {
        val s = RuleFlowSettingsState.getInstance()
        s.pythonBin = tfPython.text.trim()
        s.timeoutMs = tfTimeout.text.trim().toLongOrNull() ?: 8000
        s.defaultRunChecks = cbRunChecks.isSelected
        s.defaultStrict = cbStrict.isSelected
        s.defaultDryRun = cbDryRun.isSelected
    }

    override fun reset() {
        val s = RuleFlowSettingsState.getInstance()
        tfPython.text = s.pythonBin
        tfTimeout.text = s.timeoutMs.toString()
        cbRunChecks.isSelected = s.defaultRunChecks
        cbStrict.isSelected = s.defaultStrict
        cbDryRun.isSelected = s.defaultDryRun
    }
}

data class FsApplyPatchParams(
    val path: String,
    val content: String,
    val runChecks: Boolean,
    val strict: Boolean,
    val dryRun: Boolean,
)

class FsApplyPatchDialog(
    private val baseDir: File? = null,
    private val defaults: RuleFlowSettingsState = RuleFlowSettingsState.getInstance()
) : javax.swing.JDialog() {
    private var ok = false
    private val tfPath = JTextField(36)
    private val taContent = javax.swing.JTextArea(12, 48)
    private val cbRunChecks = JCheckBox("Run checks", defaults.defaultRunChecks)
    private val cbStrict = JCheckBox("Strict", defaults.defaultStrict)
    private val cbDryRun = JCheckBox("Dry-run", defaults.defaultDryRun)

    init {
        title = "fs.apply_patch"
        modalityType = ModalityType.APPLICATION_MODAL
        val p = JPanel(GridBagLayout())
        val c = GridBagConstraints()
        c.insets = Insets(4, 4, 4, 4)
        c.anchor = GridBagConstraints.WEST
        c.fill = GridBagConstraints.HORIZONTAL
        c.gridx = 0; c.gridy = 0; p.add(JLabel("Path (relative)"), c)
        c.gridx = 1; p.add(tfPath, c)
        val btnBrowse = JButton("Browse…")
        c.gridx = 2; p.add(btnBrowse, c)
        c.gridx = 0; c.gridy = 1; c.gridwidth = 2
        p.add(javax.swing.JScrollPane(taContent), c)
        c.gridy = 2; c.gridwidth = 1
        p.add(cbRunChecks, c)
        c.gridx = 1; p.add(cbStrict, c)
        c.gridx = 2; p.add(cbDryRun, c)
        val btnOk = javax.swing.JButton("OK")
        val btnCancel = javax.swing.JButton("Cancel")
        val btnPanel = JPanel()
        btnPanel.add(btnOk); btnPanel.add(btnCancel)
        c.gridx = 0; c.gridy = 3; c.gridwidth = 2
        p.add(btnPanel, c)
        contentPane = p
        pack()
        setLocationRelativeTo(null)
        btnOk.addActionListener { ok = true; dispose() }
        btnCancel.addActionListener { ok = false; dispose() }

        btnBrowse.addActionListener {
            val chooser = JFileChooser()
            if (baseDir != null && baseDir.exists()) chooser.currentDirectory = baseDir
            chooser.fileSelectionMode = JFileChooser.FILES_ONLY
            val res = chooser.showOpenDialog(this)
            if (res == JFileChooser.APPROVE_OPTION) {
                val sel = chooser.selectedFile
                val path = try {
                    if (baseDir != null && sel.absolutePath.startsWith(baseDir.absolutePath))
                        baseDir.toPath().relativize(sel.toPath()).toString()
                    else sel.absolutePath
                } catch (_: Exception) { sel.path }
                tfPath.text = path.replace('\\', '/')
            }
        }
    }

    fun preset(path: String? = null, content: String? = null, strict: Boolean? = null, dryRun: Boolean? = null) {
        if (path != null) tfPath.text = path
        if (content != null) taContent.text = content
        if (strict != null) cbStrict.isSelected = strict
        if (dryRun != null) cbDryRun.isSelected = dryRun
    }

    fun showAndGet(): FsApplyPatchParams? {
        isVisible = true
        if (!ok) return null
        val p = tfPath.text.trim()
        val c = taContent.text
        if (p.isEmpty()) return null
        return FsApplyPatchParams(
            path = p,
            content = c,
            runChecks = cbRunChecks.isSelected,
            strict = cbStrict.isSelected,
            dryRun = cbDryRun.isSelected,
        )
    }
}
