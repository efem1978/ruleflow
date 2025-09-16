package com.ruleflow.mcp.handlers;

import java.io.BufferedReader;
import java.io.File;
import java.io.InputStreamReader;

import org.eclipse.core.commands.AbstractHandler;
import org.eclipse.core.commands.ExecutionEvent;
import org.eclipse.core.commands.ExecutionException;
import org.eclipse.core.resources.IProject;
import org.eclipse.core.resources.ResourcesPlugin;
import org.eclipse.jface.dialogs.MessageDialog;
import org.eclipse.swt.widgets.Display;
import org.eclipse.ui.handlers.HandlerUtil;

public abstract class MCPCommandHandler extends AbstractHandler {
    
    protected abstract String getCommand();
    
    @Override
    public Object execute(ExecutionEvent event) throws ExecutionException {
        try {
            IProject[] projects = ResourcesPlugin.getWorkspace().getRoot().getProjects();
            if (projects.length == 0) {
                showError("No project open");
                return null;
            }
            
            IProject project = projects[0]; // Use first project
            File projectDir = project.getLocation().toFile();
            File mcpDir = new File(projectDir, ".mcp");
            
            if (!mcpDir.exists()) {
                showError("MCP project not found (.mcp directory missing)");
                return null;
            }
            
            String os = System.getProperty("os.name").toLowerCase();
            File pythonBin;
            if (os.contains("windows")) {
                pythonBin = new File(mcpDir, "venv/Scripts/python.exe");
            } else {
                pythonBin = new File(mcpDir, "venv/bin/python");
            }
            
            if (!pythonBin.exists()) {
                showError("MCP not installed (run install script)");
                return null;
            }
            
            ProcessBuilder pb = new ProcessBuilder(
                pythonBin.getAbsolutePath(),
                "-m", "mcp_rules_assistant.cli"
            );
            
            String[] commandParts = getCommand().split(" ");
            for (String part : commandParts) {
                pb.command().add(part);
            }
            
            pb.directory(projectDir);
            pb.redirectErrorStream(true);
            
            Process process = pb.start();
            
            StringBuilder output = new StringBuilder();
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    output.append(line).append("\n");
                }
            }
            
            int exitCode = process.waitFor();
            
            if (exitCode == 0) {
                showInfo("Command completed successfully:\n" + output.toString());
            } else {
                showError("Command failed (exit code: " + exitCode + "):\n" + output.toString());
            }
            
        } catch (Exception e) {
            showError("Failed to execute command: " + e.getMessage());
        }
        
        return null;
    }
    
    private void showInfo(String message) {
        Display.getDefault().asyncExec(() -> {
            MessageDialog.openInformation(null, "MCP Rules Assistant", message);
        });
    }
    
    private void showError(String message) {
        Display.getDefault().asyncExec(() -> {
            MessageDialog.openError(null, "MCP Rules Assistant - Error", message);
        });
    }
}

// Specific command handlers
class StatusUpdateHandler extends MCPCommandHandler {
    @Override
    protected String getCommand() {
        return "status-update";
    }
}

class CoverageHandler extends MCPCommandHandler {
    @Override
    protected String getCommand() {
        return "coverage";
    }
}

class IngestRulesHandler extends MCPCommandHandler {
    @Override
    protected String getCommand() {
        return "ingest-rules README.md docs/";
    }
}

class GenerateCIHandler extends MCPCommandHandler {
    @Override
    protected String getCommand() {
        return "generate-ci";
    }
}
