"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const assert = require("assert");
const vscode = require("vscode");
const fs = require("fs");
const path = require("path");
function ensureFile(p, content) {
    const dir = path.dirname(p);
    if (!fs.existsSync(dir))
        fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(p, content, 'utf-8');
}
suite('Panel dispatch common paths (fake mode, split)', () => {
    test('loadRules (compiled+json fallback)', async () => {
        const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
        assert.ok(ext);
        await ext.activate();
        const ws = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
        assert.ok(ws);
        const fs = require('fs');
        const path = require('path');
        const sentinel = path.resolve(ws, '.mcp/dashboard/fake_mode');
        fs.mkdirSync(path.dirname(sentinel), { recursive: true });
        fs.writeFileSync(sentinel, '1', 'utf-8');
        ensureFile(path.resolve(ws, '.mcp/rules_compiled.md'), '# Rules\n');
        await vscode.commands.executeCommand('mcpRulesAssistant.openPanel');
        await vscode.commands.executeCommand('mcpRulesAssistant._test_waitReady');
        await vscode.commands.executeCommand('mcpRulesAssistant._test_sendPanelMessage', { t: 'loadRules' });
        await vscode.commands.executeCommand('mcpRulesAssistant._test_waitIdle');
        await vscode.commands.executeCommand('mcpRulesAssistant._test_waitReady2', 'rulesReady');
    });
    test('coverage summary/groups/near (single message)', async () => {
        const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
        assert.ok(ext);
        await ext.activate();
        const ws = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
        assert.ok(ws);
        const fs = require('fs');
        const path = require('path');
        const sentinel = path.resolve(ws, '.mcp/dashboard/fake_mode');
        fs.mkdirSync(path.dirname(sentinel), { recursive: true });
        fs.writeFileSync(sentinel, '1', 'utf-8');
        ensureFile(path.resolve(ws, '.mcp/dashboard/weak_top.csv'), 'file,coverage,threshold,weak_count,files_count\nmod.py,0.90,0.95,1,1\n');
        await vscode.commands.executeCommand('mcpRulesAssistant.openPanel');
        await vscode.commands.executeCommand('mcpRulesAssistant._test_waitReady');
        await vscode.commands.executeCommand('mcpRulesAssistant._test_sendPanelMessage', { t: 'coverage' });
        await vscode.commands.executeCommand('mcpRulesAssistant._test_waitIdle');
        await vscode.commands.executeCommand('mcpRulesAssistant._test_waitReady2', 'covWeakReady');
    });
    test('csvPreviewPick weak_top only', async () => {
        const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
        assert.ok(ext);
        await ext.activate();
        const ws = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
        assert.ok(ws);
        const fs = require('fs');
        const path = require('path');
        const sentinel = path.resolve(ws, '.mcp/dashboard/fake_mode');
        fs.mkdirSync(path.dirname(sentinel), { recursive: true });
        fs.writeFileSync(sentinel, '1', 'utf-8');
        ensureFile(path.resolve(ws, '.mcp/dashboard/weak_top.csv'), 'file,coverage,threshold,weak_count,files_count\nmod.py,0.90,0.95,1,1\n');
        await vscode.commands.executeCommand('mcpRulesAssistant.openPanel');
        await vscode.commands.executeCommand('mcpRulesAssistant._test_waitReady');
        await vscode.commands.executeCommand('mcpRulesAssistant._test_sendPanelMessage', { t: 'csvPreviewPick', which: 'weak_top.csv' });
        await vscode.commands.executeCommand('mcpRulesAssistant._test_waitIdle');
        await vscode.commands.executeCommand('mcpRulesAssistant._test_waitReady2', 'csvPreviewReady');
    });
    test('ciCheck only', async () => {
        const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
        assert.ok(ext);
        await ext.activate();
        const ws = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
        assert.ok(ws);
        const fs = require('fs');
        const path = require('path');
        const sentinel = path.resolve(ws, '.mcp/dashboard/fake_mode');
        fs.mkdirSync(path.dirname(sentinel), { recursive: true });
        fs.writeFileSync(sentinel, '1', 'utf-8');
        ensureFile(path.resolve(ws, '.github/workflows/ci.yml'), 'name: CI\n');
        await vscode.commands.executeCommand('mcpRulesAssistant.openPanel');
        await vscode.commands.executeCommand('mcpRulesAssistant._test_waitReady');
        await vscode.commands.executeCommand('mcpRulesAssistant._test_sendPanelMessage', { t: 'ciCheck' });
        await vscode.commands.executeCommand('mcpRulesAssistant._test_waitIdle');
        await vscode.commands.executeCommand('mcpRulesAssistant._test_waitReady2', 'ciStatusReady');
    });
});
//# sourceMappingURL=panel_dispatch_paths.test.js.map