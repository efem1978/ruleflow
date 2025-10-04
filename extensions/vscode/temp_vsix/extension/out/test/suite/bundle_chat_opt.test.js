"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const assert = require("assert");
const vscode = require("vscode");
const fs = require("fs");
const path = require("path");
suite('Bundle contains Chat (optional) UI', () => {
    test('chat enable/disable/preview buttons exist', async () => {
        const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
        assert.ok(ext, 'Extension not found');
        const outJs = path.resolve(ext.extensionPath, 'out', 'extension.js');
        const js = fs.readFileSync(outJs, 'utf-8');
        assert.ok(js.includes('btnChatEnable'), 'Expected btnChatEnable');
        assert.ok(js.includes('btnChatDisable'), 'Expected btnChatDisable');
        assert.ok(js.includes('btnChatPreview'), 'Expected btnChatPreview');
    });
});
//# sourceMappingURL=bundle_chat_opt.test.js.map