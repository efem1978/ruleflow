"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const assert = require("assert");
const vscode = require("vscode");
const fs = require("fs");
const path = require("path");
suite('Panel more message paths (fake, split)', () => {
    test('memory only', async () => {
        const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
        assert.ok(ext, 'Extension not found');
        await ext.activate();
        const ws = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
        if (ws) {
            const s = path.resolve(ws, '.mcp/dashboard/fake_mode');
            fs.mkdirSync(path.dirname(s), { recursive: true });
            fs.writeFileSync(s, '1', 'utf-8');
        }
        await vscode.commands.executeCommand('mcpRulesAssistant.openPanel');
        await vscode.commands.executeCommand('mcpRulesAssistant._test_waitReady');
        await vscode.commands.executeCommand('mcpRulesAssistant._test_sendPanelMessage', { t: 'memory' });
        await vscode.commands.executeCommand('mcpRulesAssistant._test_waitIdle');
        await vscode.commands.executeCommand('mcpRulesAssistant._test_waitReady2', 'memoryReady');
    });
    test('ciFetch/ciSave only', async () => {
        const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
        assert.ok(ext, 'Extension not found');
        await ext.activate();
        await vscode.commands.executeCommand('mcpRulesAssistant.openPanel');
        await vscode.commands.executeCommand('mcpRulesAssistant._test_waitReady');
        await vscode.commands.executeCommand('mcpRulesAssistant._test_sendPanelMessage', { t: 'ciFetch' });
        await vscode.commands.executeCommand('mcpRulesAssistant._test_waitIdle');
        await vscode.commands.executeCommand('mcpRulesAssistant._test_waitReady2', 'ciReady');
        await vscode.commands.executeCommand('mcpRulesAssistant._test_sendPanelMessage', { t: 'ciSave', data: { mutation_gate_strict: false } });
        await vscode.commands.executeCommand('mcpRulesAssistant._test_waitIdle');
    });
    test('prepare env only', async () => {
        const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
        assert.ok(ext, 'Extension not found');
        await ext.activate();
        await vscode.commands.executeCommand('mcpRulesAssistant.openPanel');
        await vscode.commands.executeCommand('mcpRulesAssistant._test_waitReady');
        await vscode.commands.executeCommand('mcpRulesAssistant._test_sendPanelMessage', { t: 'prepareEnvDry' });
        await vscode.commands.executeCommand('mcpRulesAssistant._test_waitIdle');
        await vscode.commands.executeCommand('mcpRulesAssistant._test_sendPanelMessage', { t: 'prepareEnvInstall' });
        await vscode.commands.executeCommand('mcpRulesAssistant._test_waitIdle');
    });
});
//# sourceMappingURL=panel_more_paths.test.js.map