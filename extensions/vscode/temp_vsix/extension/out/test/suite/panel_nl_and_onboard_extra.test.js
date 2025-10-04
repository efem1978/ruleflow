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
suite('panel NL + onboard + license (fake)', () => {
    test('nl + licenseActivate + onboardApply + planSet paths', async () => {
        const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
        assert.ok(ext, 'Extension not found');
        await ext.activate();
        const ws = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
        assert.ok(ws, 'workspace required');
        await setFakeMode(ws);
        // Prepare temp license file
        const lic = path.join(ws, '.mcp', 'license.json');
        fs.mkdirSync(path.dirname(lic), { recursive: true });
        fs.writeFileSync(lic, JSON.stringify({ issued_to: 'CI', expires: '2099-01-01', alg: 'hs256', signature: 'deadbeef' }), 'utf-8');
        // Monkeypatch VS Code UI prompts
        const origQP = vscode.window.showQuickPick;
        const origIB = vscode.window.showInputBox;
        const origOD = vscode.window.showOpenDialog;
        // sequence for onboard: scenario -> complexity -> devMode
        const qpSeq = [
            { label: '个人 / personal', val: 'personal' },
            { label: '小 / small', val: 'small' },
            { label: 'TDD', val: 'tdd' },
        ];
        vscode.window.showQuickPick = async (items, _opts) => {
            // planSet passes an array of strings; return a valid status string then
            if (Array.isArray(items) && items.length && typeof items[0] === 'string') {
                return 'in_progress';
            }
            return qpSeq.shift() ?? { label: '个人 / personal', val: 'personal' };
        };
        const ibSeq = ['cur', 'next', '加载覆盖率'];
        vscode.window.showInputBox = async (..._args) => {
            return String(ibSeq.shift() ?? 'cur');
        };
        vscode.window.showOpenDialog = async (_opts) => {
            return [vscode.Uri.file(lic)];
        };
        try {
            await vscode.commands.executeCommand('mcpRulesAssistant.openPanel');
            await vscode.commands.executeCommand('mcpRulesAssistant._test_waitReady');
            // Activate license via panel message
            await vscode.commands.executeCommand('mcpRulesAssistant._test_sendPanelMessage', { t: 'licenseActivate' });
            // Trigger onboard apply (uses patched showQuickPick sequence)
            await vscode.commands.executeCommand('mcpRulesAssistant._test_sendPanelMessage', { t: 'onboardApply' });
            // Plan set (uses patched input boxes)
            await vscode.commands.executeCommand('mcpRulesAssistant.planSet');
            // NL command (uses patched input box to return text)
            await vscode.commands.executeCommand('mcpRulesAssistant.nlCommand');
            // Sanity: openStatus should still succeed
            await vscode.commands.executeCommand('mcpRulesAssistant.openStatus');
        }
        finally {
            // restore
            vscode.window.showQuickPick = origQP;
            vscode.window.showInputBox = origIB;
            vscode.window.showOpenDialog = origOD;
        }
    });
});
//# sourceMappingURL=panel_nl_and_onboard_extra.test.js.map