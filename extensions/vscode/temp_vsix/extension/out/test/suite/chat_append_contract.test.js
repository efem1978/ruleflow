"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const assert = require("assert");
const vscode = require("vscode");
const fs = require("fs");
const path = require("path");
suite('Chat append (optional) contract', () => {
    test('chatAppendSummary calls memory.append_turn when enabled (fake)', async () => {
        const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
        assert.ok(ext, 'Extension not found');
        await ext.activate();
        const ws = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
        assert.ok(ws, 'workspace required');
        // enable fake mode
        const fakeSentinel = path.resolve(ws, '.mcp/dashboard/fake_mode');
        fs.mkdirSync(path.dirname(fakeSentinel), { recursive: true });
        fs.writeFileSync(fakeSentinel, '1', 'utf-8');
        // clear previous records and enable chat
        await vscode.commands.executeCommand('mcpRulesAssistant._test_clearFakeCalls');
        await vscode.commands.executeCommand('mcpRulesAssistant._test_chatSetEnabled', true);
        // call append with a demo summary
        const ok = await vscode.commands.executeCommand('mcpRulesAssistant.chatAppendSummary', '上一轮：完成代码审查，下一步补测');
        assert.strictEqual(ok, true, 'command should resolve true');
        const calls = (await vscode.commands.executeCommand('mcpRulesAssistant._test_getFakeCalls'));
        const names = (calls || []).map((c) => c && c.name);
        assert.ok(names.includes('memory.append_turn'), 'expected memory.append_turn to be called by chat append');
        const last = (calls || []).reverse().find((c) => c && c.name === 'memory.append_turn');
        assert.ok(last && typeof last.args?.content === 'string' && /Chat/i.test(last.args.content), 'append_turn content should include Chat prefix');
    });
});
//# sourceMappingURL=chat_append_contract.test.js.map