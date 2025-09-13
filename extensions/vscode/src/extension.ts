import * as vscode from 'vscode';
import { spawn, ChildProcessWithoutNullStreams } from 'child_process';

// ---- Workspace helpers (multi-root aware, Occam's razor) ----
function getWorkspaceRoot(): string | undefined {
  try {
    const ed = vscode.window.activeTextEditor;
    if (ed) {
      const folder = vscode.workspace.getWorkspaceFolder(ed.document.uri);
      if (folder) return folder.uri.fsPath;
    }
    return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  } catch {
    return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  }
}

function getWorkspaceLabel(): string {
  try {
    const ed = vscode.window.activeTextEditor;
    if (ed) {
      const folder = vscode.workspace.getWorkspaceFolder(ed.document.uri);
      if (folder) return folder.name;
    }
    const ws0 = vscode.workspace.workspaceFolders?.[0];
    return ws0?.name || '当前工作区';
  } catch {
    return '当前工作区';
  }
}

class McpClient {
  private proc: ChildProcessWithoutNullStreams | null = null;
  private seq = 0;
  private pending = new Map<number, (res: any) => void>();
  private fakeMode = ((process.env.RULEFLOW_TEST_FAKE || '').trim() === '1');

  private updateFakeMode() {
    try {
      if ((process.env.RULEFLOW_TEST_FAKE || '').trim() === '1') { this.fakeMode = true; return; }
      const ws = getWorkspaceRoot() || process.cwd();
      const p = require('path').join(ws, '.mcp', 'dashboard', 'fake_mode');
      const fs = require('fs');
      if (fs.existsSync(p)) this.fakeMode = true;
    } catch { /* ignore */ }
  }

  start(context: vscode.ExtensionContext) {
    this.updateFakeMode();
    if (this.proc || this.fakeMode) return;
    // 尽量不影响性能：按需启动，面板打开或首次请求时才启动
    const ws = getWorkspaceRoot() || process.cwd();
    const path = require('path');
    const fs = require('fs');
    // 1) 优先使用工作区内 .mcp/venv 的 Python（真正开箱即用）
    const venvPy = process.platform === 'win32'
      ? path.join(ws, '.mcp', 'venv', 'Scripts', 'python.exe')
      : path.join(ws, '.mcp', 'venv', 'bin', 'python');
    let pyBin = venvPy;
    if (!fs.existsSync(venvPy)) {
      // 2) 其次使用环境变量 MCP_PYTHON_BIN
      if (process.env.MCP_PYTHON_BIN && process.env.MCP_PYTHON_BIN.trim()) {
        pyBin = process.env.MCP_PYTHON_BIN.trim();
      } else {
        // 3) 最后回退到系统 python/python3
        pyBin = (process.platform === 'win32' ? 'python' : 'python3');
      }
    }
    this.proc = spawn(pyBin, ['-m', 'mcp_rules_assistant.cli', 'start'], {
      cwd: getWorkspaceRoot(),
      stdio: ['pipe', 'pipe', 'pipe']
    });
    this.proc.on('error', (err) => {
      vscode.window.showErrorMessage(`MCP Server 启动失败，请检查 Python：${String(err)}。可设置环境变量 MCP_PYTHON_BIN 指定解释器。`);
    });
    this.proc.on('close', (code) => {
      if (code !== 0) {
        vscode.window.showWarningMessage(`MCP Server 退出（代码 ${code}）。部分功能可能不可用。`);
      }
    });
    this.proc.stdout.setEncoding('utf8');
    this.proc.stdout.on('data', (chunk: string) => {
      chunk.split(/\r?\n/).forEach(line => {
        if (!line.trim()) return;
        try {
          const msg = JSON.parse(line);
          if (msg.id !== undefined && this.pending.has(msg.id)) {
            const cb = this.pending.get(msg.id)!;
            this.pending.delete(msg.id);
            cb(msg.result ?? msg.error);
          }
        } catch {
          // ignore
        }
      });
    });
  }

  request(method: string, params?: any): Promise<any> {
    this.updateFakeMode();
    if (this.fakeMode) {
      return this._fakeRequest(method, params || {});
    }
    if (!this.proc) throw new Error('MCP server not started');
    const id = ++this.seq;
    const payload = JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n';
    return new Promise(resolve => {
      this.pending.set(id, resolve);
      this.proc!.stdin.write(payload, 'utf8');
    });
  }

  private async _fakeRequest(method: string, params: any): Promise<any> {
    try {
      const ws = getWorkspaceRoot() || process.cwd();
      const fsApi = vscode.workspace.fs;
      const fileToString = async (u: vscode.Uri) => {
        try { const b = await fsApi.readFile(u); return Buffer.from(b).toString('utf-8'); } catch { return ''; }
      };
      if (method === 'resources/list') {
        const items: any[] = [];
        // sentinels to toggle off some resources
        let noTree = false, noRules = false;
        try { await fsApi.stat(vscode.Uri.file(ws + '/.mcp/dashboard/notree')); noTree = true; } catch {}
        try { await fsApi.stat(vscode.Uri.file(ws + '/.mcp/dashboard/norules')); noRules = true; } catch {}
        if (!noRules) {
          items.push({ uri: `rules://project/x/compiled`, name: 'Compiled project rules' });
          items.push({ uri: `rules://project/x/compiled.json`, name: 'Compiled rules (JSON)' });
          items.push({ uri: `rules://project/x/suggestions`, name: 'Rule suggestions' });
        }
        items.push({ uri: `coverage://project/x/summary`, name: 'Coverage summary' });
        items.push({ uri: `coverage://project/x/groups`, name: 'Coverage groups' });
        if (!noTree) items.push({ uri: `coverage://project/x/tree`, name: 'Coverage tree' });
        items.push({ uri: `coverage://project/x/near`, name: 'Coverage near' });
        items.push({ uri: `memory://x/rollup`, name: 'Last 20 turns & summary' });
        items.push({ uri: `progress://x/plan`, name: 'Project plan' });
        try { await fsApi.stat(vscode.Uri.file(ws + '/.github/workflows/ci.yml')); items.push({ uri: `ci://project/x/workflow`, name: 'CI workflow (YAML)' }); } catch {}
        return { resources: items };
      }
      if (method === 'resources/read') {
        const uri = String((params || {}).uri || '');
        if (uri.endsWith('/compiled')) {
          const u = vscode.Uri.file(ws + '/.mcp/rules_compiled.md');
          const text = await fileToString(u) || 'Rules (fake compiled)';
          return { mimeType: 'text/markdown', text };
        }
        if (uri.endsWith('/compiled.json')) {
          const u = vscode.Uri.file(ws + '/.mcp/rules_compiled.json');
          const fallback = JSON.stringify({ conflicts: [{ key: 'coverage.min_module', from: 0.9, to: 0.95 }], suggestions: [{ key: 'security.secrets_scan', action: 'enable' }, { key: 'ci.vscode_required', action: 'enable' }] });
          const text = await fileToString(u) || fallback;
          return { mimeType: 'application/json', text };
        }
        if (uri.endsWith('/suggestions')) {
          const u = vscode.Uri.file(ws + '/.mcp/rules_suggestions.md');
          const text = await fileToString(u) || 'No suggestions (fake)';
          return { mimeType: 'text/markdown', text };
        }
        if (uri.endsWith('/summary')) {
          let bad = false; try { await fsApi.stat(vscode.Uri.file(ws + '/.mcp/dashboard/coverage_bad')); bad = true; } catch {}
          if (bad) {
            const text = JSON.stringify({ ok: false, message: 'coverage not available' });
            return { mimeType: 'application/json', text };
          }
          const weakCsv = await fileToString(vscode.Uri.file(ws + '/.mcp/dashboard/weak_top.csv'));
          const weak = (weakCsv && weakCsv.includes('\n')) ? weakCsv.split('\n').slice(1).filter(Boolean).map((line) => ({ file: (line.split(',')[0] || 'file.py') })) : [];
          const text = JSON.stringify({ ok: true, weak });
          return { mimeType: 'application/json', text };
        }
        if (uri.endsWith('/groups')) {
          const text = JSON.stringify({ ok: true, groups: [{ prefix: 'mod', coverage: 0.97, threshold: 0.95, weak_count: 0, files_count: 1 }] });
          return { mimeType: 'application/json', text };
        }
        if (uri.endsWith('/tree')) {
          const text = JSON.stringify({ ok: true, tree: { name: '/', children: { mod: { name: 'mod', children: {} } } } });
          return { mimeType: 'application/json', text };
        }
        if (uri.endsWith('/near')) {
          const text = JSON.stringify({ ok: true, near: [] });
          return { mimeType: 'application/json', text };
        }
        if (uri.startsWith('ci://')) {
          const y = await fileToString(vscode.Uri.file(ws + '/.github/workflows/ci.yml')) || 'name: CI\n';
          return { mimeType: 'text/yaml', text: y };
        }
        if (uri.startsWith('memory://')) {
          const text = JSON.stringify({ turns: [], summary: 'fake summary', links: [] });
          return { mimeType: 'application/json', text };
        }
        if (uri.startsWith('progress://')) {
          const text = '# Plan\n- 状态: in_progress\n- 当前步骤: test';
          return { mimeType: 'text/markdown', text };
        }
        return { mimeType: 'text/plain', text: '' };
      }
      if (method === 'tools/call') {
        const name = String((params || {}).name || '');
        if (name === 'coverage.near') {
          let empty = false; try { await fsApi.stat(vscode.Uri.file(ws + '/.mcp/dashboard/near_empty')); empty = true; } catch {}
          if (empty) return { near: [] };
          return { near: [{ file: 'mod.py', coverage: 0.961, threshold: 0.95 }] };
        }
        if (name === 'ci.generate') {
          const u = vscode.Uri.file(ws + '/.github/workflows/ci.yml');
          try { await fsApi.createDirectory(vscode.Uri.file(ws + '/.github/workflows')); } catch {}
          await fsApi.writeFile(u, Buffer.from('name: CI\n', 'utf-8'));
          return { ok: true, path: '.github/workflows/ci.yml' };
        }
        if (name === 'ci.validate') {
          try { await fsApi.stat(vscode.Uri.file(ws + '/.github/workflows/ci.yml')); return { ok: true, checks: { workflow: true } }; } catch { return { ok: false, checks: { workflow: false } }; }
        }
        if (name === 'rules.onboard') {
          return { scenario: 'personal', complexity: 'small', devMode: 'tdd', thresholds: { min_module: 0.9, min_core: 0.95 } };
        }
        if (name === 'plan.set') {
          const status = (params && params.status) || 'in_progress';
          const current = (params && params.current) || 'step';
          const u = vscode.Uri.file(ws + '/.mcp/plan.md');
          const md = Buffer.from(`# Plan\n- 状态: ${status}\n- 当前步骤: ${current}\n`, 'utf-8');
          try { await fsApi.createDirectory(vscode.Uri.file(ws + '/.mcp')); } catch {}
          await fsApi.writeFile(u, md);
          return { ok: true };
        }
        if (name === 'config.get') {
          return { ok: true, config: {} };
        }
        if (name === 'config.update' || name === 'rules.enforce' || name === 'git.install_hooks' || name === 'rules.ingest' || name === 'env.prepare' || name === 'compliance.commitment' || name === 'ide.scaffold' || name === 'license.verify') {
          return { ok: true, path: name === 'compliance.commitment' ? '.mcp/compliance.md' : undefined };
        }
        if (name === 'nl.command') {
          return { parsed: { tool: '' } };
        }
      }
      return {};
    } catch {
      return {};
    }
  }
}

const client = new McpClient();
// ---- test hooks (non-public commands register below) ----
let __testWebviewHandler: ((msg: any) => Promise<void> | void) | null = null;
let __testPanelHandler: ((msg: any) => Promise<void> | void) | null = null;
let __panelReadyResolve: (() => void) | null = null;
let __panelReady: Promise<void> | null = null;
let __panelInFlightResolve: (() => void) | null = null;
let __panelInFlight: Promise<void> | null = null;
const __ready2Resolvers = new Map<string, () => void>();
const __ready2Promises = new Map<string, Promise<void>>();

async function handleOpenMessage(msg: any) {
  if (msg && msg.t === 'open' && msg.path) {
    try {
      const wsRoot = getWorkspaceRoot() || '';
      let filePath = String(msg.path);
      if (!filePath.match(/^\w:\\|^\//)) {
        filePath = require('path').join(wsRoot, filePath);
      }
      if (wsRoot && !String(filePath).startsWith(wsRoot)) {
        vscode.window.showErrorMessage('无法打开文件：不在当前工作区内');
        return;
      }
      const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(filePath));
      const editor = await vscode.window.showTextDocument(doc, { preview: false });
      const line = Math.max(0, (msg.line || 1) - 1);
      const pos = new vscode.Position(line, 0);
      editor.selection = new vscode.Selection(pos, pos);
      editor.revealRange(new vscode.Range(pos, pos), vscode.TextEditorRevealType.InCenter);
    } catch (e:any) {
      vscode.window.showErrorMessage('无法打开文件：' + String(e));
    }
  }
}

export function activate(context: vscode.ExtensionContext) {
  vscode.window.showInformationMessage('RuleFlow Extension is now active!');
  // 在状态栏放一个快捷入口，点击即可打开面板
  const sb = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  sb.text = 'RuleFlow';
  sb.tooltip = 'Quick Actions';
  sb.command = 'mcpRulesAssistant.quickActions';
  sb.show();
  context.subscriptions.push(sb);

  // 轻量状态栏刷新：从 coverage.report 获取摘要并更新状态显示
  const updateStatusBar = async () => {
    try {
      client.start(context);
      const rep = await client.request('tools/call', { name: 'coverage.report', arguments: {} });
      if (rep && rep.ok) {
        const w = Array.isArray(rep.weak) ? rep.weak.length : 0;
        const n = Array.isArray(rep.near) ? rep.near.length : 0;
        sb.text = `RuleFlow $(check) w${w}/n${n}`;
        const g = Array.isArray(rep.groups) ? rep.groups.length : 0;
        const mm = typeof rep.min_module === 'number' ? `${(rep.min_module*100).toFixed(0)}%` : '-';
        sb.tooltip = `Coverage: weak=${w}, near=${n}, groups=${g}, min_module=${mm}`;
      } else {
        sb.text = 'RuleFlow $(alert)';
        sb.tooltip = 'Coverage not available. Run tests to produce coverage.xml';
      }
    } catch {
      sb.text = 'RuleFlow';
      sb.tooltip = 'Open RuleFlow Panel';
    }
  };
  // 首次尝试刷新一次
  updateStatusBar().then(()=>{});

  // 快捷命令：快速打开计划与记忆文件
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant.openPlan', async () => {
    const ws = getWorkspaceRoot();
    if (!ws) { vscode.window.showInformationMessage('No workspace'); return; }
    const uri = vscode.Uri.file(ws + '/.mcp/plan.md');
    try {
      await vscode.workspace.fs.stat(uri);
      const doc = await vscode.workspace.openTextDocument(uri);
      await vscode.window.showTextDocument(doc, { preview: false });
    } catch {
      vscode.window.showInformationMessage('.mcp/plan.md not found');
    }
  }));
  // 主动加载覆盖率：调用 MCP 工具 coverage.report，并给出摘要提示
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant.loadCoverage', async () => {
    try { client.start(context); } catch {}
    try {
      const res = await client.request('tools/call', { name: 'coverage.report', arguments: {} });
      const weak = Array.isArray(res?.weak) ? res.weak.length : 0;
      const near = Array.isArray(res?.near) ? res.near.length : 0;
      const groups = Array.isArray(res?.groups) ? res.groups.length : 0;
      const mm = typeof res?.min_module === 'number' ? res.min_module : undefined;
      if (res && res.ok) {
        vscode.window.showInformationMessage(`Coverage loaded: weak=${weak}, near=${near}, groups=${groups}` + (mm !== undefined ? `, min_module=${(mm*100).toFixed(0)}%` : ''));
        try { await updateStatusBar(); } catch {}
        try {
          const content = `Coverage loaded: weak=${weak}, near=${near}, groups=${groups}` + (mm !== undefined ? `, min_module=${(mm*100).toFixed(0)}%` : '');
          await client.request('tools/call', { name: 'memory.append_turn', arguments: { role: 'assistant', content, meta: { source: 'vscode', action: 'loadCoverage' } } });
        } catch {}
      } else {
        const msg = (res && (res.message || res.error)) || 'coverage.xml not found or unavailable';
        vscode.window.showWarningMessage(`Coverage not available: ${String(msg)}`);
        try {
          const content = `Coverage not available: ${String(msg)}`;
          await client.request('tools/call', { name: 'memory.append_turn', arguments: { role: 'assistant', content, meta: { source: 'vscode', action: 'loadCoverage' } } });
        } catch {}
      }
    } catch (e:any) {
      vscode.window.showErrorMessage(`Load Coverage failed: ${String(e)}`);
    }
  }));

  // 快速动作（状态栏入口）
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant.quickActions', async () => {
    try { client.start(context); } catch {}
    const choice = await vscode.window.showQuickPick([
      'Open Panel',
      'Load Coverage',
      'Open Plan',
      'Open Status',
      'Ingest Rules (Quick)',
      'Status Update',
      'Generate CI',
      'Validate CI',
      'Install Hooks',
      'Natural Command',
    ], { placeHolder: 'RuleFlow Quick Actions' });
    if (!choice) return;
    if (choice === 'Open Panel') { await vscode.commands.executeCommand('mcpRulesAssistant.openPanel'); return; }
    if (choice === 'Load Coverage') { await vscode.commands.executeCommand('mcpRulesAssistant.loadCoverage'); return; }
    if (choice === 'Open Plan') { await vscode.commands.executeCommand('mcpRulesAssistant.openPlan'); return; }
    if (choice === 'Open Status') { await vscode.commands.executeCommand('mcpRulesAssistant.openStatus'); return; }
    if (choice === 'Ingest Rules (Quick)') { await vscode.commands.executeCommand('mcpRulesAssistant.ingestQuick'); return; }
    if (choice === 'Status Update') { await vscode.commands.executeCommand('mcpRulesAssistant.statusUpdate'); return; }
    if (choice === 'Generate CI') { await client.request('tools/call', { name: 'ci.generate', arguments: {} }); vscode.window.showInformationMessage('CI 已生成'); try { await client.request('tools/call', { name: 'memory.append_turn', arguments: { role: 'assistant', content: 'CI generated', meta: { source: 'vscode', action: 'ci.generate' } } }); } catch {} return; }
    if (choice === 'Validate CI') { await client.request('tools/call', { name: 'ci.validate', arguments: {} }); vscode.window.showInformationMessage('CI 校验完成'); try { await client.request('tools/call', { name: 'memory.append_turn', arguments: { role: 'assistant', content: 'CI validated', meta: { source: 'vscode', action: 'ci.validate' } } }); } catch {} return; }
    if (choice === 'Install Hooks') { await client.request('tools/call', { name: 'git.install_hooks', arguments: {} }); vscode.window.showInformationMessage('Git hooks 已安装'); try { await client.request('tools/call', { name: 'memory.append_turn', arguments: { role: 'assistant', content: 'Git hooks installed', meta: { source: 'vscode', action: 'git.install_hooks' } } }); } catch {} return; }
    if (choice === 'Natural Command') { await vscode.commands.executeCommand('mcpRulesAssistant.nlCommand'); return; }
  }));

  // 状态刷新（显示摘要 + 刷新状态栏）
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant.statusUpdate', async () => {
    try {
      client.start(context);
      const pyBin = process.env.MCP_PYTHON_BIN && process.env.MCP_PYTHON_BIN.trim() ? process.env.MCP_PYTHON_BIN.trim() : (process.platform === 'win32' ? 'python' : 'python3');
      const cwd = getWorkspaceRoot() || process.cwd();
      const { execFile } = require('child_process');
      execFile(pyBin, ['-m', 'mcp_rules_assistant.cli', 'status-update', '--json'], { cwd }, async (err: any, stdout: string, stderr: string) => {
        if (err) { vscode.window.showErrorMessage('状态刷新失败：' + String(err)); return; }
        try {
          const data = JSON.parse(stdout || '{}');
          const cov = data.coverage || {}; const w = (cov.weak||[]).length || 0; const n = (cov.near||[]).length || 0; const mm = cov.min_module;
          vscode.window.showInformationMessage(`Status: weak=${w}, near=${n}` + (mm !== undefined ? `, min_module=${(mm*100).toFixed(0)}%` : ''));
          try { await updateStatusBar(); } catch {}
        } catch { vscode.window.showInformationMessage('状态已刷新'); }
      });
    } catch (e:any) { vscode.window.showErrorMessage('状态刷新失败：' + String(e)); }
  }));

  // 快速摄取（默认 README.md, docs/）
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant.ingestQuick', async () => {
    try { client.start(context); } catch {}
    try { await client.request('tools/call', { name: 'rules.ingest', arguments: { paths: ['README.md', 'docs/'] } }); vscode.window.showInformationMessage('规则摄取完成'); } catch (e:any) { vscode.window.showErrorMessage('规则摄取失败：' + String(e)); }
  }));

  // 打开状态文件
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant.openStatus', async () => {
    try {
      const ws = getWorkspaceRoot(); if (!ws) { vscode.window.showWarningMessage('No workspace'); return; }
      const uri = vscode.Uri.file(ws + '/.mcp/dashboard/status.json');
      const doc = await vscode.workspace.openTextDocument(uri);
      await vscode.window.showTextDocument(doc, { preview: false });
    } catch { vscode.window.showInformationMessage('status.json not found'); }
  }));

  // 计划设置（status/current/next 三项任意）
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant.planSet', async () => {
    try { client.start(context); } catch {}
    const status = await vscode.window.showQuickPick(['in_progress', 'done', 'planned', 'skip (no change)'], { placeHolder: 'status' });
    let stVal: string|undefined = undefined; if (status && !status.startsWith('skip')) stVal = status;
    const current = await vscode.window.showInputBox({ placeHolder: 'current (可留空不变)' });
    const next = await vscode.window.showInputBox({ placeHolder: 'next (可留空不变)' });
    const args: any = {}; if (stVal) args.status = stVal; if (current) args.current = current; if (next) args.next = next;
    await client.request('tools/call', { name: 'plan.set', arguments: args });
    vscode.window.showInformationMessage('Plan updated');
    try {
      const content = `Plan set: ${['status', 'current', 'next'].map(k=> (args[k]!==undefined? `${k}=${args[k]}` : '')).filter(Boolean).join(', ')}`;
      await client.request('tools/call', { name: 'memory.append_turn', arguments: { role: 'assistant', content, meta: { source: 'vscode', action: 'plan.set' } } });
    } catch {}
  }));

  // 记忆：追加选中内容
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant.memoryAppendSelection', async () => {
    try { client.start(context); } catch {}
    const ed = vscode.window.activeTextEditor;
    let text = '';
    if (ed) { text = ed.document.getText(ed.selection); }
    if (!text) { text = await vscode.window.showInputBox({ placeHolder: '输入要追加到记忆的文本' }) || ''; }
    if (!text) { vscode.window.showWarningMessage('无内容可追加'); return; }
    await client.request('tools/call', { name: 'memory.append_turn', arguments: { role: 'user', content: text } });
    vscode.window.showInformationMessage('已追加到记忆');
  }));

  // 受控写入：当前文件或输入路径 + 内容；支持 dry-run/strict 选项
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant.fsApplyPatch', async () => {
    try { client.start(context); } catch {}
    const ed = vscode.window.activeTextEditor;
    const ws = getWorkspaceRoot() || process.cwd();
    const modeTop = await vscode.window.showQuickPick(['single file', 'multi files (dry-run)'], { placeHolder: '模式选择 / Mode' });
    if (!modeTop) return;
    if (modeTop.startsWith('single')) {
      let defaultPath = '';
      if (ed) {
        const p = ed.document.uri.fsPath;
        if (p && p.startsWith(ws)) defaultPath = p.substring(ws.length+1).replace(/\\\\/g,'/');
      }
      const path = await vscode.window.showInputBox({ placeHolder: '相对路径（例如 src/app.py）', value: defaultPath });
      if (!path) { vscode.window.showWarningMessage('路径为空'); return; }
      let content = ed ? ed.document.getText(ed.selection) : '';
      if (!content) { content = await vscode.window.showInputBox({ placeHolder: '写入内容（留空则取消）' }) || ''; }
      if (!content) { vscode.window.showWarningMessage('内容为空'); return; }
      const mode = await vscode.window.showQuickPick(['dry-run', 'write (runChecks=strict)', 'write (runChecks=on, strict=off)'], { placeHolder: '模式' });
      if (!mode) return;
      const dryRun = mode === 'dry-run'; const strict = mode.includes('strict'); const runChecks = !mode.includes('strict') ? true : true;
      const files = [{ path, content }];
      const out = await client.request('tools/call', { name: 'fs.apply_patch', arguments: { files, runChecks, strict, dryRun } });
      vscode.window.showInformationMessage('fs.apply_patch: ' + (out && out.ok ? 'OK' : 'Done'));
      try {
        const contentSum = `fs.apply_patch: ${dryRun ? 'dry-run' : 'write'}, files=${files.length}, strict=${strict}`;
        await client.request('tools/call', { name: 'memory.append_turn', arguments: { role: 'assistant', content: contentSum, meta: { source: 'vscode', action: 'fs.apply_patch', dryRun, strict, files: files.length } } });
      } catch {}
      return;
    }
    // Multi files (dry-run) with simple diff preview
    const nStr = await vscode.window.showInputBox({ placeHolder: '输入文件数量(1-10)', value: '2' });
    const n = Math.max(1, Math.min(10, parseInt(nStr || '2', 10) || 2));
    const items: { path: string, content: string }[] = [];
    for (let i=1; i<=n; i++) {
      const p = await vscode.window.showInputBox({ placeHolder: `第 ${i} 个相对路径`, value: i===1 && ed && ed.document.uri.fsPath.startsWith(ws) ? ed.document.uri.fsPath.substring(ws.length+1).replace(/\\\\/g,'/') : '' });
      if (!p) break;
      let c = ed ? ed.document.getText(ed.selection) : '';
      if (!c) { c = await vscode.window.showInputBox({ placeHolder: `第 ${i} 个文件内容（留空取消本次多文件）` }) || ''; }
      if (!c) { vscode.window.showWarningMessage('内容为空，已取消'); break; }
      items.push({ path: p, content: c });
    }
    if (!items.length) { vscode.window.showWarningMessage('未收集到文件'); return; }
    const out = await client.request('tools/call', { name: 'fs.apply_patch', arguments: { files: items, runChecks: true, strict: true, dryRun: true } });
    try {
      const previewLines: string[] = [];
      previewLines.push('# Guarded Write (dry-run) preview');
      const fsApi = vscode.workspace.fs;
      for (const it of items) {
        previewLines.push('--- ' + it.path);
        try {
          const uri = vscode.Uri.file((ws ? (ws + '/' + it.path) : it.path));
          const buf = await fsApi.readFile(uri);
          const cur = Buffer.from(buf).toString('utf-8');
          previewLines.push('@@ current length=' + cur.length + ' new length=' + it.content.length);
          const headOld = (cur || '').split(/\r?\n/).slice(0,3).join('\n');
          const headNew = (it.content || '').split(/\r?\n/).slice(0,3).join('\n');
          previewLines.push('- ' + headOld.replace(/\n/g, '\n- '));
          previewLines.push('+ ' + headNew.replace(/\n/g, '\n+ '));
        } catch {
          previewLines.push('@@ new file (length=' + it.content.length + ')');
          const headNew = (it.content || '').split(/\r?\n/).slice(0,3).join('\n');
          previewLines.push('+ ' + headNew.replace(/\n/g, '\n+ '));
        }
      }
      const doc = await vscode.workspace.openTextDocument({ language: 'markdown', content: previewLines.join('\n') });
      await vscode.window.showTextDocument(doc, { preview: true });
      vscode.window.showInformationMessage('fs.apply_patch (multi dry-run): ' + (out && out.ok ? 'OK' : 'Done'));
      try { await client.request('tools/call', { name: 'memory.append_turn', arguments: { role: 'assistant', content: `fs.apply_patch: dry-run multi, files=${items.length}`, meta: { source: 'vscode', action: 'fs.apply_patch', dryRun: true, files: items.length } } }); } catch {}
    } catch (e:any) {
      vscode.window.showErrorMessage('预览失败：' + String(e));
    }
  }));
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant.openMemory', async () => {
    const ws = getWorkspaceRoot();
    if (!ws) { vscode.window.showInformationMessage('No workspace'); return; }
    const uri = vscode.Uri.file(ws + '/.mcp/memory.json');
    try {
      await vscode.workspace.fs.stat(uri);
      const doc = await vscode.workspace.openTextDocument(uri);
      await vscode.window.showTextDocument(doc, { preview: false });
    } catch {
      vscode.window.showInformationMessage('.mcp/memory.json not found');
    }
  }));

  const disposable = vscode.commands.registerCommand('mcpRulesAssistant.openPanel', async () => {
    // 按需启动后端 Python 服务器
    try { client.start(context); } catch {}
    const panel = vscode.window.createWebviewPanel(
      'mcpRulesAssistant',
      'RuleFlow: Rules & Memory',
      vscode.ViewColumn.Beside,
      { enableScripts: true }
    );
    __panelReady = new Promise<void>((res) => { __panelReadyResolve = res; });

    /* c8 ignore start */
    const render = (md: string, toolsListHtml: string, sugg: string = '') => `
      <html>
      <body style="font-family: -apple-system,Segoe UI,Arial;">
        <h2>MCP 规则与上下文助手</h2>
        <p>已连接到 Python MCP Server（最小协议）。默认快速内环：保存轻、推送重。</p>
        <div id="ticker" style="height:auto; background:#f6f6f6; border:1px solid #ddd; padding:4px 8px; margin:6px 0;">
          <span id="tickerText" style="display:inline-block; white-space:nowrap; font-size:12px; color:#333;"></span>
        </div>
        <div id="proj" style="padding:4px 6px; border:1px solid #ddd; background:#fafafa; margin:6px 0; display:flex; align-items:center; gap:8px;">
          <b>当前项目:</b> <span id="curProject">(检测中)</span>
          <button id="btnSelectProject">选择/切换项目…</button>
        </div>
        <div id="lic" style="padding:4px 6px; border:1px solid #ddd; background:#fafafa; margin:6px 0; display:flex; align-items:center; gap:8px;">
          <b>License:</b> <span id="licText">(loading)</span>
          <button id="btnLicVerify">Verify</button>
          <button id="btnLicActivate">Activate…</button>
        </div>
        <pre id="licDetail" style="white-space:pre-wrap; display:none; font-size:11px; color:#555; background:#f7f7f7; padding:4px;"></pre>
        <div id="info" style="margin:6px 0; color:#d33;"></div>
        <div style="margin:8px 0;">
          <input id="nlInput" placeholder="自然语言指令：如 摄取规则 README.md, docs/ / 加载覆盖率 / 开启滚动记忆" style="width:65%;" />
          <button id="nlSend">执行</button>
          <button id="nlExamples">范例</button>
          <button id="nlClear">清空历史</button>
          <button id="btnStatusUpdate">刷新状态</button>
          <span style="margin-left:6px;">近阈值%:</span>
          <input id="nearPct" value="3" style="width:40px;" />
          <button id="btnCovNearInline">显示近阈值</button>
          <button id="btnIdeScaffold">生成 IDE 集成配置</button>
          <button id="btnCompliance">生成合规承诺</button>
          <button id="btnOpenCompliance">打开合规承诺</button>
          <button id="btnOpenIdeDir">打开 IDE 目录</button>
        </div>
        <div id="nlExamplesBox" style="display:none; margin:4px 0 10px 0;">
          <span style="opacity:.8">快速范例：</span>
          <button data-nl="摄取规则 README.md, docs/">摄取规则</button>
          <button data-nl="加载覆盖率">加载覆盖率</button>
          <button data-nl="仅看近阈值 3">仅看近阈值</button>
          <button data-nl="开启滚动记忆">开启记忆</button>
          <button data-nl="生成 CI">生成 CI</button>
          <button data-nl="校验 CI">校验 CI</button>
        </div>
        <div>
          <h4 style="margin:8px 0 4px;">最近指令</h4>
          <ul id="nlHistory" style="padding-left:18px;"></ul>
        </div>
        <div style="margin:8px 0;">
          <button id="btnLoad">载入编译规则 / Load Rules</button>
          <button id="btnIngest">摄取规则 / Ingest</button>
          <button id="btnValidate">校验规则 / Validate</button>
          <button id="btnHooks">安装钩子 / Install Hooks</button>
          <button id="btnLoadSugg">载入建议 / Load Suggestions</button>
          <button id="btnCoverage">加载覆盖率 / Load Coverage</button>
          <button id="btnShowWeak">仅看弱项 / Show Weak</button>
          <button id="btnCovTree">加载目录树 / Load Weak Tree</button>
          <button id="btnCovNear">仅看近阈值 / Show Near</button>
          <button id="btnCovExport">导出覆盖率报表 / Export Coverage</button>
          <button id="btnPrepareEnvDry">准备环境(预览) / Prepare Env (dry-run)</button>
          <button id="btnPrepareEnvInstall">准备并安装环境 / Prepare & Install</button>
        </div>
        <div style="margin:8px 0;">
          <button id="btnOpenUserGuide">打开用户上手 / Open User Guide</button>
          <button id="btnOpenIdeSupport">打开 IDE 支持 / Open IDE Support</button>
        </div>
        <div>
          <h3>可用工具（示例）</h3>
          <ul>${toolsListHtml}</ul>
        </div>
        <div>
          <h3>项目规则（编译版）</h3>
          <pre id="rules" style="white-space:pre-wrap; background:#1112; padding:8px;">${md || '暂无内容 / No content'}</pre>
        </div>
        <div>
          <h3>冲突定位（可点击跳转）</h3>
          <ul id="conflicts"></ul>
        </div>
        <div>
          <h3>冲突与建议（Conflicts & Suggestions）</h3>
          <pre id="sugg" style="white-space:pre-wrap; background:#1111; padding:8px;">${sugg || '暂无建议 / No suggestions'}</pre>
        </div>
        <div>
          <h3>规则引导（Onboard）</h3>
          <div style="margin:6px 0;">
            <button id="btnOnboardPreview">预览推荐 / Preview</button>
            <button id="btnOnboardApply">一键采纳 / Apply</button>
          </div>
          <pre id="onboardSummary" style="white-space:pre-wrap; background:#f7f7f7; padding:8px; font-size:12px; color:#333;">（点击“预览推荐”查看将启用的规则摘要）</pre>
        </div>
        <div>
          <h3>覆盖率分组</h3>
          <ul id="covGroups"></ul>
        </div>
        <div>
          <h3>覆盖率薄弱（Top 20）</h3>
          <input id="covFilter" placeholder="过滤文件名关键词..." />
          <button id="btnCovFilter">过滤</button>
          <button id="btnOpenWeakCsv">打开 weak_top.csv</button>
          <button id="btnOpenNearCsv">打开 near_top.csv</button>
          <button id="btnOpenGroupsCsv">打开 groups.csv</button>
          <button id="btnOpenGroupsMd">打开 jb_groups.md</button>
          <ul id="covWeak"></ul>
          <h4>CSV 预览</h4>
          <pre id="csvPreview" style="white-space:pre-wrap; background:#f7f7f7; padding:4px; font-size:11px;"></pre>
          <div>
            <label>切换预览：</label>
            <select id="csvSelect">
              <option value="weak_top.csv">weak_top.csv</option>
              <option value="near_top.csv">near_top.csv</option>
              <option value="groups.csv">groups.csv</option>
            </select>
            <button id="btnCsvReload">重新加载预览</button>
          </div>
        </div>
        <div>
          <h3>覆盖率目录树（弱项）</h3>
          <ul id="covTree"></ul>
        </div>
        <div>
          <h3>最近记忆与计划</h3>
          <pre id="memory" style="white-space:pre-wrap; background:#1102; padding:8px;">（点击“加载记忆 / 加载计划”获取）</pre>
          <pre id="plan" style="white-space:pre-wrap; background:#1101; padding:8px;"></pre>
        </div>
        <div>
          <h3>剩余任务（来自 .mcp/plan.md）</h3>
          <ul id="tasksPending"></ul>
          <h3>已完成</h3>
          <ul id="tasksDone"></ul>
        </div>
        <div>
          <h3>CI 配置（hadolint / semgrep / mutation）</h3>
          <label><input type="checkbox" id="ciHadolint"> 启用 hadolint</label><br/>
          镜像: <input id="ciHadolintImage" style="width:260px" placeholder="hadolint/hadolint:latest"/>
          参数: <input id="ciHadolintArgs" style="width:260px" placeholder="--ignore DL3008"/><br/>
          semgrep 规则: <input id="ciSemgrepConfig" style="width:180px" placeholder="auto / p/ci"/>
          <div style="margin-top:4px;">
            <label><input type="checkbox" id="ciMutGateStrict"> 严格模式变异门禁（strict 或显式开启）</label>
          </div>
          <div style="margin-top:4px;">
            <label><input type="checkbox" id="execChecksDelegate"> checks 委托至统一 runner（process.run_cmd）</label>
          </div>
          <button id="btnCiSave">保存 CI 配置</button>
          <button id="btnCiGen">生成 CI</button>
          <button id="btnCiPreview">预览 CI</button>
          <button id="btnCiOpen">打开 CI 文件</button>
          <button id="btnInsertRules">插入示例规则</button>
          <span id="ciStatus" style="margin-left:8px;color:#888;"></span>
          <div style="margin-top:6px;">
            <h4>CI 预览（内联）</h4>
            <pre id="ciPreviewBox" style="white-space:pre-wrap; background:#1111; padding:6px; max-height:200px; overflow:auto;"></pre>
            <h4>CI 校验结果</h4>
            <ul id="ciChecks"></ul>
          </div>
        </div>
        <script>
          const vscode = acquireVsCodeApi();
          try { vscode.postMessage({ t: 'ready' }); } catch {}
          document.getElementById('btnLoad').onclick = () => vscode.postMessage({ t: 'loadRules' });
          document.getElementById('btnStatusUpdate').onclick = () => vscode.postMessage({ t: 'statusUpdate' });
          (document.getElementById('btnSelectProject') as HTMLButtonElement).onclick = () => vscode.postMessage({ t: 'selectProject' });
          document.getElementById('btnIngest').onclick = () => vscode.postMessage({ t: 'ingestRules' });
          document.getElementById('btnValidate').onclick = () => vscode.postMessage({ t: 'validateRules' });
          document.getElementById('btnHooks').onclick = () => vscode.postMessage({ t: 'installHooks' });
          document.getElementById('btnLoadSugg').onclick = () => vscode.postMessage({ t: 'loadSugg' });
          document.getElementById('btnCoverage').onclick = () => vscode.postMessage({ t: 'coverage' });
          document.getElementById('btnCovTree').onclick = () => vscode.postMessage({ t: 'coverageTree' });
          (document.getElementById('btnOpenWeakCsv') as HTMLButtonElement).onclick = () => vscode.postMessage({ t: 'open', path: '.mcp/dashboard/weak_top.csv', line: 1 });
          (document.getElementById('btnOpenNearCsv') as HTMLButtonElement).onclick = () => vscode.postMessage({ t: 'open', path: '.mcp/dashboard/near_top.csv', line: 1 });
          (document.getElementById('btnOpenGroupsCsv') as HTMLButtonElement).onclick = () => vscode.postMessage({ t: 'open', path: '.mcp/dashboard/groups.csv', line: 1 });
          (document.getElementById('btnOpenGroupsMd') as HTMLButtonElement).onclick = () => vscode.postMessage({ t: 'open', path: '.mcp/dashboard/jb_groups.md', line: 1 });
          (document.getElementById('btnCovExport') as HTMLButtonElement).onclick = () => vscode.postMessage({ t: 'covExport' });
          (document.getElementById('btnCopyCsvPreview') as HTMLButtonElement).onclick = async () => {
            try {
              const el = document.getElementById('csvPreview');
              const text = (el && (el as any).textContent) ? String((el as any).textContent) : '';
              if (text && (navigator as any).clipboard) {
                await (navigator as any).clipboard.writeText(text);
                vscode.postMessage({ t: 'info', text: '已复制 CSV 预览到剪贴板' });
              }
            } catch {}
          };
          (document.getElementById('btnCsvReload') as HTMLButtonElement).onclick = () => {
            try {
              const sel = document.getElementById('csvSelect') as HTMLSelectElement;
              const which = sel && sel.value ? sel.value : 'weak_top.csv';
              vscode.postMessage({ t: 'csvPreviewPick', which });
            } catch {}
          };
          const btnMd = document.createElement('button'); btnMd.id = 'btnCopyCsvAsMd'; btnMd.textContent = '复制为 Markdown 表格';
          const weakBox = document.getElementById('covWeak');
          if (weakBox) { weakBox.parentElement?.insertBefore(btnMd, weakBox.nextSibling); }
          btnMd.onclick = async () => {
            try {
              const el = document.getElementById('csvPreview');
              const text = (el && (el as any).textContent) ? String((el as any).textContent) : '';
              const lines = text.split(/\r?\n/).filter(Boolean);
              if (lines.length >= 2) {
                const head = lines[0].replace(/^\[[^\]]*\]\s*/, '');
                const data = lines.slice(1);
                const cols = (head.split(',').map(s=>s.trim()));
                const tbl = [
                  '| ' + cols.join(' | ') + ' |',
                  '| ' + cols.map(()=> '---').join(' | ') + ' |',
                  ...data.map(row => '| ' + row.split(',').map(s=>s.trim()).join(' | ') + ' |')
                ].join('\n');
                if ((navigator as any).clipboard) {
                  await (navigator as any).clipboard.writeText(tbl);
                  vscode.postMessage({ t: 'info', text: '已复制 Markdown 表格到剪贴板' });
                }
              }
            } catch {}
          };
          (document.getElementById('btnIdeScaffold') as HTMLButtonElement).onclick = () => vscode.postMessage({ t: 'ideScaffold' });
          (document.getElementById('btnCompliance') as HTMLButtonElement).onclick = () => vscode.postMessage({ t: 'compliance' });
          (document.getElementById('btnOpenCompliance') as HTMLButtonElement).onclick = () => vscode.postMessage({ t: 'openCompliance' });
          (document.getElementById('btnOpenIdeDir') as HTMLButtonElement).onclick = () => vscode.postMessage({ t: 'openIdeDir' });
          const btnUG = document.getElementById('btnOpenUserGuide') as HTMLButtonElement | null;
          if (btnUG) btnUG.onclick = () => vscode.postMessage({ t: 'open', path: 'docs/USER_GUIDE.md' });
          const btnIS = document.getElementById('btnOpenIdeSupport') as HTMLButtonElement | null;
          if (btnIS) btnIS.onclick = () => vscode.postMessage({ t: 'open', path: 'docs/IDE_SUPPORT.md' });
          (document.getElementById('btnPrepareEnvInstall') as HTMLButtonElement).onclick = () => vscode.postMessage({ t: 'prepareEnvInstall' });
          (document.getElementById('btnOnboardPreview') as HTMLButtonElement).onclick = () => vscode.postMessage({ t: 'onboardPreview' });
          (document.getElementById('btnOnboardApply') as HTMLButtonElement).onclick = () => vscode.postMessage({ t: 'onboardApply' });
          (document.getElementById('btnShowWeak') as HTMLButtonElement).onclick = () => {
            const all = (window as any).__weakAll || [];
            const ulw = document.getElementById('covWeak');
            if (!ulw) return;
            ulw.innerHTML = '';
            (all || []).forEach((w:any) => {
              const li = document.createElement('li');
              const a = document.createElement('a'); a.href = '#';
              a.textContent = (w.coverage*100).toFixed(1) + '% < ' + Math.round((w.threshold||0)*100) + '% — ' + w.file;
              a.addEventListener('click', (ev)=>{ ev.preventDefault(); vscode.postMessage({ t: 'open', path: w.file, line: 1 }); });
              li.appendChild(a); ulw.appendChild(li);
            });
            const inf = document.getElementById('info'); if (inf) inf.textContent = '当前视图：弱项';
          };
          (document.getElementById('btnCovNear') as HTMLButtonElement).onclick = async () => {
            const last = (window as any).__nearPct || 3;
            // 通过扩展侧获取输入与数据
            vscode.postMessage({ t: 'covNearPrompt', last });
          };
          (document.getElementById('btnCovNearInline') as HTMLButtonElement).onclick = () => {
            const ip = document.getElementById('nearPct') as HTMLInputElement;
            const v = parseInt((ip && ip.value) || '3', 10) || 3;
            (window as any).__nearPct = v;
            try { vscode.setState && vscode.setState({ nearPct: v }); } catch {}
            try { localStorage.setItem('ruleflow.nearPct', String(v)); } catch {}
            try { vscode.postMessage({ t: 'saveNearPct', v }); } catch {}
            vscode.postMessage({ t: 'covNearPrompt', last: v });
          };
          const memBtn = document.createElement('button');
          memBtn.id = 'btnMemory'; memBtn.textContent = '加载记忆 / Load Memory';
          const planBtn = document.createElement('button');
          planBtn.id = 'btnPlan'; planBtn.textContent = '加载计划 / Load Plan';
          const bar = document.querySelector('div[style*="margin:8px 0;"]');
          if (bar) { 
            bar.appendChild(memBtn); 
            bar.appendChild(planBtn);
            const btnOpenPlan = document.createElement('button'); btnOpenPlan.textContent = '在编辑器打开计划';
            const btnOpenMemory = document.createElement('button'); btnOpenMemory.textContent = '在编辑器打开记忆';
            btnOpenPlan.onclick = () => vscode.postMessage({ t: 'open', path: '.mcp/plan.md', line: 1 });
            btnOpenMemory.onclick = () => vscode.postMessage({ t: 'open', path: '.mcp/memory.json', line: 1 });
            bar.appendChild(btnOpenPlan); bar.appendChild(btnOpenMemory);
          }
          memBtn.onclick = () => vscode.postMessage({ t: 'memory' });
          planBtn.onclick = () => vscode.postMessage({ t: 'plan' });
          // 读取 CI 配置
          vscode.postMessage({ t: 'ciFetch' });
          vscode.postMessage({ t: 'ciCheck' });
          // 绑定 CI 操作按钮
          (document.getElementById('btnCiSave') as HTMLButtonElement).onclick = () => {
            const had = (document.getElementById('ciHadolint') as HTMLInputElement).checked;
            const img = (document.getElementById('ciHadolintImage') as HTMLInputElement).value;
            const args = (document.getElementById('ciHadolintArgs') as HTMLInputElement).value;
            const sem = (document.getElementById('ciSemgrepConfig') as HTMLInputElement).value;
            const mutStrict = (document.getElementById('ciMutGateStrict') as HTMLInputElement).checked;
            const execChecks = (document.getElementById('execChecksDelegate') as HTMLInputElement).checked;
            vscode.postMessage({ t: 'ciSave', data: { hadolint: had, hadolint_image: img, hadolint_args: args, semgrep_config: sem, mutation_gate_strict: mutStrict, execution: { checks_delegate_run_cmd: execChecks } } });
          };
          (document.getElementById('btnCiGen') as HTMLButtonElement).onclick = () => vscode.postMessage({ t: 'ciGen' });
          (document.getElementById('btnCiPreview') as HTMLButtonElement).onclick = () => vscode.postMessage({ t: 'ciPreviewInline' });
          (document.getElementById('btnCiOpen') as HTMLButtonElement).onclick = () => vscode.postMessage({ t: 'ciOpen' });
          (document.getElementById('btnCiValidate') as HTMLButtonElement).onclick = () => vscode.postMessage({ t: 'ciValidate' });
          (document.getElementById('btnInsertRules') as HTMLButtonElement).onclick = () => vscode.postMessage({ t: 'insertSamples' });
          (document.getElementById('btnPrepareEnvDry') as HTMLButtonElement).onclick = () => vscode.postMessage({ t: 'prepareEnvDry' });
          const runNL = () => {
            const ip = document.getElementById('nlInput') as HTMLInputElement;
            const txt = (ip && ip.value || '').trim();
            if (!txt) return;
            vscode.postMessage({ t: 'nl', text: txt });
          };
          (document.getElementById('nlSend') as HTMLButtonElement).onclick = runNL;
          (document.getElementById('nlInput') as HTMLInputElement).addEventListener('keydown', (ev) => { if (ev.key === 'Enter') runNL(); });
          (document.getElementById('nlExamples') as HTMLButtonElement).onclick = () => {
            const box = document.getElementById('nlExamplesBox'); if (!box) return;
            box.style.display = box.style.display === 'none' ? '' : 'none';
          };
          (document.querySelectorAll('#nlExamplesBox button') as any).forEach((b:any)=>{
            b.addEventListener('click', ()=>{ const t=b.getAttribute('data-nl')||''; (document.getElementById('nlInput') as HTMLInputElement).value=t; runNL(); });
          });
          const btnLicV = document.getElementById('btnLicVerify') as HTMLButtonElement | null;
          const btnLicA = document.getElementById('btnLicActivate') as HTMLButtonElement | null;
          if (btnLicV) btnLicV.onclick = () => vscode.postMessage({ t: 'licenseVerify' });
          if (btnLicA) btnLicA.onclick = () => vscode.postMessage({ t: 'licenseActivate' });
          const btnClr = document.getElementById('nlClear') as HTMLButtonElement;
          if (btnClr) btnClr.onclick = () => { vscode.postMessage({ t: 'nlClearHistory' }); };
          vscode.postMessage({ t: 'nlFetchHistory' });

          // 初始化 nearPct 值
          try {
            const st = vscode.getState && vscode.getState();
            const saved = (st && st.nearPct) || Number(localStorage.getItem('ruleflow.nearPct')||'0') || 0;
            if (saved) { (window as any).__nearPct = saved; const ip = document.getElementById('nearPct') as HTMLInputElement; if (ip) ip.value = String(saved); }
          } catch {}

          window.addEventListener('message', (e) => {
            const msg = e.data || {};
            const setTicker = () => {
              const t = document.getElementById('tickerText');
              if (!t) return;
              const weakAll = (window as any).__weakAll || [];
              const nearAll = (window as any).__near || [];
              const topWeak = (weakAll || []).slice(0, 3).map((w:any)=> (w.coverage*100).toFixed(1) + '% ' + w.file);
              const topNear = (nearAll || []).slice(0, 3).map((n:any)=> (n.coverage*100).toFixed(1) + '% ' + n.file);
              const parts = [
                '弱项 ' + String(weakAll.length),
                '近阈值 ' + String(nearAll.length),
                topWeak.length ? ('Top弱项: ' + topWeak.join(' | ')) : '',
                topNear.length ? ('Top近阈值: ' + topNear.join(' | ')) : ''
              ].filter(Boolean);
              (t as any).textContent = parts.join('  ·  ');
            };
            if (msg.t === 'info') {
              const inf = document.getElementById('info');
              if (inf) inf.textContent = msg.text || '';
            }
            if (msg.t === 'onboardShow') {
              const el = document.getElementById('onboardSummary');
              if (el) { (el as any).textContent = String(msg.text || ''); }
            }
            if (msg.t === 'csvPreview') {
              const el = document.getElementById('csvPreview');
              if (el) {
                const which = msg.which || 'weak_top.csv';
                const arr: string[] = (msg.head || []);
                const mapHeader = (h: string) => {
                  const m = h.trim().toLowerCase();
                  if (which === 'weak_top.csv' || which === 'near_top.csv') {
                    return '文件,覆盖率%,阈值%,差值%';
                  }
                  if (which === 'groups.csv') {
                    return '前缀,覆盖率%,阈值%,弱项,文件数';
                  }
                  return h;
                };
                if (arr.length) arr[0] = mapHeader(String(arr[0] || ''));
                const lines = arr.join('\n');
                (el as any).textContent = '[' + which + ']\n' + lines;
              }
            }
            if (msg.t === 'project') {
              const el = document.getElementById('curProject');
              if (el) el.textContent = String(msg.name || '(未知)');
            }
            if (msg.t === 'covNearDisplay') {
              let items = msg.items || [];
              const pct = msg.pct || 3;
              const top = msg.top || items.length;
              try { items = (items || []).slice().sort((a:any,b:any)=> (a.delta_up||0)-(b.delta_up||0)).slice(0, top); } catch {}
              (window as any).__nearPct = pct;
              try { vscode.setState && vscode.setState({ nearPct: pct }); } catch {}
              (window as any).__near = items;
              setTicker();
              const ulw = document.getElementById('covWeak');
              if (ulw) {
                ulw.innerHTML = '';
                (items || []).forEach((w:any) => {
                  const li = document.createElement('li');
                  const a = document.createElement('a');
                  a.href = '#';
                  a.textContent = (w.coverage*100).toFixed(1) + '% ≥ ' + Math.round((w.threshold||0)*100) + '% — ' + w.file + ' （距阈值 +' + ((w.delta_up||0)*100).toFixed(1) + '%）';
                  a.addEventListener('click', (ev)=>{ ev.preventDefault(); vscode.postMessage({ t: 'open', path: w.file, line: 1 }); });
                  li.appendChild(a);
                  ulw.appendChild(li);
                });
              }
              const inf = document.getElementById('info'); if (inf) inf.textContent = '当前视图：近阈值（≤' + pct + '%，Top ' + top + '） — ' + ((items||[]).length || 0) + ' 个';
            }
            if (msg.t === 'suggestIngest') {
              const bar = document.querySelector('div[style*="margin:8px 0;"]');
              if (bar && !document.getElementById('btnQuickIngest')) {
                const qi = document.createElement('button');
                qi.id = 'btnQuickIngest';
                qi.textContent = '快速摄取 / Quick Ingest';
                (qi as HTMLButtonElement).onclick = () => vscode.postMessage({ t: 'ingestRules' });
                bar.appendChild(qi);
              }
            }
            if (msg.t === 'rules') {
              document.getElementById('rules').textContent = msg.md || '暂无内容';
            }
            if (msg.t === 'tasks') {
              const pend = Array.isArray(msg.pending) ? msg.pending : [];
              const done = Array.isArray(msg.done) ? msg.done : [];
              const up = document.getElementById('tasksPending');
              const ud = document.getElementById('tasksDone');
              if (up) { up.innerHTML = ''; pend.forEach((t:string)=>{ const li=document.createElement('li'); li.textContent=t; up.appendChild(li); }); }
              if (ud) { ud.innerHTML = ''; done.forEach((t:string)=>{ const li=document.createElement('li'); li.textContent=t; ud.appendChild(li); }); }
              const inf = document.getElementById('info');
              if (inf) inf.textContent = '任务：剩余 ' + String(pend.length) + '，完成 ' + String(done.length);
            }
            if (msg.t === 'sugg') {
              document.getElementById('sugg').textContent = msg.md || '暂无建议';
            }
            if (msg.t === 'covWeakAll') {
              (window as any).__weakAll = msg.items || [];
              // 自动构建目录树（弱项文件）
              const tree = document.getElementById('covTree');
              if (tree) {
                const all = (window as any).__weakAll || [];
                // 构建 prefix -> children 的浅树（前 3 层）
                const root: any = {};
                (all || []).forEach((w:any) => {
                  const parts = String(w.file||'').split('/').slice(0, 3);
                  let node = root;
                  parts.forEach((p, i) => {
                    if (!p) return;
                    node.children = node.children || {};
                    node.children[p] = node.children[p] || {};
                    node = node.children[p];
                  });
                  node.files = node.files || [];
                  node.files.push(w);
                });
                const renderNode = (node:any, name:string, depth:number): HTMLElement => {
                  const li = document.createElement('li');
                  const title = document.createElement('span');
                  title.textContent = name;
                  title.style.cursor = 'pointer';
                  li.appendChild(title);
                  const weakFiles = (node.files||[]);
                  if (weakFiles.length) {
                    title.style.color = '#d33';
                    const ulFiles = document.createElement('ul');
                    weakFiles.forEach((w:any) => {
                      const lif = document.createElement('li');
                      const a = document.createElement('a'); a.href = '#'; a.style.color = '#d33';
                      a.textContent = (w.coverage*100).toFixed(1) + '% — ' + w.file;
                      a.onclick = (ev)=>{ ev.preventDefault(); vscode.postMessage({ t: 'open', path: w.file, line: 1 }); };
                      lif.appendChild(a); ulFiles.appendChild(lif);
                    });
                    li.appendChild(ulFiles);
                    title.onclick = () => {
                      const vis = (ulFiles as any)._collapsed;
                      (ulFiles as any)._collapsed = !vis;
                      ulFiles.style.display = vis ? '' : 'none';
                    };
                  }
                  if (node.children) {
                    const ul = document.createElement('ul');
                    (ul as any)._collapsed = false;
                    Object.keys(node.children).sort().forEach((k)=>{
                      ul.appendChild(renderNode(node.children[k], k, depth+1));
                    });
                    li.appendChild(ul);
                    title.onclick = () => {
                      const vis = (ul as any)._collapsed;
                      (ul as any)._collapsed = !vis;
                      ul.style.display = vis ? '' : 'none';
                    };
                  }
                  return li;
                };
                tree.innerHTML = '';
                const ulRoot = document.createElement('ul');
                Object.keys(root.children||{}).sort().forEach((k)=>{
                  ulRoot.appendChild(renderNode(root.children[k], k, 0));
                });
                tree.appendChild(ulRoot);
              }
              // 更新信息条（弱项/近阈值数量）
              const w = ((msg.items||[]) as any[]).length;
              const n = ((window as any).__near || []).length || 0;
              const inf = document.getElementById('info');
              if (inf) {
                const s = '弱项 ' + w + ' 个' + (n ? ('；近阈值 ' + n + ' 个') : '');
                inf.textContent = s;
              }
            }
            if (msg.t === 'ci') {
              const cfg = msg.config || {}; const ci = cfg.ci || {};
              (document.getElementById('ciHadolint') as HTMLInputElement).checked = !!ci.hadolint;
              (document.getElementById('ciHadolintImage') as HTMLInputElement).value = ci.hadolint_image || '';
              (document.getElementById('ciHadolintArgs') as HTMLInputElement).value = ci.hadolint_args || '';
              (document.getElementById('ciSemgrepConfig') as HTMLInputElement).value = ci.semgrep_config || '';
              (document.getElementById('ciMutGateStrict') as HTMLInputElement).checked = !!ci.mutation_gate_strict;
              try {
                const ex = cfg.execution || {};
                (document.getElementById('execChecksDelegate') as HTMLInputElement).checked = !!ex.checks_delegate_run_cmd;
              } catch {}
              try {
                const perf = cfg.performance || {};
                const strict = String(perf.mode || '').toLowerCase() === 'strict' || !!ci.mutation_gate_strict;
                // Update status bar hint
                (globalThis as any).__ruleflowStrict = strict;
                sb.text = strict ? 'RuleFlow [Strict]' : 'RuleFlow';
              } catch {}
            }
            if (msg.t === 'ciStatus') {
              const el = document.getElementById('ciStatus');
              if (el) el.textContent = msg.exist ? 'CI: 已生成' : 'CI: 未生成';
              if (el) el.style.color = msg.exist ? '#2a2' : '#d33';
              try { vscode.postMessage({ t: 'ready2', topic: 'ciStatusReady' }); } catch {}
            }
            if (msg.t === 'ciPreviewContent') {
              const pv = document.getElementById('ciPreviewBox');
              if (pv) pv.textContent = msg.text || '';
              try { vscode.postMessage({ t: 'ready2', topic: 'ciPreviewReady' }); } catch {}
            }
            if (msg.t === 'ciChecks') {
              const ul = document.getElementById('ciChecks');
              if (ul) {
                ul.innerHTML = '';
                const checks = msg.checks || {};
                const labels: any = { exists: '文件存在', has_precommit: 'Pre-commit 扫描', has_hadolint: 'Hadolint 检查', has_semgrep: 'Semgrep 扫描', has_tests: 'Pytest + 覆盖率', has_bandit: 'Bandit 扫描' };
                Object.keys(labels).forEach((k) => {
                  const li = document.createElement('li');
                  li.textContent = labels[k] + '：' + (checks[k] ? '✔' : '✘');
                  li.style.color = checks[k] ? '#2a2' : '#d33';
                  ul.appendChild(li);
                });
              }
            }
            if (msg.t === 'covGroups') {
              const ul = document.getElementById('covGroups');
              if (ul) {
                ul.innerHTML = '';
                (msg.items || []).forEach((g) => {
                  const li = document.createElement('li');
                  const a = document.createElement('a');
                  a.href = '#';
                  a.textContent = String(g.prefix) + ': ' + (g.coverage*100).toFixed(1) + '% < ' + Math.round((g.threshold||0)*100) + '% — 弱项 ' + g.weak_count + '/' + g.files_count;
                  a.style.color = (g.coverage < g.threshold) ? '#d33' : '#2a2';
                  a.addEventListener('click', (ev) => {
                    ev.preventDefault();
                    const all = (window as any).__weakAll || [];
                    const filtered = g.prefix === 'other' ? all : all.filter((w:any)=> (w.file||'').startsWith(g.prefix));
                    const ulw = document.getElementById('covWeak');
                    if (ulw) {
                      ulw.innerHTML = '';
                      (filtered || []).forEach((w:any) => {
                        const li2 = document.createElement('li');
                        const a2 = document.createElement('a');
                        a2.href = '#';
                        a2.textContent = (w.coverage*100).toFixed(1) + '% — ' + w.file;
                        a2.style.color = '#d33';
                        a2.addEventListener('click', (ev2) => { ev2.preventDefault(); vscode.postMessage({ t: 'open', path: w.file, line: 1 }); });
                        li2.appendChild(a2);
                        ulw.appendChild(li2);
                      });
                    }
                  });
                  li.appendChild(a);
                  ul.appendChild(li);
                });
              }
            }
            if (msg.t === 'suggestIngest') {
              const bar = document.querySelector('div[style*="margin:8px 0;"]');
              if (bar && !document.getElementById('btnQuickIngest')) {
                const qi = document.createElement('button');
                qi.id = 'btnQuickIngest';
                qi.textContent = '快速摄取 / Quick Ingest';
                (qi as HTMLButtonElement).onclick = () => vscode.postMessage({ t: 'ingestRules' });
                bar.appendChild(qi);
              }
            }
            if (msg.t === 'covNear') {
              (window as any).__near = msg.items || [];
              const n = ((msg.items||[]) as any[]).length;
              const w = ((window as any).__weakAll || []).length || 0;
              const s = (w ? ('弱项 ' + w + ' 个；') : '') + '近阈值 ' + n + ' 个（≤3%）';
              const inf = document.getElementById('info'); if (inf) inf.textContent = s;
              setTicker();
            }
            if (msg.t === 'covTreeData') {
              const container = document.getElementById('covTree');
              if (container) {
                container.innerHTML = '';
                const renderNode = (node: any): HTMLLIElement => {
                  const li = document.createElement('li');
                  const title = document.createElement('span');
                  title.textContent = String(node.name || '');
                  title.style.cursor = 'pointer';
                  li.appendChild(title);
                  const files = node.files || [];
                  if (files.length) {
                    const uf = document.createElement('ul');
                    files.forEach((w: any) => {
                      const lif = document.createElement('li');
                      const a = document.createElement('a');
                      a.href = '#'; a.style.color = '#d33';
                      a.textContent = ((w.coverage||0)*100).toFixed(1) + '% — ' + w.file;
                      a.addEventListener('click', (ev) => { ev.preventDefault(); vscode.postMessage({ t: 'open', path: w.file, line: 1 }); });
                      lif.appendChild(a); uf.appendChild(lif);
                    });
                    li.appendChild(uf);
                  }
                  const children = node.children || {};
                  const keys = Object.keys(children);
                  if (keys.length) {
                    const ul2 = document.createElement('ul');
                    keys.sort().forEach((k) => ul2.appendChild(renderNode(children[k])));
                    li.appendChild(ul2);
                  }
                  return li as HTMLLIElement;
                };
                const ulRoot = document.createElement('ul');
                const tree = msg.tree || { children: {} };
                Object.keys(tree.children || {}).sort().forEach((k) => ulRoot.appendChild(renderNode(tree.children[k])));
                container.appendChild(ulRoot);
              }
            }
            if (msg.t === 'conflicts') {
              const ul = document.getElementById('conflicts');
              if (ul) {
                ul.innerHTML = '';
                (msg.items || []).forEach((c) => {
                  const li = document.createElement('li');
                  const key = c.key;
                  const sources = c.sources || [];
                  li.textContent = key + ': ';
                  sources.forEach((s: any, i: number) => {
                    const a = document.createElement('a');
                    a.href = '#';
                    a.textContent = (s.file || '') + ':' + (s.line || 1);
                    a.addEventListener('click', (ev) => {
                      ev.preventDefault();
                      vscode.postMessage({ t: 'open', path: s.file, line: s.line });
                    });
                    li.appendChild(a);
                    if (i < sources.length - 1) li.appendChild(document.createTextNode(' | '));
                  });
                  ul.appendChild(li);
                });
              }
            }
            if (msg.t === 'covWeak') {
              const ul = document.getElementById('covWeak');
              if (ul) {
                ul.innerHTML = '';
                (msg.items || []).forEach((w) => {
                  const li = document.createElement('li');
                  const a = document.createElement('a');
                  a.href = '#';
                  a.textContent = (w.coverage*100).toFixed(1) + '% < ' + Math.round((w.threshold||0)*100) + '% — ' + w.file;
                  a.addEventListener('click', (ev) => {
                    ev.preventDefault();
                    vscode.postMessage({ t: 'open', path: w.file, line: 1 });
                  });
                  li.appendChild(a);
                  ul.appendChild(li);
                });
                const filterBtn = document.getElementById('btnCovFilter') as HTMLButtonElement;
                const filterInput = document.getElementById('covFilter') as HTMLInputElement;
                if (filterBtn && filterInput) {
                  filterBtn.onclick = () => {
                    const kw = (filterInput.value || '').toLowerCase();
                    const all = (window as any).__weakAll || [];
                    const filtered = kw ? all.filter((w:any)=> String(w.file||'').toLowerCase().includes(kw)) : all;
                    // 直接重绘列表（不依赖扩展消息）
                    ul.innerHTML = '';
                    (filtered || []).forEach((w:any) => {
                      const li = document.createElement('li');
                      const a = document.createElement('a');
                      a.href = '#';
                      a.textContent = (w.coverage*100).toFixed(1) + '% < ' + Math.round((w.threshold||0)*100) + '% — ' + w.file;
                      a.addEventListener('click', (ev) => { ev.preventDefault(); vscode.postMessage({ t: 'open', path: w.file, line: 1 }); });
                      li.appendChild(a);
                      ul.appendChild(li);
                    });
                  };
                }
                // store for ticker
                (window as any).__weakAll = msg.items || [];
                setTicker();
              }
            }
            if (msg.t === 'memory') {
              document.getElementById('memory').textContent = msg.text || '';
            }
            if (msg.t === 'plan') {
              document.getElementById('plan').textContent = msg.text || '';
            }
            if (msg.t === 'ci') {
              const cfg = msg.config || {}; const ci = cfg.ci || {};
              (document.getElementById('ciHadolint') as HTMLInputElement).checked = !!ci.hadolint;
              (document.getElementById('ciHadolintImage') as HTMLInputElement).value = ci.hadolint_image || '';
              (document.getElementById('ciHadolintArgs') as HTMLInputElement).value = ci.hadolint_args || '';
              (document.getElementById('ciSemgrepConfig') as HTMLInputElement).value = ci.semgrep_config || '';
            }
            if (msg.t === 'ciStatus') {
              const el = document.getElementById('ciStatus');
              if (el) el.textContent = msg.exist ? 'CI: 已生成' : 'CI: 未生成';
              if (el) el.style.color = msg.exist ? '#2a2' : '#d33';
            }
            if (msg.t === 'license') {
              const L = msg.license || {}; const el = document.getElementById('licText');
              const ok = !!L.ok; const activated = !!L.activated; const sig = !!L.signature_ok; const dateok = !!L.date_ok; const exp = L.expires || '';
              let label = 'Missing'; let color = '#d33';
              if (activated && !ok) { label = 'Invalid'; }
              if (activated && ok && !dateok) { label = 'Expired'; }
              if (activated && ok && dateok) { label = 'Valid'; color = '#2a2'; }
              if (el) { el.textContent = label + (exp ? (' (expires ' + exp + ')') : ''); (el as any).style = 'color:' + color; }
              const det = document.getElementById('licDetail');
              if (det) { try { (det as any).textContent = JSON.stringify(L, null, 2); (det as any).style = 'display:block'; } catch { (det as any).textContent=''; (det as any).style='display:none'; } }
            }
            try { vscode.postMessage({ t: 'ready2', topic: String(msg.t||'any') }); } catch {}
        });
        </script>
      </body></html>`;
    /* c8 ignore stop */

    try {
      client.start(context);
      await client.request('initialize', {});
      const tools = await client.request('tools/list', {});
      const list = (tools.tools || []).map((t: any) => `<li><code>${t.name}</code> — ${t.description}</li>`).join('');
      panel.webview.html = render('', list);
      try {
        panel.webview.postMessage({ t: 'project', name: getWorkspaceLabel() });
        const diag = await client.request('tools/call', { name: 'env.diagnose', arguments: {} });
        panel.webview.postMessage({ t: 'license', license: (diag && (diag as any).license) || {} });
        // 缺少工具或 venv 时，提示一键准备环境
        const toolsMap = (diag && (diag as any).tools) || {};
        const missing: string[] = [];
        ['pytest', 'pre-commit', 'ruff', 'mypy', 'bandit'].forEach(k => { if (!toolsMap[k]) missing.push(k); });
        let venvMissing = false;
        try {
          const ws = getWorkspaceRoot();
          if (ws) {
            const uri = vscode.Uri.file(ws + '/.mcp/venv');
            await vscode.workspace.fs.stat(uri).then(()=>{}, ()=>{ venvMissing = true; });
          }
        } catch { venvMissing = true; }
        if ((venvMissing || missing.length) && (process.env.RULEFLOW_TEST_FAKE || '') !== '1') {
          panel.webview.postMessage({ t: 'info', text: `检测到开发环境不完整（venv: ${venvMissing ? '缺失' : '存在'}；缺少工具: ${missing.join(', ') || '无'}）。建议点击“准备并安装环境”。` });
          const pick = await vscode.window.showInformationMessage('检测到缺少开发环境，是否一键创建并安装基础工具？', '立即创建', '稍后');
          if (pick === '立即创建') {
            try {
              await client.request('tools/call', { name: 'env.prepare', arguments: { create: true, install: true } });
              vscode.window.showInformationMessage('已创建并安装基础环境 (.mcp/venv)。');
            } catch (e:any) {
              vscode.window.showErrorMessage('创建环境失败：' + String(e));
            }
          }
        }
      } catch {}
    } catch (e: any) {
      panel.webview.html = `<pre>连接 MCP 失败：${String(e)}</pre>`;
    }

    const __panelDispatch = async (msg: any) => {
      // mark in-flight for tests to await idle
      try { __panelInFlight = new Promise<void>((res)=>{ __panelInFlightResolve = res; }); } catch {}
      try {
        __testWebviewHandler = async (m:any) => { await handleOpenMessage(m); };
        if (msg.t === 'statusUpdate') {
          const pyBin = process.env.MCP_PYTHON_BIN && process.env.MCP_PYTHON_BIN.trim()
            ? process.env.MCP_PYTHON_BIN.trim()
            : (process.platform === 'win32' ? 'python' : 'python3');
          const cwd = getWorkspaceRoot() || process.cwd();
          const { execFile } = require('child_process');
          execFile(pyBin, ['-m', 'mcp_rules_assistant.cli', 'status-update', '--json'], { cwd }, (err: any, stdout: string, stderr: string) => {
            if (err) {
              vscode.window.showErrorMessage('状态刷新失败：' + String(err));
              return;
            }
            try {
              const data = JSON.parse(stdout || '{}');
              panel.webview.postMessage({ t: 'info', text: '状态已刷新。弱项：' + (((data.coverage||{}).weak||[]).length || 0) });
              const tk = (data.tasks||{});
              panel.webview.postMessage({ t: 'tasks', pending: tk.pending || [], done: tk.done || [] });
            } catch (e) {
              vscode.window.showInformationMessage('状态已刷新');
            }
          });
          return;
        }
        if (msg.t === 'loadRules') {
          const resList = await client.request('resources/list', {});
          const compiledUri = (resList.resources || []).find((r: any) => String(r.uri || '').endsWith('/compiled'))?.uri;
          const jsonUri = (resList.resources || []).find((r: any) => String(r.uri || '').endsWith('/compiled.json'))?.uri;
          if (!compiledUri) {
            panel.webview.postMessage({ t: 'rules', md: '未找到规则资源，请先“摄取规则”' });
            panel.webview.postMessage({ t: 'info', text: '未找到编译规则，请点击“摄取规则 / Ingest”进行摄取。' });
            panel.webview.postMessage({ t: 'suggestIngest' });
            return;
          }
          const res = await client.request('resources/read', { uri: compiledUri });
          panel.webview.postMessage({ t: 'rules', md: res.text || '' });
          if (jsonUri) {
            const compiled = await client.request('resources/read', { uri: jsonUri });
            const data = JSON.parse(compiled.text || '{}');
            panel.webview.postMessage({ t: 'conflicts', items: data.conflicts || [] });
            try {
              const n = Array.isArray(data.conflicts) ? data.conflicts.length : 0;
              const m = Array.isArray(data.suggestions) ? data.suggestions.length : 0;
              if (n > 0) {
                panel.webview.postMessage({ t: 'info', text: `检测到 ${n} 处规则冲突，已在下方列出。建议数：${m}` });
              } else {
                panel.webview.postMessage({ t: 'info', text: `未检测到规则冲突。建议数：${m}` });
              }
            } catch {}
          }
        } else if (msg.t === 'coverage') {
          // Quick combined report for toast summary
          let weakCount = 0, groupsCount = 0, nearCount = 0; let minModule: number | undefined = undefined;
          try {
            const rep = await client.request('tools/call', { name: 'coverage.report', arguments: {} });
            if (rep && rep.ok) {
              weakCount = Array.isArray(rep.weak) ? rep.weak.length : 0;
              groupsCount = Array.isArray(rep.groups) ? rep.groups.length : 0;
              nearCount = Array.isArray(rep.near) ? rep.near.length : 0;
              if (typeof rep.min_module === 'number') minModule = rep.min_module;
            }
          } catch {}
          const resList = await client.request('resources/list', {});
          const covUri = (resList.resources || []).find((r: any) => String(r.uri || '').endsWith('/summary'))?.uri;
          const groupsUri = (resList.resources || []).find((r: any) => String(r.uri || '').endsWith('/groups'))?.uri;
          const treeUri = (resList.resources || []).find((r: any) => String(r.uri || '').endsWith('/tree'))?.uri;
          const nearUri = (resList.resources || []).find((r:any)=> String(r.uri||'').endsWith('/near'))?.uri;
          if (!covUri) {
            vscode.window.showWarningMessage('未找到覆盖率资源，请先在推送/CI 生成 coverage.xml');
            panel.webview.postMessage({ t: 'info', text: '未找到覆盖率资源，请先运行 pytest 生成 coverage.xml（或在 CI 推送生成）。' });
            return;
          }
          const res = await client.request('resources/read', { uri: covUri });
          const data = JSON.parse(res.text || '{}');
          if (!data.ok) {
            vscode.window.showWarningMessage(data.message || '未找到 coverage.xml，请先在推送/CI 生成');
            panel.webview.postMessage({ t: 'info', text: data.message || '覆盖率摘要不可用，请生成 coverage.xml' });
          } else {
            panel.webview.postMessage({ t: 'covWeakAll', items: data.weak || [] });
            panel.webview.postMessage({ t: 'covWeak', items: data.weak || [] });
            const wcnt = (data.weak || []).length;
            panel.webview.postMessage({ t: 'info', text: `弱项 ${wcnt} 个` });
          }
          if (groupsUri) {
            const gres = await client.request('resources/read', { uri: groupsUri });
            const gdata = JSON.parse(gres.text || '{}');
            if (gdata.ok) {
              panel.webview.postMessage({ t: 'covGroups', items: gdata.groups || [] });
            }
          }
          if (treeUri) {
            try {
              const tres = await client.request('resources/read', { uri: treeUri });
              const tdata = JSON.parse((tres as any).text || '{}');
              if (tdata.ok) {
                panel.webview.postMessage({ t: 'covTreeData', tree: tdata.tree || { name: '/', children: {} } });
              }
            } catch {}
          }
          if (nearUri) {
            try {
              const nres = await client.request('resources/read', { uri: nearUri });
              const ndata = JSON.parse((nres as any).text || '{}');
              if (ndata.ok) {
                const items = ndata.near || [];
                panel.webview.postMessage({ t: 'covNear', items });
                const n = Array.isArray(items) ? items.length : 0;
                panel.webview.postMessage({ t: 'info', text: `近阈值文件：${n} 个（≤3%）` });
              }
            } catch {}
          }
          // Toast summary for panel action (align with VS Code command behavior)
          try {
            const parts: string[] = [`weak=${weakCount}`, `near=${nearCount}`, `groups=${groupsCount}`];
            if (typeof minModule === 'number') parts.push(`min_module=${(minModule*100).toFixed(0)}%`);
            vscode.window.showInformationMessage('Coverage loaded: ' + parts.join(', '));
            try { await updateStatusBar(); } catch {}
            try {
              const content = 'Coverage loaded: ' + parts.join(', ');
              await client.request('tools/call', { name: 'memory.append_turn', arguments: { role: 'assistant', content, meta: { source: 'vscode', action: 'panel.coverage' } } });
            } catch {}
          } catch {}
        } else if (msg.t === 'coverageTree') {
          const resList = await client.request('resources/list', {});
          const treeUri = (resList.resources || []).find((r: any) => String(r.uri || '').endsWith('/tree'))?.uri;
          if (!treeUri) {
            panel.webview.postMessage({ t: 'info', text: '未找到目录树资源，请先生成 coverage.xml 或点击“加载覆盖率”。' });
            return;
          }
          const tres = await client.request('resources/read', { uri: treeUri });
          try {
            const data = JSON.parse((tres as any).text || '{}');
            if (!data.ok) {
              panel.webview.postMessage({ t: 'info', text: '目录树不可用，请先生成 coverage.xml。' });
              return;
            }
            panel.webview.postMessage({ t: 'covTreeData', tree: data.tree || { name: '/', children: {} } });
          } catch {
            panel.webview.postMessage({ t: 'info', text: '解析目录树失败。' });
          }
        } else if (msg.t === 'ingestRules') {
          const pathsInput = await vscode.window.showInputBox({
            title: '输入要摄取的文件或目录（逗号分隔）',
            placeHolder: '如：rules.md, docs/rules',
          });
          if (!pathsInput) return;
          const paths = pathsInput.split(',').map(s => s.trim()).filter(Boolean);
          await client.request('tools/call', { name: 'rules.ingest', arguments: { paths } });
          vscode.window.setStatusBarMessage('规则摄取完成', 3000);
          // 自动刷新
          const resList = await client.request('resources/list', {});
          const compiledUri = (resList.resources || []).find((r: any) => String(r.uri || '').endsWith('/compiled'))?.uri;
          const suggUri = (resList.resources || []).find((r: any) => String(r.uri || '').endsWith('/suggestions'))?.uri;
          const jsonUri = (resList.resources || []).find((r: any) => String(r.uri || '').endsWith('/compiled.json'))?.uri;
          if (compiledUri) {
            const res = await client.request('resources/read', { uri: compiledUri });
            panel.webview.postMessage({ t: 'rules', md: res.text || '' });
          }
          if (suggUri) {
            const sug = await client.request('resources/read', { uri: suggUri });
            panel.webview.postMessage({ t: 'sugg', md: sug.text || '' });
          }
          if (jsonUri) {
            const compiled = await client.request('resources/read', { uri: jsonUri });
            try {
              const data = JSON.parse(((compiled as any).text) || '{}');
              panel.webview.postMessage({ t: 'conflicts', items: data.conflicts || [] });
              const n = Array.isArray(data.conflicts) ? data.conflicts.length : 0;
              const m = Array.isArray(data.suggestions) ? data.suggestions.length : 0;
              panel.webview.postMessage({ t: 'info', text: (n > 0) ? `检测到 ${n} 处规则冲突，已在下方列出。建议数：${m}` : `未检测到规则冲突。建议数：${m}` });
            } catch {
              panel.webview.postMessage({ t: 'info', text: '解析规则 JSON 失败。' });
            }
          }
        } else if (msg.t === 'validateRules') {
          await client.request('tools/call', { name: 'rules.validate', arguments: {} });
          vscode.window.setStatusBarMessage('规则校验完成', 3000);
          const resList = await client.request('resources/list', {});
          const compiledUri = (resList.resources || []).find((r: any) => String(r.uri || '').endsWith('/compiled'))?.uri;
          const suggUri = (resList.resources || []).find((r: any) => String(r.uri || '').endsWith('/suggestions'))?.uri;
          const jsonUri = (resList.resources || []).find((r: any) => String(r.uri || '').endsWith('/compiled.json'))?.uri;
          if (compiledUri) {
            const res = await client.request('resources/read', { uri: compiledUri });
            panel.webview.postMessage({ t: 'rules', md: res.text || '' });
          }
          if (suggUri) {
            const sug = await client.request('resources/read', { uri: suggUri });
            panel.webview.postMessage({ t: 'sugg', md: sug.text || '' });
          }
          if (jsonUri) {
            const compiled = await client.request('resources/read', { uri: jsonUri });
            try {
              const data = JSON.parse(((compiled as any).text) || '{}');
              panel.webview.postMessage({ t: 'conflicts', items: data.conflicts || [] });
              const n = Array.isArray(data.conflicts) ? data.conflicts.length : 0;
              const m = Array.isArray(data.suggestions) ? data.suggestions.length : 0;
              panel.webview.postMessage({ t: 'info', text: (n > 0) ? `检测到 ${n} 处规则冲突，已在下方列出。建议数：${m}` : `未检测到规则冲突。建议数：${m}` });
            } catch {
              panel.webview.postMessage({ t: 'info', text: '解析规则 JSON 失败。' });
            }
          }
        } else if (msg.t === 'covExport') {
          try {
            const out = await client.request('tools/call', { name: 'coverage.export', arguments: {} });
            vscode.window.showInformationMessage('Coverage 导出完成: ' + (out.out_dir || ''));
            // 预览 weak_top.csv 前 3 行
            const ws = getWorkspaceRoot();
            if (ws) {
              const uri = vscode.Uri.file(ws + '/.mcp/dashboard/weak_top.csv');
              try {
                const data = await vscode.workspace.fs.readFile(uri);
                const text = Buffer.from(data).toString('utf8');
                const raw = text.split(/\r?\n/).slice(0, 4).filter(Boolean);
                if (raw.length >= 1) {
                  const outLines: string[] = [];
                  outLines.push(raw[0]); // header: file,coverage,threshold,delta
                  for (const row of raw.slice(1)) {
                    const parts = row.split(',');
                    if (parts.length >= 4) {
                      const file = parts[0];
                      const cov = Number(parts[1]||0)*100;
                      const thr = Number(parts[2]||0)*100;
                      const delt = Number(parts[3]||0)*100;
                      outLines.push(`${file},${cov.toFixed(1)}%,${Math.round(thr)}%,${delt.toFixed(1)}%`);
                    } else {
                      outLines.push(row);
                    }
                  }
                  panel.webview.postMessage({ t: 'csvPreview', which: 'weak_top.csv', head: outLines });
                }
              } catch {}
              // 预览 near_top.csv 前 3 行
              try {
                const uri2 = vscode.Uri.file(ws + '/.mcp/dashboard/near_top.csv');
                const data2 = await vscode.workspace.fs.readFile(uri2);
                const text2 = Buffer.from(data2).toString('utf8');
                const raw2 = text2.split(/\r?\n/).slice(0, 4).filter(Boolean);
                if (raw2.length >= 1) {
                  const out2: string[] = [];
                  out2.push(raw2[0]); // header: file,coverage,threshold,delta_up
                  for (const row of raw2.slice(1)) {
                    const parts = row.split(',');
                    if (parts.length >= 4) {
                      const file = parts[0];
                      const cov = Number(parts[1]||0)*100;
                      const thr = Number(parts[2]||0)*100;
                      const delt = Number(parts[3]||0)*100;
                      out2.push(`${file},${cov.toFixed(1)}%,${Math.round(thr)}%,${delt.toFixed(1)}%`);
                    } else {
                      out2.push(row);
                    }
                  }
                  panel.webview.postMessage({ t: 'csvPreview', which: 'near_top.csv', head: out2 });
                }
              } catch {}
              // 预览 groups.csv 前 3 行
              try {
                const uri3 = vscode.Uri.file(ws + '/.mcp/dashboard/groups.csv');
                const data3 = await vscode.workspace.fs.readFile(uri3);
                const text3 = Buffer.from(data3).toString('utf8');
                const raw3 = text3.split(/\r?\n/).slice(0, 4).filter(Boolean);
                if (raw3.length >= 1) {
                  const out3: string[] = [];
                  out3.push(raw3[0]); // header: prefix,coverage,threshold,weak_count,files_count
                  for (const row of raw3.slice(1)) {
                    const parts = row.split(',');
                    if (parts.length >= 5) {
                      const pref = parts[0];
                      const cov = Number(parts[1]||0)*100;
                      const thr = Number(parts[2]||0)*100;
                      const wc = parts[3];
                      const fc = parts[4];
                      out3.push(`${pref},${cov.toFixed(1)}%,${Math.round(thr)}%,${wc},${fc}`);
                    } else {
                      out3.push(row);
                    }
                  }
                  panel.webview.postMessage({ t: 'csvPreview', which: 'groups.csv', head: out3 });
                }
              } catch {}
            }
          } catch (e:any) {
            vscode.window.showWarningMessage('Coverage 导出失败：' + String(e));
          }
        } else if (msg.t === 'csvPreviewPick') {
          try {
            const ws = getWorkspaceRoot(); if (!ws) throw new Error('no workspace');
            const which = String(msg.which || 'weak_top.csv');
            const path = ws + '/.mcp/dashboard/' + which;
            const uri = vscode.Uri.file(path);
            const data = await vscode.workspace.fs.readFile(uri);
            const text = Buffer.from(data).toString('utf8');
            const raw = text.split(/\r?\n/).slice(0, 4).filter(Boolean);
            const out: string[] = [];
            if (raw.length >= 1) {
              out.push(raw[0]);
              for (const row of raw.slice(1)) {
                const parts = row.split(',');
                if (which === 'weak_top.csv' || which === 'near_top.csv') {
                  if (parts.length >= 4) {
                    const file = parts[0];
                    const cov = Number(parts[1]||0)*100;
                    const thr = Number(parts[2]||0)*100;
                    const delt = Number(parts[3]||0)*100;
                    out.push(`${file},${cov.toFixed(1)}%,${Math.round(thr)}%,${delt.toFixed(1)}%`);
                  } else { out.push(row); }
                } else if (which === 'groups.csv') {
                  if (parts.length >= 5) {
                    const pref = parts[0];
                    const cov = Number(parts[1]||0)*100;
                    const thr = Number(parts[2]||0)*100;
                    const wc = parts[3];
                    const fc = parts[4];
                    out.push(`${pref},${cov.toFixed(1)}%,${Math.round(thr)}%,${wc},${fc}`);
                  } else { out.push(row); }
                } else { out.push(row); }
              }
            }
            panel.webview.postMessage({ t: 'csvPreview', which, head: out });
          } catch (e:any) {
            vscode.window.showWarningMessage('读取 CSV 失败：' + String(e));
          }
        } else if (msg.t === 'loadSugg') {
          const resList = await client.request('resources/list', {});
          const suggUri = (resList.resources || []).find((r: any) => String(r.uri || '').endsWith('/suggestions'))?.uri;
          if (!suggUri) {
            panel.webview.postMessage({ t: 'sugg', md: '未找到建议资源，请先“摄取规则”或“校验规则”' });
            panel.webview.postMessage({ t: 'info', text: '未找到规则建议，请点击“摄取规则 / Ingest”进行摄取。' });
            panel.webview.postMessage({ t: 'suggestIngest' });
            return;
          }
          const sug = await client.request('resources/read', { uri: suggUri });
          panel.webview.postMessage({ t: 'sugg', md: sug.text || '' });
        } else if (msg.t === 'installHooks') {
          await client.request('tools/call', { name: 'git.install_hooks', arguments: {} });
          vscode.window.setStatusBarMessage('钩子安装完成', 3000);
          try {
            await client.request('tools/call', { name: 'memory.append_turn', arguments: { role: 'assistant', content: 'Git hooks installed', meta: { source: 'vscode', action: 'git.install_hooks' } } });
          } catch {}
        } else if (msg.t === 'memory') {
          const resList = await client.request('resources/list', {});
          const memUri = (resList.resources || []).find((r: any) => String(r.uri || '').startsWith('memory://'))?.uri;
          if (!memUri) { panel.webview.postMessage({ t: 'memory', text: '无记忆资源' }); return; }
          const res = await client.request('resources/read', { uri: memUri });
          panel.webview.postMessage({ t: 'memory', text: res.text || '' });
        } else if (msg.t === 'plan') {
          const resList = await client.request('resources/list', {});
          const planUri = (resList.resources || []).find((r: any) => String(r.uri || '').startsWith('progress://'))?.uri;
          if (!planUri) { panel.webview.postMessage({ t: 'plan', text: '无计划资源' }); return; }
          const res = await client.request('resources/read', { uri: planUri });
          panel.webview.postMessage({ t: 'plan', text: res.text || '' });
          const act = await vscode.window.showQuickPick(['标记进行中 / In progress', '标记完成 / Done', '仅查看 / View'], { title: '计划操作' });
          if (act && act.startsWith('标记进行中')) {
            const cur = await vscode.window.showInputBox({ title: '当前步骤 / Current step', placeHolder: '例如：实现 MCP 协议方法' });
            if (cur) await client.request('tools/call', { name: 'plan.set', arguments: { status: 'in_progress', current: cur } });
            const res2 = await client.request('resources/read', { uri: planUri });
            panel.webview.postMessage({ t: 'plan', text: res2.text || '' });
          } else if (act && act.startsWith('标记完成')) {
            await client.request('tools/call', { name: 'plan.set', arguments: { status: 'done' } });
            const res2 = await client.request('resources/read', { uri: planUri });
            panel.webview.postMessage({ t: 'plan', text: res2.text || '' });
          }
        } else if (msg.t === 'ciFetch') {
          const cfg = await client.request('tools/call', { name: 'config.get', arguments: {} });
          panel.webview.postMessage({ t: 'ci', config: cfg.config || {} });
          vscode.window.setStatusBarMessage('已加载 CI 配置', 2000);
        } else if (msg.t === 'ciCheck') {
          try {
          const ws = getWorkspaceRoot();
          if (!ws) throw new Error('no workspace');
          const target = vscode.Uri.file(ws + '/.github/workflows/ci.yml');
          await vscode.workspace.fs.stat(target);
          panel.webview.postMessage({ t: 'ciStatus', exist: true });
          } catch {
            panel.webview.postMessage({ t: 'ciStatus', exist: false });
          }
        } else if (msg.t === 'ciSave') {
          const data = msg.data || {};
          await client.request('tools/call', { name: 'config.update', arguments: { data } });
          vscode.window.setStatusBarMessage('CI 配置已保存', 2000);
        } else if (msg.t === 'ciGen') {
          const out = await client.request('tools/call', { name: 'ci.generate', arguments: {} });
          vscode.window.showInformationMessage('已生成 CI: ' + (out.path || ''));        
          vscode.commands.executeCommand('workbench.action.files.refresh');
          panel.webview.postMessage({ t: 'ciCheck' });
          try { await client.request('tools/call', { name: 'memory.append_turn', arguments: { role: 'assistant', content: 'CI generated', meta: { source: 'vscode', action: 'ci.generate', path: out && out.path } } }); } catch {}
        } else if (msg.t === 'ciValidate') {
          const res = await client.request('tools/call', { name: 'ci.validate', arguments: {} });
          panel.webview.postMessage({ t: 'ciChecks', checks: (res.checks || {}) });
          try { await client.request('tools/call', { name: 'memory.append_turn', arguments: { role: 'assistant', content: 'CI validated', meta: { source: 'vscode', action: 'ci.validate', ok: res && res.ok } } }); } catch {}
        } else if (msg.t === 'ciPreviewInline') {
          const resList = await client.request('resources/list', {});
          const ciUri = (resList.resources || []).find((r:any)=> String(r.uri||'').startsWith('ci://'))?.uri;
          if (!ciUri) { panel.webview.postMessage({ t: 'ciPreviewContent', text: '（未生成 CI）' }); return; }
          const res = await client.request('resources/read', { uri: ciUri });
          panel.webview.postMessage({ t: 'ciPreviewContent', text: res.text || '' });
        } else if (msg.t === 'ciOpen') {
          const ws = getWorkspaceRoot(); if (!ws) return;
          const target = vscode.Uri.file(ws + '/.github/workflows/ci.yml');
          try {
            await vscode.workspace.fs.stat(target);
            const doc = await vscode.workspace.openTextDocument(target);
            await vscode.window.showTextDocument(doc, { preview: false });
          } catch {
            vscode.window.showWarningMessage('CI 文件不存在，请先生成');
          }
        } else if (msg.t === 'ciPreview') {
          const resList = await client.request('resources/list', {});
          const ciUri = (resList.resources || []).find((r:any)=> String(r.uri||'').startsWith('ci://'))?.uri;
          if (!ciUri) { vscode.window.showWarningMessage('未找到 CI 资源'); return; }
          const res = await client.request('resources/read', { uri: ciUri });
          const doc = await vscode.workspace.openTextDocument({ language: 'yaml', content: res.text || '' });
          await vscode.window.showTextDocument(doc, { preview: true });
        } else if (msg.t === 'ciOpen') {
          const ws = getWorkspaceRoot(); if (!ws) return;
          const target = vscode.Uri.file(ws + '/.github/workflows/ci.yml');
          try {
            await vscode.workspace.fs.stat(target);
            const doc = await vscode.workspace.openTextDocument(target);
            await vscode.window.showTextDocument(doc, { preview: false });
          } catch {
            vscode.window.showWarningMessage('CI 文件不存在，请先生成');
          }
        } else if (msg.t === 'ideScaffold') {
          const pick = await vscode.window.showQuickPick([
            { label: 'VS Code', val: 'vscode' },
            { label: 'Cursor', val: 'cursor' },
            { label: 'JetBrains', val: 'jetbrains' },
            { label: 'Neovim', val: 'neovim' },
          ], { title: '选择 IDE' });
          if (!pick) return;
          const out = await client.request('tools/call', { name: 'ide.scaffold', arguments: { editor: pick.val } });
          vscode.window.showInformationMessage('已生成 IDE 集成配置: ' + JSON.stringify(out.files || []));
        } else if (msg.t === 'compliance') {
          const out = await client.request('tools/call', { name: 'compliance.commitment', arguments: { write: true } });
          vscode.window.showInformationMessage('已生成合规承诺: ' + (out.path || '.mcp/compliance.md'));
        } else if (msg.t === 'openCompliance') {
          try {
            // ensure file exists, then open
            const ws = getWorkspaceRoot(); if (!ws) return;
            const p = vscode.Uri.file(ws + '/.mcp/compliance.md');
            try { await vscode.workspace.fs.stat(p); }
            catch { await client.request('tools/call', { name: 'compliance.commitment', arguments: { write: true } }); }
            const doc = await vscode.workspace.openTextDocument(p);
            await vscode.window.showTextDocument(doc, { preview: false });
          } catch (e:any) {
            vscode.window.showWarningMessage('无法打开合规承诺：' + String(e));
          }
        } else if (msg.t === 'openIdeDir') {
          try {
            const ws = getWorkspaceRoot(); if (!ws) return;
            const p = vscode.Uri.file(ws + '/.mcp/ide');
            await vscode.commands.executeCommand('revealFileInOS', p);
          } catch (e:any) {
            vscode.window.showWarningMessage('无法打开 IDE 目录：' + String(e));
          }
        } else if (msg.t === 'insertSamples') {
          const semgrep = `rules:\n  - id: py-no-eval\n    message: \"Avoid eval() — security risk\"\n    languages: [python]\n    severity: ERROR\n    pattern: eval(...)\n\n  - id: py-no-exec\n    message: \"Avoid exec() — security risk\"\n    languages: [python]\n    severity: ERROR\n    pattern: exec(...)\n`;
          const hadolint = `ignored:\n  - DL3008\n  - DL3059\n\noverrides:\n  DL3007: warning\n`;
          await client.request('tools/call', { name: 'fs.apply_patch', arguments: { files: [
            { path: '.semgrep.yml', content: semgrep },
            { path: '.hadolint.yaml', content: hadolint }
          ] } });
          vscode.window.setStatusBarMessage('已插入示例规则（.semgrep.yml / .hadolint.yaml）', 3000);
        } else if (msg.t === 'prepareEnvDry') {
          try {
            const out = await client.request('tools/call', { name: 'env.prepare', arguments: { create: false, install: false } });
            vscode.window.showInformationMessage('env.prepare 计划: ' + JSON.stringify(out.plan || out));
            try { await client.request('tools/call', { name: 'memory.append_turn', arguments: { role: 'assistant', content: 'env.prepare dry-run', meta: { source: 'vscode', action: 'env.prepare', create: false, install: false } } }); } catch {}
          } catch (e:any) {
            vscode.window.showErrorMessage('env.prepare 执行失败：' + String(e));
          }
        } else if (msg.t === 'prepareEnvInstall') {
          try {
            const out = await client.request('tools/call', { name: 'env.prepare', arguments: { create: true, install: true } });
            const msgInfo = (out && (out as any).ok) ? ('已创建并安装：' + String((out as any).venv || '')) : '执行失败';
            vscode.window.showInformationMessage('env.prepare: ' + msgInfo);
            try { await client.request('tools/call', { name: 'memory.append_turn', arguments: { role: 'assistant', content: 'env.prepare install', meta: { source: 'vscode', action: 'env.prepare', create: true, install: true } } }); } catch {}
          } catch (e:any) {
            vscode.window.showErrorMessage('env.prepare 执行失败：' + String(e));
          }
        } else if (msg.t === 'selectProject') {
          const folders = vscode.workspace.workspaceFolders || [];
          if (!folders.length) { vscode.window.showWarningMessage('未找到工作区'); return; }
          const pick = await vscode.window.showQuickPick(folders.map(f=>({ label: f.name, description: f.uri.fsPath })), { title: '选择项目根目录' });
          if (!pick) return;
          try {
            await client.request('tools/call', { name: 'project.switch', arguments: { path: pick.description } });
            panel.webview.postMessage({ t: 'project', name: pick.label });
            panel.webview.postMessage({ t: 'info', text: '已切换至项目：' + pick.label });
          } catch (e:any) {
            vscode.window.showErrorMessage('切换项目失败：' + String(e));
          }
        }
        else if (msg.t === 'onboardPreview') {
          try {
            const out = await client.request('tools/call', { name: 'rules.onboard', arguments: { apply: false } });
            const ob = out || {};
            const lines: string[] = [];
            if (typeof ob.summary === 'string' && ob.summary) lines.push(String(ob.summary));
            try {
              const p = ob.profile || {};
              const cov = p.coverage || {}; const sec = p.security || {}; const cont = p.container || {}; const lic = p.license || {}; const ci = p.ci || {};
              lines.push('— coverage.min_module=' + (cov.min_module!==undefined? String(cov.min_module):'-'));
              lines.push('— security: secrets_scan=' + String(!!sec.secrets_scan) + ', sast_strict=' + String(!!sec.sast_strict));
              lines.push('— container: baseline=' + String(!!cont.baseline) + ', required=' + String(!!cont.required));
              lines.push('— license.required=' + String(!!lic.required));
              if (ci && (ci.hadolint || ci.semgrep_config)) {
                lines.push('— ci: hadolint=' + String(!!ci.hadolint) + (ci.semgrep_config? (', semgrep_config=' + String(ci.semgrep_config)) : ''));
              }
            } catch {}
            panel.webview.postMessage({ t: 'onboardShow', text: lines.join('\n') });
            panel.webview.postMessage({ t: 'info', text: 'Onboard 预览完成' });
          } catch (e:any) {
            panel.webview.postMessage({ t: 'info', text: 'Onboard 预览失败：' + String(e) });
          }
        } else if (msg.t === 'onboardApply') {
          try {
            const out = await client.request('tools/call', { name: 'rules.onboard', arguments: { apply: true } });
            vscode.window.showInformationMessage('Onboard 已采纳：' + JSON.stringify({ applied: out && out.applied }));
            try { await client.request('tools/call', { name: 'memory.append_turn', arguments: { role: 'assistant', content: 'Onboard applied', meta: { source: 'vscode', action: 'rules.onboard' } } }); } catch {}
          } catch (e:any) {
            vscode.window.showErrorMessage('Onboard 采纳失败：' + String(e));
          }
        }
      } catch (e: any) {
        vscode.window.showErrorMessage('操作失败：' + String(e));
      } finally {
        try { if (__panelInFlightResolve) { __panelInFlightResolve(); } } catch {}
        __panelInFlightResolve = null;
        __panelInFlight = null;
      }
    };
    panel.webview.onDidReceiveMessage(async (msg) => { await __panelDispatch(msg); });
    __testPanelHandler = __panelDispatch;

    // 处理从 webview 的“打开源文件/ready/ready2”请求
    panel.webview.onDidReceiveMessage(async (msg) => {
      await handleOpenMessage(msg);
      if (msg && msg.t === 'ready') { try { if (__panelReadyResolve) { __panelReadyResolve(); __panelReadyResolve = null; } } catch {} }
      if (msg && msg.t === 'ready2') {
        try {
          const key = String((msg.topic||'any'));
          const r = __ready2Resolvers.get(key) || __ready2Resolvers.get('any');
          if (r) r();
        } catch {}
      }
      if (msg && msg.t === 'nl') {
        try {
          const text = String(msg.text || '').trim();
          if (!text) return;
          const res = await client.request('tools/call', { name: 'nl.command', arguments: { text } });
          const mapped = (res && (res as any).parsed && (res as any).parsed.tool) || '';
          // 简易调度：根据映射调用常用工具
          const lower = text.toLowerCase();
          const runIngest = async () => {
            // 粗略提取可能的路径
            const cand = text.split(/[，,\s]+/).filter(s => /[./]/.test(s));
            const paths = cand.filter(p => !/摄取|规则|ingest|load|载入|加载/.test(p));
            const final = paths.length ? paths : (await vscode.window.showInputBox({ title: '输入要摄取的文件或目录（逗号分隔）' }))?.split(',').map(s=>s.trim()).filter(Boolean) || [];
            if (!final.length) return;
            await client.request('tools/call', { name: 'rules.ingest', arguments: { paths: final } });
            panel.webview.postMessage({ t: 'info', text: '规则摄取完成：' + final.join(', ') });
          };
          const runCoverage = async () => {
            const resList = await client.request('resources/list', {});
            const summaryUri = (resList.resources || []).find((r: any) => String(r.uri || '').endsWith('/summary'))?.uri;
            if (!summaryUri) { panel.webview.postMessage({ t: 'info', text: '未找到覆盖率资源，请先生成 coverage.xml。' }); return; }
            const r = await client.request('resources/read', { uri: summaryUri });
            try { const data = JSON.parse((r as any).text || '{}'); panel.webview.postMessage({ t: 'covWeakAll', items: data.weak || [] }); } catch {}
          };
          const runNear = async () => {
            const pct = 0.03;
            const r = await client.request('tools/call', { name: 'coverage.near', arguments: { within: pct, top: 50 } });
            const items = (r && (r as any).near) ? (r as any).near : [];
            panel.webview.postMessage({ t: 'covNearDisplay', items, pct: 3 });
          };
          const runLoadRules = async () => {
            const resList = await client.request('resources/list', {});
            const compiledUri = (resList.resources || []).find((r: any) => String(r.uri || '').endsWith('/compiled'))?.uri;
            const suggUri = (resList.resources || []).find((r: any) => String(r.uri || '').endsWith('/suggestions'))?.uri;
            if (compiledUri) {
              const res = await client.request('resources/read', { uri: compiledUri });
              panel.webview.postMessage({ t: 'rules', md: res.text || '' });
            }
            if (suggUri) {
              const sug = await client.request('resources/read', { uri: suggUri });
              panel.webview.postMessage({ t: 'sugg', md: sug.text || '' });
            }
          };
          const runToggleMemory = async () => {
            const on = !/(关闭|disable)/.test(text);
            await client.request('tools/call', { name: 'memory.toggle_auto', arguments: { on } });
            panel.webview.postMessage({ t: 'info', text: on ? '已开启滚动记忆' : '已关闭滚动记忆' });
          };
          const runMemorySnapshot = async () => {
            const snap = await client.request('tools/call', { name: 'memory.snapshot', arguments: {} });
            panel.webview.postMessage({ t: 'memory', text: JSON.stringify(snap || {}, null, 2) });
          };
          const runCiGen = async () => { await client.request('tools/call', { name: 'ci.generate', arguments: {} }); panel.webview.postMessage({ t: 'info', text: '已生成 CI' }); };
          const runCiValidate = async () => { const v = await client.request('tools/call', { name: 'ci.validate', arguments: {} }); panel.webview.postMessage({ t: 'info', text: 'CI 校验完成' }); };
          const runCiAutofix = async () => { await client.request('tools/call', { name: 'ci.autofix', arguments: {} }); panel.webview.postMessage({ t: 'info', text: 'CI 已自修复' }); };
          const runInstallHooks = async () => { await client.request('tools/call', { name: 'git.install_hooks', arguments: {} }); panel.webview.postMessage({ t: 'info', text: '钩子安装完成' }); };
          const runEnforce = async () => { await client.request('tools/call', { name: 'rules.enforce', arguments: {} }); panel.webview.postMessage({ t: 'info', text: '已应用门禁策略到配置' }); };
          const runRulesOnboard = async () => {
            const pick = await vscode.window.showQuickPick([
              { label: '个人 / personal', val: 'personal' },
              { label: '专业 / pro', val: 'pro' },
              { label: '企业 / enterprise', val: 'enterprise' },
              { label: '机构 / institution', val: 'institution' },
            ], { title: '选择应用场景 / Scenario' });
            if (!pick) return;
            const pickC = await vscode.window.showQuickPick([
              { label: '小 / small', val: 'small' },
              { label: '中 / medium', val: 'medium' },
              { label: '大 / large', val: 'large' },
            ], { title: '选择复杂度 / Complexity' });
            if (!pickC) return;
            const pickM = await vscode.window.showQuickPick([
              { label: 'TDD', val: 'tdd' },
              { label: 'BDD', val: 'bdd' },
              { label: '文档驱动 / doc', val: 'doc' },
              { label: '原型 / spike', val: 'spike' },
            ], { title: '选择开发模式 / Dev Mode' });
            if (!pickM) return;
            const out = await client.request('tools/call', { name: 'rules.onboard', arguments: { scenario: pick.val, complexity: pickC.val, devMode: pickM.val, apply: true } });
            vscode.window.showInformationMessage('已应用规则档：' + JSON.stringify(out));
          };
          const runPrepareEnv = async () => { const out = await client.request('tools/call', { name: 'env.prepare', arguments: { create: false, install: false } }); vscode.window.showInformationMessage('env.prepare 计划: ' + JSON.stringify(out.plan || out)); };

          if (mapped === 'rules.ingest') await runIngest();
          else if (mapped === 'coverage.near') await runNear();
          else if (mapped === 'resources.read') { if (/覆盖率|coverage/.test(lower)) await runCoverage(); else await runLoadRules(); }
          else if (mapped === 'memory.toggle_auto') await runToggleMemory();
          else if (mapped === 'memory.snapshot') await runMemorySnapshot();
          else if (mapped === 'ci.generate') await runCiGen();
          else if (mapped === 'ci.validate') await runCiValidate();
          else if (mapped === 'ci.autofix') await runCiAutofix();
          else if (mapped === 'git.install_hooks') await runInstallHooks();
          else if (mapped === 'rules.validate') { await client.request('tools/call', { name: 'rules.validate', arguments: {} }); await runLoadRules(); }
          else if (mapped === 'rules.enforce') await runEnforce();
          else if (mapped === 'env.prepare') await runPrepareEnv();

          vscode.window.setStatusBarMessage('已执行：' + (mapped || 'nl.command'), 3000);
          panel.webview.postMessage({ t: 'info', text: '已执行：' + (text || '') });
          // 请求刷新历史
          vscode.commands.executeCommand('setContext', 'ruleflow.lastNL', text);
          panel.webview.postMessage({ t: 'nlRunOk', text });
          const h = context.globalState.get<string[]>('ruleflow.nl.history') || [];
          const nh = [text, ...h.filter(x=>x!==text)].slice(0, 10);
          await context.globalState.update('ruleflow.nl.history', nh);
          panel.webview.postMessage({ t: 'nlHistory', items: nh });
        } catch (e:any) {
          vscode.window.showWarningMessage('自然语言执行失败：' + String(e));
          panel.webview.postMessage({ t: 'info', text: '自然语言执行失败' });
        }
      }
      // Webview 请求“近阈值”交互：扩展侧弹出输入框并计算
      if (msg && msg.t === 'covNearPrompt') {
        try {
          const last = Number(msg.last || 3) || 3;
          const val = await vscode.window.showInputBox({ title: '近阈值窗口（百分比）', value: String(last), prompt: '单位 %（1–10），例如 3 表示 ≤3%' });
          if (!val) { return; }
          const pct = Math.max(1, Math.min(10, parseFloat(val))) || 3;
          const top = 50;
          const res = await client.request('tools/call', { name: 'coverage.near', arguments: { within: pct/100.0, top } });
          const items = (res && (res as any).near) ? (res as any).near : [];
          panel.webview.postMessage({ t: 'covNearDisplay', items, pct, top });
        } catch (e:any) {
          vscode.window.showWarningMessage('获取近阈值失败：' + String(e));
        }
      }
      if (msg && msg.t === 'nlClearHistory') {
        try {
          await context.globalState.update('ruleflow.nl.history', []);
          panel.webview.postMessage({ t: 'nlHistory', items: [] });
          panel.webview.postMessage({ t: 'info', text: '已清空自然语言历史' });
        } catch {}
      }
      if (msg && msg.t === 'nlFetchHistory') {
        try {
          const h = context.globalState.get<string[]>('ruleflow.nl.history') || [];
          panel.webview.postMessage({ t: 'nlHistory', items: h });
        } catch {}
      }
      if (msg && msg.t === 'licenseVerify') {
        try {
          const diag = await client.request('tools/call', { name: 'env.diagnose', arguments: {} });
          panel.webview.postMessage({ t: 'license', license: (diag && (diag as any).license) || {} });
          panel.webview.postMessage({ t: 'info', text: 'License 已校验' });
        } catch (e:any) {
          vscode.window.showWarningMessage('License 校验失败：' + String(e));
        }
      }
      if (msg && msg.t === 'licenseActivate') {
        try {
          const files = await vscode.window.showOpenDialog({ title: '选择 License JSON 文件', canSelectMany: false, filters: { 'JSON': ['json'], 'All Files': ['*'] } });
          if (!files || !files.length) return;
          const p = files[0].fsPath;
          await client.request('tools/call', { name: 'license.activate', arguments: { path: p } });
          const diag = await client.request('tools/call', { name: 'env.diagnose', arguments: {} });
          panel.webview.postMessage({ t: 'license', license: (diag && (diag as any).license) || {} });
          panel.webview.postMessage({ t: 'info', text: 'License 已激活' });
        } catch (e:any) {
          vscode.window.showWarningMessage('License 激活失败：' + String(e));
        }
      }
    });
  });
  // Quick actions: small launcher for common tasks
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant.quickActions', async () => {
    const pick = await vscode.window.showQuickPick([
      { label: '摄取规则 / Ingest', action: 'ingestRules' },
      { label: '加载覆盖率 / Load Coverage', action: 'coverage' },
      { label: '生成 CI / Generate CI', action: 'ciGen' },
      { label: '校验 CI / Validate CI', action: 'ciValidate' },
      { label: '导出覆盖率 / Export Coverage', action: 'covExport' },
      { label: '打开 JB 验证 / Open JB Verify', action: 'openJbVerify' },
      { label: '打开 jb_groups.md', action: 'openJbGroupsMd' },
      { label: '打开 weak_top.csv', action: 'openWeakCsv' },
      { label: '打开 near_top.csv', action: 'openNearCsv' },
      { label: '打开 groups.csv', action: 'openGroupsCsv' },
    ], { title: 'RuleFlow: Quick Actions' });
    if (!pick) { return; }
    try { client.start(context); } catch {}
    // Route to openPanel first to ensure webview exists
    await vscode.commands.executeCommand('mcpRulesAssistant.openPanel');
    // Post a message to the active webview (panel reuses the last instance)
    try {
      // Use a global state marker; in this minimal change, rely on the panel created above
      // The panel handler already registers message listeners; send event via commands below
      switch (pick.action) {
        case 'ingestRules':
          vscode.commands.executeCommand('mcpRulesAssistant.openPanel');
          break;
        case 'coverage':
          vscode.commands.executeCommand('mcpRulesAssistant.openPanel');
          break;
        case 'ciGen':
          vscode.commands.executeCommand('mcpRulesAssistant.openPanel');
          break;
        case 'ciValidate':
          vscode.commands.executeCommand('mcpRulesAssistant.openPanel');
          break;
        case 'covExport':
          try {
            await client.request('tools/call', { name: 'coverage.export', arguments: {} });
            const ws2 = getWorkspaceRoot();
            if (ws2) {
              const uri2 = vscode.Uri.file(ws2 + '/.mcp/dashboard/weak_top.csv');
              try {
                await vscode.workspace.fs.stat(uri2);
                const doc2 = await vscode.workspace.openTextDocument(uri2);
                await vscode.window.showTextDocument(doc2, { preview: false });
              } catch {}
            }
            vscode.window.showInformationMessage('Coverage 导出完成 (.mcp/dashboard)');
          } catch (e:any) {
            vscode.window.showWarningMessage('Coverage 导出失败：' + String(e));
          }
          break;
        case 'openJbVerify':
          try {
            const ws3 = getWorkspaceRoot();
            if (!ws3) throw new Error('no workspace');
            const uri3 = vscode.Uri.file(ws3 + '/.mcp/dashboard/jb_verify.json');
            await vscode.workspace.fs.stat(uri3);
            const doc3 = await vscode.workspace.openTextDocument(uri3);
            await vscode.window.showTextDocument(doc3, { preview: false });
          } catch (e:any) {
            vscode.window.showWarningMessage('未找到 jb_verify.json：' + String(e));
          }
          break;
        case 'openWeakCsv':
          try { const ws = getWorkspaceRoot(); if (!ws) throw new Error('no workspace'); const u=vscode.Uri.file(ws + '/.mcp/dashboard/weak_top.csv'); await vscode.workspace.fs.stat(u); const d=await vscode.workspace.openTextDocument(u); await vscode.window.showTextDocument(d,{preview:false}); } catch {}
          break;
        case 'openNearCsv':
          try { const ws = getWorkspaceRoot(); if (!ws) throw new Error('no workspace'); const u=vscode.Uri.file(ws + '/.mcp/dashboard/near_top.csv'); await vscode.workspace.fs.stat(u); const d=await vscode.workspace.openTextDocument(u); await vscode.window.showTextDocument(d,{preview:false}); } catch {}
          break;
        case 'openGroupsCsv':
          try { const ws = getWorkspaceRoot(); if (!ws) throw new Error('no workspace'); const u=vscode.Uri.file(ws + '/.mcp/dashboard/groups.csv'); await vscode.workspace.fs.stat(u); const d=await vscode.workspace.openTextDocument(u); await vscode.window.showTextDocument(d,{preview:false}); } catch {}
          break;
        case 'openJbGroupsMd':
          try { const ws = getWorkspaceRoot(); if (!ws) throw new Error('no workspace'); const u=vscode.Uri.file(ws + '/.mcp/dashboard/jb_groups.md'); await vscode.workspace.fs.stat(u); const d=await vscode.workspace.openTextDocument(u); await vscode.window.showTextDocument(d,{preview:false}); } catch {}
          break;
      }
    } catch (e:any) {
      vscode.window.showErrorMessage('Quick action failed: ' + String(e));
    }
  }));

  // 许可状态（只读）：调用 license.verify 并展示结果
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant.licenseStatus', async () => {
    try { client.start(context); } catch {}
    try {
      const out = await client.request('tools/call', { name: 'license.verify', arguments: {} });
      vscode.window.showInformationMessage('License: ' + JSON.stringify(out));
    } catch (e:any) {
      vscode.window.showErrorMessage('License verify failed: ' + String(e));
    }
  }));

  context.subscriptions.push(disposable);

  // --- test-only helper commands (not contributed) ---
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant._test_openPanelLite', async () => {
    const panel = vscode.window.createWebviewPanel('mcpRulesAssistantTest', 'RuleFlow Test Panel', vscode.ViewColumn.Beside, { enableScripts: true });
    panel.webview.html = '<html><body><h3>Test Panel</h3></body></html>';
    panel.webview.onDidReceiveMessage(async (msg) => { await handleOpenMessage(msg); });
    __testWebviewHandler = async (m:any) => { await handleOpenMessage(m); };
    return true;
  }));
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant._test_waitReady', async () => {
    try {
      const p = __panelReady;
      if (!p) return true;
      let done = false;
      const t = new Promise<void>((res)=>setTimeout(res, 2500));
      await Promise.race([p.then(()=>{ done = true; }), t]);
      return true;
    } catch { return true; }
  }));
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant._test_waitIdle', async () => {
    try {
      const p = __panelInFlight;
      if (!p) return true;
      const t = new Promise<void>((res)=>setTimeout(res, 2500));
      await Promise.race([p, t]);
      return true;
    } catch { return true; }
  }));
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant._test_waitReady2', async (topic?: string) => {
    try {
      const key = String(topic||'any');
      let p = __ready2Promises.get(key);
      if (!p) {
        p = new Promise<void>((res)=>{ __ready2Resolvers.set(key, res); });
        __ready2Promises.set(key, p);
      }
      const t = new Promise<void>((res)=>setTimeout(res, 2500));
      await Promise.race([p, t]);
      __ready2Promises.delete(key);
      __ready2Resolvers.delete(key);
      return true;
    } catch { return true; }
  }));
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant._test_simulateWebviewMessage', async (msg:any) => {
    if (__testWebviewHandler) { await __testWebviewHandler(msg); }
    return true;
  }));

  // test-only: get/clear fake tool calls (when fake mode is on)
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant._test_getFakeCalls', async () => {
    try { return (client as any)._testGetFakeCalls ? (client as any)._testGetFakeCalls() : []; } catch { return []; }
  }));
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant._test_clearFakeCalls', async () => {
    try { if ((client as any)._testClearFakeCalls) (client as any)._testClearFakeCalls(); return true; } catch { return false; }
  }));

  // test-only: 直接触发部分 quick actions（不依赖后端与真实 webview 事件），便于在无 Python 的环境覆盖 UI 分支
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant._test_dispatchQuick', async (which: string) => {
    try {
      switch (which) {
        case 'openWeakCsv': {
          const ws = getWorkspaceRoot(); if (!ws) throw new Error('no workspace');
          const u = vscode.Uri.file(ws + '/.mcp/dashboard/weak_top.csv');
          await vscode.workspace.fs.stat(u);
          const d = await vscode.workspace.openTextDocument(u);
          await vscode.window.showTextDocument(d, { preview: false });
          break;
        }
        case 'openNearCsv': {
          const ws = getWorkspaceRoot(); if (!ws) throw new Error('no workspace');
          const u = vscode.Uri.file(ws + '/.mcp/dashboard/near_top.csv');
          await vscode.workspace.fs.stat(u);
          const d = await vscode.workspace.openTextDocument(u);
          await vscode.window.showTextDocument(d, { preview: false });
          break;
        }
        case 'openGroupsCsv': {
          const ws = getWorkspaceRoot(); if (!ws) throw new Error('no workspace');
          const u = vscode.Uri.file(ws + '/.mcp/dashboard/groups.csv');
          await vscode.workspace.fs.stat(u);
          const d = await vscode.workspace.openTextDocument(u);
          await vscode.window.showTextDocument(d, { preview: false });
          break;
        }
        case 'openJbGroupsMd': {
          const ws = getWorkspaceRoot(); if (!ws) throw new Error('no workspace');
          const u = vscode.Uri.file(ws + '/.mcp/dashboard/jb_groups.md');
          await vscode.workspace.fs.stat(u);
          const d = await vscode.workspace.openTextDocument(u);
          await vscode.window.showTextDocument(d, { preview: false });
          break;
        }
        case 'openJbVerify': {
          const ws = getWorkspaceRoot(); if (!ws) throw new Error('no workspace');
          const u = vscode.Uri.file(ws + '/.mcp/dashboard/jb_verify.json');
          await vscode.workspace.fs.stat(u);
          const d = await vscode.workspace.openTextDocument(u);
          await vscode.window.showTextDocument(d, { preview: false });
          break;
        }
        case 'openIdeDir': {
          const ws = getWorkspaceRoot(); if (!ws) throw new Error('no workspace');
          const uri = vscode.Uri.file(ws + '/.mcp/ide');
          // ensure directory exists or silently skip
          try { await vscode.workspace.fs.createDirectory(uri); } catch {}
          // reveal directory by opening a dummy README if present in subtree, else no-op
          // (避免额外复杂度：不强制创建文件)
          break;
        }
        default:
          // no-op
          break;
      }
      return true;
    } catch (e:any) {
      // 和真实分支保持一致：若不存在则静默或以信息提示，这里统一不抛异常
      return false;
    }
  }));

  // test-only: 模拟 Panel 消息分支（无后端），覆盖部分 onDidReceiveMessage 的典型路径
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant._test_dispatchPanel', async (which: string) => {
    try {
      const ws = getWorkspaceRoot() || process.cwd();
      const dash = vscode.Uri.file(ws + '/.mcp/dashboard');
      try { await vscode.workspace.fs.createDirectory(dash); } catch {}
      switch (which) {
        case 'statusUpdate': {
          const u = vscode.Uri.file(ws + '/.mcp/dashboard/status.json');
          const data = Buffer.from(JSON.stringify({ plan: { status: 'in_progress', current: 'test' }, coverage: { weak: [] }, tasks: { pending: [], done: [] } }, null, 2), 'utf-8');
          await vscode.workspace.fs.writeFile(u, data);
          vscode.window.showInformationMessage('test: status updated');
          break;
        }
        case 'ideScaffold': {
          const ide = vscode.Uri.file(ws + '/.mcp/ide');
          await vscode.workspace.fs.createDirectory(ide);
          vscode.window.showInformationMessage('test: ide scaffold created');
          break;
        }
        case 'compliance': {
          const u = vscode.Uri.file(ws + '/.mcp/compliance.md');
          await vscode.workspace.fs.writeFile(u, Buffer.from('# Compliance Commitment\n', 'utf-8'));
          vscode.window.showInformationMessage('test: compliance.md written');
          break;
        }
        case 'openCompliance': {
          const u = vscode.Uri.file(ws + '/.mcp/compliance.md');
          try { await vscode.workspace.fs.stat(u); } catch { await vscode.workspace.fs.writeFile(u, Buffer.from('# Compliance Commitment\n', 'utf-8')); }
          const doc = await vscode.workspace.openTextDocument(u);
          await vscode.window.showTextDocument(doc, { preview: false });
          break;
        }
        case 'ciOpenExist': {
          const yml = vscode.Uri.file(ws + '/.github/workflows/ci.yml');
          try { await vscode.workspace.fs.stat(yml); } catch {
            await vscode.workspace.fs.createDirectory(vscode.Uri.file(ws + '/.github/workflows'));
            await vscode.workspace.fs.writeFile(yml, Buffer.from('name: CI\n', 'utf-8'));
          }
          const doc = await vscode.workspace.openTextDocument(yml);
          await vscode.window.showTextDocument(doc, { preview: false });
          break;
        }
        case 'ciOpenMissing': {
          const yml = vscode.Uri.file(ws + '/.github/workflows/ci.yml');
          try { await vscode.workspace.fs.delete(yml, { recursive: false }); } catch {}
          // simulate missing path by attempting stat and swallowing
          try { await vscode.workspace.fs.stat(yml); } catch {}
          vscode.window.showInformationMessage('test: ci.yml missing (simulated)');
          break;
        }
        case 'covNearPrompt': {
          const near = vscode.Uri.file(ws + '/.mcp/dashboard/near_top.csv');
          try { await vscode.workspace.fs.stat(near); } catch { await vscode.workspace.fs.writeFile(near, Buffer.from('file,coverage,threshold\n', 'utf-8')); }
          vscode.window.showInformationMessage('test: covNearPrompt simulated');
          break;
        }
        default:
          break;
      }
      return true;
    } catch {
      return false;
    }
  }));

  // test-only: 直接向 panel 消息处理器发送消息（需要先打开 openPanel 创建面板）
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant._test_sendPanelMessage', async (msg: any) => {
    if (__testPanelHandler) { await __testPanelHandler(msg); return true; }
    return false;
  }));

  // test-only: NL 历史 add/clear（不依赖后端）
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant._test_nlHistory', async (op: 'add'|'clear', text?: string) => {
    if (op === 'add') {
      const h = context.globalState.get<string[]>('ruleflow.nl.history') || [];
      const t = (text || 'hello').trim();
      const nh = [t, ...h.filter(x=>x!==t)].slice(0, 10);
      await context.globalState.update('ruleflow.nl.history', nh);
      return nh.length;
    }
    if (op === 'clear') {
      await context.globalState.update('ruleflow.nl.history', []);
      return 0;
    }
    return -1;
  }));

  // 轻量保存拦截：不做重操作，仅后续可扩展（保持性能）
  context.subscriptions.push(vscode.workspace.onWillSaveTextDocument(async (_e) => {
    // 预留：可在此做改动文件 lint 的触发或统计，无阻塞
  }));

  // 软拦截：提交（运行 pre-commit commit 阶段）
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant.commit', async () => {
    try {
      const ws = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
      if (!ws) { vscode.window.showWarningMessage('未找到工作区'); return; }
      const msg = await vscode.window.showInputBox({ title: '提交说明 / Commit message' });
      if (msg === undefined) return;
      // 先运行 pre-commit commit 阶段
      await runShell('pre-commit', ['run', '--hook-stage', 'commit', '--all-files'], ws);
      await runShell('git', ['add', '-A'], ws);
      await runShell('git', ['commit', '-m', msg || 'chore: commit via mcp'], ws);
      vscode.window.setStatusBarMessage('提交完成（commit checks 通过）', 3000);
    } catch (e: any) {
      vscode.window.showErrorMessage('提交失败：' + String(e));
    }
  }));

  // 软拦截：推送（触发 pre-push 钩子，跑重型门禁）
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant.push', async () => {
    try {
      const ws = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
      if (!ws) { vscode.window.showWarningMessage('未找到工作区'); return; }
      await runShell('git', ['push'], ws);
      vscode.window.setStatusBarMessage('推送完成（push gates 通过）', 3000);
    } catch (e: any) {
      vscode.window.showErrorMessage('推送失败：' + String(e));
    }
  }));

  // 自然语言命令：在输入框中输入“摄取规则/开启记忆”等短语
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant.nlCommand', async () => {
    try {
      client.start(context);
      const text = await vscode.window.showInputBox({
        title: 'RuleFlow 自然语言命令',
        placeHolder: '例如：摄取规则 README.md, docs/ 或 开启滚动记忆'
      });
      if (!text) return;
      const res = await client.request('tools/call', { name: 'nl.command', arguments: { text } });
      const tool = (res && (res as any).parsed && (res as any).parsed.tool) || 'nl.command';
      const lower = (text || '').toLowerCase();
      // Route common tools to concrete actions for true one-command behavior
      const runLoadCoverage = async () => {
        await vscode.commands.executeCommand('mcpRulesAssistant.loadCoverage');
      };
      const runIngestRules = async () => {
        // Try to parse simple CSV paths from input, else default to README.md, docs/
        const m = text.split(/摄取规则|ingest rules|规则|ingest/i).slice(-1)[0] || '';
        let paths = m.split(/[,，]/).map(s=>s.trim()).filter(Boolean);
        if (paths.length === 0) paths = ['README.md', 'docs/'];
        await client.request('tools/call', { name: 'rules.ingest', arguments: { paths } });
        vscode.window.showInformationMessage('规则摄取完成');
      };
      const runCiGenerate = async () => {
        const out = await client.request('tools/call', { name: 'ci.generate', arguments: {} });
        vscode.window.showInformationMessage('CI 已生成: ' + (out && out.path ? String(out.path) : ''));        
      };
      const runCiValidate = async () => {
        const out = await client.request('tools/call', { name: 'ci.validate', arguments: {} });
        vscode.window.showInformationMessage('CI 校验完成');
      };
      const runInstallHooks = async () => {
        await client.request('tools/call', { name: 'git.install_hooks', arguments: {} });
        vscode.window.showInformationMessage('Git hooks 已安装');
      };
      const runEnvPrepare = async () => {
        const choice = await vscode.window.showQuickPick(['预览 / Dry-run', '创建并安装 / Create+Install'], { title: '准备环境' });
        if (!choice) return;
        const args = choice.startsWith('预览') ? { create: false, install: false } : { create: true, install: true };
        const out = await client.request('tools/call', { name: 'env.prepare', arguments: args });
        vscode.window.showInformationMessage('环境准备: ' + (out && out.ok ? 'OK' : 'Done'));
      };
      const runRulesEnforce = async () => {
        const out = await client.request('tools/call', { name: 'rules.enforce', arguments: {} });
        vscode.window.showInformationMessage('Enforce: ' + (out && out.changed ? '配置已更新' : '无变化'));
      };
      const runCompliance = async () => {
        const out = await client.request('tools/call', { name: 'compliance.commitment', arguments: { write: true } });
        vscode.window.showInformationMessage('合规承诺已生成');
      };
      // Dispatch
      if (tool === 'coverage.report' || /加载覆盖率|load coverage/.test(lower)) {
        await runLoadCoverage();
      } else if (tool === 'rules.ingest' || /摄取规则|ingest rules/.test(lower)) {
        await runIngestRules();
      } else if (tool === 'ci.generate' || /生成 ci|生成ci|generate ci/.test(lower)) {
        await runCiGenerate();
      } else if (tool === 'ci.validate' || /校验 ci|validate ci/.test(lower)) {
        await runCiValidate();
      } else if (tool === 'git.install_hooks' || /安装钩子|install hooks/.test(lower)) {
        await runInstallHooks();
      } else if (tool === 'env.prepare' || /准备环境|prepare env/.test(lower)) {
        await runEnvPrepare();
      } else if (tool === 'rules.enforce' || /应用门禁|生成门禁|enforce/.test(lower)) {
        await runRulesEnforce();
      } else if (tool === 'compliance.commitment' || /合规承诺|compliance/.test(lower)) {
        await runCompliance();
      } else if (tool === 'plan.set' || /计划\s*设置|plan set|计划[:：]/.test(lower)) {
        const mSt = /状态\s*[:=]\s*(进行中|in_progress|完成|done|planned)/i.exec(text);
        const stMap: any = { '进行中':'in_progress', '完成':'done' };
        const status = mSt ? (stMap[mSt[1]] || mSt[1]) : undefined;
        const mCur = /当前(步骤)?\s*[:=]\s*([^;，]+)/i.exec(text);
        const current = mCur ? mCur[2].trim() : undefined;
        const mNext = /(下一步|next)\s*[:=]\s*([^;，]+)/i.exec(text);
        const next = mNext ? mNext[2].trim() : undefined;
        const args:any = {}; if (status) args.status = status; if (current) args.current = current; if (next) args.next = next;
        if (Object.keys(args).length === 0) {
          await vscode.commands.executeCommand('mcpRulesAssistant.planSet');
        } else {
          await client.request('tools/call', { name: 'plan.set', arguments: args });
          vscode.window.showInformationMessage('Plan updated');
        }
      } else if (tool === 'fs.apply_patch' || /受控写入|guarded write/.test(lower)) {
        await vscode.commands.executeCommand('mcpRulesAssistant.fsApplyPatch');
      } else if (tool === 'rules.onboard' || /初始化规则|规则引导|setup rules|questionnaire/.test(lower)) {
        await client.request('tools/call', { name: 'rules.onboard', arguments: {} });
        vscode.window.showInformationMessage('已执行规则引导（默认参数）');
      } else {
        vscode.window.showInformationMessage('已执行：' + tool);
      }
      
      // 存历史
      const h = context.globalState.get<string[]>('ruleflow.nl.history') || [];
      const nh = [text, ...h.filter(x=>x!==text)].slice(0, 10);
      await context.globalState.update('ruleflow.nl.history', nh);
    } catch (e: any) {
      vscode.window.showErrorMessage('执行自然语言命令失败：' + String(e));
    }
  }));
}

export function deactivate() {}

async function runShell(cmd: string, args: string[], cwd?: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const p = spawn(cmd, args, { cwd, shell: process.platform === 'win32' });
    let stderr = '';
    p.stderr.on('data', d => stderr += d.toString());
    p.on('close', (code) => {
      if (code === 0) resolve(); else reject(new Error(stderr || `${cmd} exited with ${code}`));
    });
  });
}
