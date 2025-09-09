package com.ruleflow

import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.fileEditor.FileEditorManager
import com.intellij.openapi.fileEditor.OpenFileDescriptor
import com.intellij.openapi.ui.Messages
import com.intellij.openapi.vfs.LocalFileSystem
import java.io.File

class OpenPlanAction : AnAction() {
    override fun actionPerformed(e: AnActionEvent) {
        val project = e.project
        if (project == null) {
            Messages.showWarningDialog("No project", "RuleFlow")
            return
        }
        val base = project.basePath ?: run {
            Messages.showWarningDialog(project, "Unknown base path", "RuleFlow")
            return
        }
        val f = File(base, ".mcp/plan.md")
        if (!f.exists()) {
            Messages.showInfoMessage(project, ".mcp/plan.md not found", "RuleFlow")
            return
        }
        val vfile = LocalFileSystem.getInstance().refreshAndFindFileByIoFile(f)
        if (vfile == null) {
            Messages.showWarningDialog(project, "Cannot locate VFS file", "RuleFlow")
            return
        }
        FileEditorManager.getInstance(project).openTextEditor(OpenFileDescriptor(project, vfile, 0), true)
    }
}

