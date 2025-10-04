"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const assert = require("assert");
const vscode = require("vscode");
suite('Webview open message edges', () => {
    test('simulate open outside workspace does not throw', async () => {
        const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
        assert.ok(ext, 'Extension not found');
        await ext.activate();
        // open test panel lite (test-only helper)
        await vscode.commands.executeCommand('mcpRulesAssistant._test_openPanelLite');
        // simulate a message that attempts to open a file outside workspace
        await vscode.commands.executeCommand('mcpRulesAssistant._test_simulateWebviewMessage', { t: 'open', path: '../README.md', line: 1 });
    });
});
//# sourceMappingURL=webview_open_edge.test.js.map