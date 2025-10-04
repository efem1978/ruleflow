"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const assert = require("assert");
const vscode = require("vscode");
const fs = require("fs");
const path = require("path");
suite('VS Code bundle selectors (more)', () => {
    test('bundle includes CI-related selectors and handlers', async () => {
        const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
        assert.ok(ext, 'Extension not found');
        const outJs = path.resolve(ext.extensionPath, 'out', 'extension.js');
        const js = fs.readFileSync(outJs, 'utf-8');
        // Check for CI/UI elements and handlers
        assert.ok(js.includes('ciMutGateStrict'), 'Expected ciMutGateStrict checkbox');
        assert.ok(js.includes('execChecksDelegate'), 'Expected execChecksDelegate checkbox');
        assert.ok(js.includes('ciPreviewContent'), 'Expected ciPreviewContent handler');
        assert.ok(js.includes('ciChecks'), 'Expected ciChecks handler');
    });
});
//# sourceMappingURL=bundle_more_selectors.test.js.map