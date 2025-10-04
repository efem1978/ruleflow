"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const assert = require("assert");
const vscode = require("vscode");
const fs = require("fs");
const path = require("path");
suite.skip('Rules load with no compiled resource (fake — quarantined)', () => {
    test('loadRules when norules sentinel present', async () => {
        process.env.RULEFLOW_TEST_FAKE = '1';
        const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
        assert.ok(ext);
        await ext.activate();
        const ws = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
        assert.ok(ws);
        const sentinel = path.resolve(ws, '.mcp/dashboard/norules');
        fs.mkdirSync(path.dirname(sentinel), { recursive: true });
        fs.writeFileSync(sentinel, '1');
        await vscode.commands.executeCommand('mcpRulesAssistant.openPanel');
        await vscode.commands.executeCommand('mcpRulesAssistant._test_sendPanelMessage', { t: 'loadRules' });
        try {
            fs.unlinkSync(sentinel);
        }
        catch { }
    });
});
//# sourceMappingURL=panel_rules_norules.test.js.map