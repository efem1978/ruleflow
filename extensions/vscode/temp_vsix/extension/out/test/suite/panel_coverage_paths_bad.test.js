"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const assert = require("assert");
const vscode = require("vscode");
const fs = require("fs");
const path = require("path");
// de-duplicate accidental re-imports
suite('Coverage bad/Tree no-resource (fake)', () => {
    test('coverage summary ok=false and coverageTree no resource', async () => {
        process.env.RULEFLOW_TEST_FAKE = '1';
        const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
        assert.ok(ext, 'Extension not found');
        await ext.activate();
        const ws = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
        assert.ok(ws, 'workspace required');
        const sentinel = path.resolve(ws, '.mcp/dashboard/fake_mode');
        fs.mkdirSync(path.dirname(sentinel), { recursive: true });
        fs.writeFileSync(sentinel, '1', 'utf-8');
        // sentinel: coverage_bad
        const bad = path.resolve(ws, '.mcp/dashboard/coverage_bad');
        fs.mkdirSync(path.dirname(bad), { recursive: true });
        fs.writeFileSync(bad, '1');
        await vscode.commands.executeCommand('mcpRulesAssistant.openPanel');
        await vscode.commands.executeCommand('mcpRulesAssistant._test_waitReady');
        await vscode.commands.executeCommand('mcpRulesAssistant._test_sendPanelMessage', { t: 'coverage' });
        await vscode.commands.executeCommand('mcpRulesAssistant._test_waitIdle');
        await vscode.commands.executeCommand('mcpRulesAssistant._test_waitReady2', 'covWeakReady');
        // sentinel: notree
        const nt = path.resolve(ws, '.mcp/dashboard/notree');
        fs.writeFileSync(nt, '1');
        await vscode.commands.executeCommand('mcpRulesAssistant._test_sendPanelMessage', { t: 'coverageTree' });
        await vscode.commands.executeCommand('mcpRulesAssistant._test_waitIdle');
        await vscode.commands.executeCommand('mcpRulesAssistant._test_waitReady2', 'covTreeReady');
        // clean sentinels
        try {
            fs.unlinkSync(bad);
        }
        catch { }
        try {
            fs.unlinkSync(nt);
        }
        catch { }
    });
});
//# sourceMappingURL=panel_coverage_paths_bad.test.js.map