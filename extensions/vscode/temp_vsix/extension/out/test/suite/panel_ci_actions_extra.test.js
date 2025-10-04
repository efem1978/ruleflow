"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const assert = require("assert");
const vscode = require("vscode");
const fs = require("fs");
const path = require("path");
async function setFakeMode(ws) {
    const s = path.resolve(ws, '.mcp/dashboard/fake_mode');
    fs.mkdirSync(path.dirname(s), { recursive: true });
    fs.writeFileSync(s, '1', 'utf-8');
}
suite('panel CI actions extra (fake)', () => {
    test('exercise ciGen/ciValidate/installHooks and csvPreviewPick', async () => {
        const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
        assert.ok(ext, 'Extension not found');
        await ext.activate();
        const ws = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
        assert.ok(ws, 'workspace required');
        await setFakeMode(ws);
        // Ensure dashboard directory exists
        fs.mkdirSync(path.join(ws, '.mcp/dashboard'), { recursive: true });
        // Provide minimal CSVs for preview paths
        fs.writeFileSync(path.join(ws, '.mcp/dashboard/weak_top.csv'), 'file,coverage,threshold\na.py,0.90,0.95\n', 'utf-8');
        fs.writeFileSync(path.join(ws, '.mcp/dashboard/near_top.csv'), 'file,coverage,threshold\nb.py,0.945,0.95\n', 'utf-8');
        fs.writeFileSync(path.join(ws, '.mcp/dashboard/groups.csv'), 'prefix,coverage,threshold,weak_count,files_count\nmod,0.97,0.95,0,1\n', 'utf-8');
        await vscode.commands.executeCommand('mcpRulesAssistant.openPanel');
        await vscode.commands.executeCommand('mcpRulesAssistant._test_waitReady');
        // Trigger CI actions routed via panel messages
        await vscode.commands.executeCommand('mcpRulesAssistant._test_sendPanelMessage', { t: 'ciGen' });
        await vscode.commands.executeCommand('mcpRulesAssistant._test_sendPanelMessage', { t: 'ciValidate' });
        await vscode.commands.executeCommand('mcpRulesAssistant._test_sendPanelMessage', { t: 'installHooks' });
        // Exercise CSV picker branch
        await vscode.commands.executeCommand('mcpRulesAssistant._test_sendPanelMessage', { t: 'csvPreviewPick', which: 'near_top.csv' });
        // Coverage tree/groups branches
        await vscode.commands.executeCommand('mcpRulesAssistant._test_sendPanelMessage', { t: 'coverageTree' });
        await vscode.commands.executeCommand('mcpRulesAssistant._test_sendPanelMessage', { t: 'covNear' });
        await vscode.commands.executeCommand('mcpRulesAssistant._test_sendPanelMessage', { t: 'covGroups' });
        // Verify fake calls include CI actions
        const calls = (await vscode.commands.executeCommand('mcpRulesAssistant._test_getFakeCalls'));
        const names = (calls || []).map((c) => c && c.name);
        assert.ok(names.includes('ci.generate'), 'expected ci.generate to be called');
        assert.ok(names.includes('ci.validate'), 'expected ci.validate to be called');
    });
});
//# sourceMappingURL=panel_ci_actions_extra.test.js.map