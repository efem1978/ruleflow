"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const assert = require("assert");
const vscode = require("vscode");
suite.skip('Plan message branches (fake — quarantined for CI stability)', () => {
    test('mark in progress and done', async () => {
        process.env.RULEFLOW_TEST_FAKE = '1';
        const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
        assert.ok(ext, 'Extension not found');
        await ext.activate();
        await vscode.commands.executeCommand('mcpRulesAssistant.openPanel');
        const origPick = vscode.window.showQuickPick;
        const origInput = vscode.window.showInputBox;
        try {
            // 标记进行中 + 输入当前步骤
            vscode.window.showQuickPick = async () => '标记进行中 / In progress';
            vscode.window.showInputBox = async () => 'step-1';
            await vscode.commands.executeCommand('mcpRulesAssistant._test_sendPanelMessage', { t: 'plan' });
            // 标记完成
            vscode.window.showQuickPick = async () => '标记完成 / Done';
            await vscode.commands.executeCommand('mcpRulesAssistant._test_sendPanelMessage', { t: 'plan' });
        }
        finally {
            vscode.window.showQuickPick = origPick;
            vscode.window.showInputBox = origInput;
        }
    });
});
//# sourceMappingURL=panel_plan_branch.test.js.map