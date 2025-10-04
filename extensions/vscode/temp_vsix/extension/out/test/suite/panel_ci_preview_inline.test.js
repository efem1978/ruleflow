"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const assert = require("assert");
const vscode = require("vscode");
const fs = require("fs");
const path = require("path");
suite('Panel CI preview inline/preview (fake mode)', () => {
    test('ciPreviewInline / ciPreview run without backend', async () => {
        const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
        assert.ok(ext, 'Extension not found');
        await ext.activate();
        const ws = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
        assert.ok(ws, 'workspace required');
        const sentinel = path.resolve(ws, '.mcp/dashboard/fake_mode');
        fs.mkdirSync(path.dirname(sentinel), { recursive: true });
        fs.writeFileSync(sentinel, '1', 'utf-8');
        const yml = path.resolve(ws, '.github/workflows/ci.yml');
        if (!fs.existsSync(path.dirname(yml)))
            fs.mkdirSync(path.dirname(yml), { recursive: true });
        fs.writeFileSync(yml, 'name: CI\n', 'utf-8');
        await vscode.commands.executeCommand('mcpRulesAssistant.openPanel');
        await vscode.commands.executeCommand('mcpRulesAssistant._test_waitReady');
        await vscode.commands.executeCommand('mcpRulesAssistant._test_sendPanelMessage', { t: 'ciPreviewInline' });
        await vscode.commands.executeCommand('mcpRulesAssistant._test_waitIdle');
        await vscode.commands.executeCommand('mcpRulesAssistant._test_waitReady2', 'ciPreviewReady');
        await vscode.commands.executeCommand('mcpRulesAssistant._test_sendPanelMessage', { t: 'ciPreview' });
        await vscode.commands.executeCommand('mcpRulesAssistant._test_waitIdle');
        await vscode.commands.executeCommand('mcpRulesAssistant._test_waitReady2', 'ciPreviewReady');
    });
});
//# sourceMappingURL=panel_ci_preview_inline.test.js.map