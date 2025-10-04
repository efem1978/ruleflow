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
suite('memory.append_turn contract (NL routes & actions)', () => {
    test('command: loadCoverage appends a memory turn (fake)', async () => {
        const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
        assert.ok(ext, 'Extension not found');
        await ext.activate();
        const ws = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
        assert.ok(ws, 'workspace required');
        await setFakeMode(ws);
        // clear previous
        await vscode.commands.executeCommand('mcpRulesAssistant._test_clearFakeCalls');
        // run action
        await vscode.commands.executeCommand('mcpRulesAssistant.loadCoverage');
        // fetch calls
        const calls = (await vscode.commands.executeCommand('mcpRulesAssistant._test_getFakeCalls'));
        const names = (calls || []).map((c) => c && c.name);
        assert.ok(names.includes('memory.append_turn'), 'expected memory.append_turn to be called');
        const last = (calls || []).reverse().find((c) => c && c.name === 'memory.append_turn');
        assert.ok(last && last.args && typeof last.args.content === 'string', 'append_turn content missing');
        assert.ok(/Coverage loaded|Coverage not available/i.test(last.args.content), 'append_turn content should summarize coverage result');
    });
    test('panel: coverage action appends a memory turn (fake)', async () => {
        const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
        assert.ok(ext, 'Extension not found');
        await ext.activate();
        const ws = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
        assert.ok(ws, 'workspace required');
        await setFakeMode(ws);
        await vscode.commands.executeCommand('mcpRulesAssistant._test_clearFakeCalls');
        await vscode.commands.executeCommand('mcpRulesAssistant.openPanel');
        await vscode.commands.executeCommand('mcpRulesAssistant._test_waitReady');
        await vscode.commands.executeCommand('mcpRulesAssistant._test_sendPanelMessage', { t: 'coverage' });
        await vscode.commands.executeCommand('mcpRulesAssistant._test_waitIdle');
        const calls = (await vscode.commands.executeCommand('mcpRulesAssistant._test_getFakeCalls'));
        const names = (calls || []).map((c) => c && c.name);
        assert.ok(names.includes('memory.append_turn'), 'expected memory.append_turn to be called for panel coverage');
    });
});
//# sourceMappingURL=memory_append_turn_contract.test.js.map