"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const assert = require("assert");
const vscode = require("vscode");
const fs = require("fs");
const path = require("path");
suite('CI preview inline with no resource', () => {
    test('ciPreviewInline without ci.yml does not throw', async () => {
        process.env.RULEFLOW_TEST_FAKE = '1';
        const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
        assert.ok(ext);
        await ext.activate();
        const ws = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
        assert.ok(ws);
        const yml = path.resolve(ws, '.github/workflows/ci.yml');
        try {
            fs.unlinkSync(yml);
        }
        catch { }
        await vscode.commands.executeCommand('mcpRulesAssistant.openPanel');
        await vscode.commands.executeCommand('mcpRulesAssistant._test_sendPanelMessage', { t: 'ciPreviewInline' });
    });
});
//# sourceMappingURL=panel_ci_no_resource_inline.test.js.map