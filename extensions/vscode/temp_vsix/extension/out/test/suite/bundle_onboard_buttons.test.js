"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const assert = require("assert");
const vscode = require("vscode");
const fs = require("fs");
const path = require("path");
suite('Bundle contains onboard buttons', () => {
    test('btnOnboardPreview and btnOnboardApply in bundle', async () => {
        const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
        assert.ok(ext, 'Extension not found');
        const outJs = path.resolve(ext.extensionPath, 'out', 'extension.js');
        const js = fs.readFileSync(outJs, 'utf-8');
        assert.ok(js.includes('btnOnboardPreview'), 'Expected btnOnboardPreview in bundled JS');
        assert.ok(js.includes('btnOnboardApply'), 'Expected btnOnboardApply in bundled JS');
    });
});
//# sourceMappingURL=bundle_onboard_buttons.test.js.map