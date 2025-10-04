"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const assert = require("assert");
const vscode = require("vscode");
suite('Extension Host Commands (Light)', () => {
    test('openPlan/openMemory do not throw when files exist or not', async () => {
        const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
        assert.ok(ext, 'Extension not found');
        await ext.activate();
        // These commands should be registered and handle missing files gracefully.
        await vscode.commands.executeCommand('mcpRulesAssistant.openPlan');
        await vscode.commands.executeCommand('mcpRulesAssistant.openMemory');
    });
});
//# sourceMappingURL=host.test.js.map