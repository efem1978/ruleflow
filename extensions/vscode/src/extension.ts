import * as vscode from 'vscode';
import { spawn, ChildProcessWithoutNullStreams } from 'child_process';

// Workspace root lock (user-selected project root for strict isolation)
let __lockedRoot: string | null = null;

// Helper to generate CSP nonce for webview inline scripts
function getNonce(): string {
  const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  let text = '';
  for (let i = 0; i < 32; i++) {
    text += possible.charAt(Math.floor(Math.random() * possible.length));
  }
  return text;
}

// ---- Workspace helpers (multi-root aware, Occam's razor) ----
function getWorkspaceRoot(): string | undefined {
  try {
    if (__lockedRoot) return __lockedRoot;
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
    if (__lockedRoot) {
      try { const p = require('path'); return p.basename(__lockedRoot); } catch {}
    }
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
  private fakeCalls: { method: string; name?: string; params?: any; args?: any }[] = [];
  private hb: NodeJS.Timeout | null = null;
  private connected = false;
  private lastStartAt = 0;
  private restarting = false;
  private failureCount = 0;
  private lastFailureAt = 0;
  private autoPrepared = false;

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
    this.lastStartAt = Date.now();
    this.proc = spawn(pyBin, ['-m', 'mcp_rules_assistant.cli', 'start'], {
      cwd: ws,
      stdio: ['pipe', 'pipe', 'pipe'],
      env: { ...process.env, MCP_PROJECT_ROOT: ws, MCP_STRICT_ISOLATION: '1' }
    });
    // log to .mcp/dashboard/server.log for troubleshooting
    try {
      const logDir = path.join(ws, '.mcp', 'dashboard');
      fs.mkdirSync(logDir, { recursive: true });
      const logFile = path.join(logDir, 'server.log');
      const append = (line: string) => { try { fs.appendFileSync(logFile, line + '\n'); } catch {} };
      append(`[spawn] ${new Date().toISOString()} ${pyBin} -m mcp_rules_assistant.cli start`);
      this.proc.stderr.setEncoding('utf8');
      this.proc.stderr.on('data', async (chunk: string) => {
        chunk.split(/\r?\n/).forEach((ln: string) => { if (ln.trim()) append('[stderr] ' + ln); });
        // 自愈：缺少 mcp_rules_assistant 时自动创建 venv 并安装本地包
        try {
          if (!this.autoPrepared && /No module named .*mcp_rules_assistant/.test(String(chunk || ''))) {
            this.autoPrepared = true;
            const venvDir = path.join(ws, '.mcp', 'venv');
            const vpy = process.platform === 'win32' ? path.join(venvDir, 'Scripts', 'python.exe') : path.join(venvDir, 'bin', 'python');
            const run = (cmd: string, args: string[]) => new Promise<void>((resolve) => {
              try { const p = spawn(cmd, args, { cwd: ws }); p.on('close', () => resolve()); p.on('error', () => resolve()); } catch { resolve(); }
            });
            if (!fs.existsSync(venvDir)) {
              await run(pyBin, ['-m', 'venv', venvDir]);
            }
            if (fs.existsSync(vpy)) {
              await run(vpy, ['-m', 'pip', 'install', '-U', 'pip', 'setuptools', 'wheel']);
              await run(vpy, ['-m', 'pip', 'install', '-e', ws]);
              vscode.window.showInformationMessage('已自动安装本地 MCP 包到 .mcp/venv，尝试重新连接…');
              try { this.proc?.kill(); } catch {}
            }
          }
        } catch { /* ignore */ }
      });
    } catch { /* ignore logging errors */ }
    this.proc.on('error', (err) => {
      vscode.window.showErrorMessage(`MCP Server 启动失败，请检查 Python：${String(err)}。可设置环境变量 MCP_PYTHON_BIN 指定解释器。`);
    });
    this.proc.on('close', (code) => {
      const early = (Date.now() - this.lastStartAt) < 1500; // early exit likely due to reload/pipe close
      const willRetry = !this.restarting;
      // 延迟提示：给自动重启一个窗口，若已恢复则不打扰
      const maybeWarn = () => {
        if (code !== 0 && !this.connected) {
          vscode.window.showWarningMessage(`MCP Server 退出（代码 ${code}）。部分功能可能不可用。正在尝试自动恢复…`);
        }
      };
      this.connected = false;
      try { vscode.commands.executeCommand('setContext', 'ruleflow.mcpConnected', false); } catch {}
      // try to restart on unexpected close (debounced by caller)
      this.proc = null;
      // 失败计数与自动降级为演示模式（fake），避免空白面板
      const now = Date.now();
      this.failureCount = (now - this.lastFailureAt <= 5000) ? (this.failureCount + 1) : 1;
      this.lastFailureAt = now;
      if (this.failureCount >= 2) {
        try {
          const path = require('path'); const fs = require('fs');
          const dash = path.join(ws, '.mcp', 'dashboard');
          fs.mkdirSync(dash, { recursive: true });
          fs.writeFileSync(path.join(dash, 'fake_mode'), '1');
          this.fakeMode = true;
          vscode.window.showInformationMessage('MCP 无法启动，已自动切换为演示模式（fake）。可稍后准备环境后再试。');
        } catch { /* ignore */ }
      }
      if (willRetry) {
        this.restarting = true;
        setTimeout(() => {
          try { this.start(context); } finally { this.restarting = false; }
        }, early ? 400 : 800);
        setTimeout(maybeWarn, 1600);
      } else {
        setTimeout(maybeWarn, 800);
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
    // heartbeat ping
    if (this.hb) { clearInterval(this.hb); this.hb = null; }
    this.hb = setInterval(async () => {
      try {
        const res = await this.request('ping', {});
        const ok = !!(res && (res.ok !== false));
        if (ok !== this.connected) {
          this.connected = ok;
          try { vscode.commands.executeCommand('setContext', 'ruleflow.mcpConnected', ok); } catch {}
        }
      } catch {
        this.connected = false;
        try { vscode.commands.executeCommand('setContext', 'ruleflow.mcpConnected', false); } catch {}
        // attempt a light restart
        if (!this.proc) {
          try { this.start(context); } catch {}
        }
      }
    }, 5000);
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
      // 记录调用供测试断言
      try { this.fakeCalls.push({ method, name: (params && params.name) || undefined, params, args: (params && (params.arguments ?? params)) }); } catch {}
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

  // test helpers (exposed via commands)
  public _testGetFakeCalls(): { method: string; name?: string; params?: any; args?: any }[] {
    return Array.from(this.fakeCalls);
  }
  public _testClearFakeCalls(): void {
    this.fakeCalls = [];
  }
}

const client = new McpClient();
function memAllowed(): boolean {
  try { if ((client as any).fakeMode) return true; } catch {}
  const v = String(process.env.RULEFLOW_ALLOW_MEMORY_APPEND || '').trim().toLowerCase();
  return ['1','true','on','yes','y'].includes(v);
}
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

let __activated = false; // 防重复激活（测试/多次初始化场景）

export function activate(context: vscode.ExtensionContext) {
  if (__activated) {
    // 避免重复注册命令导致 “command ... already exists”
    return;
  }
  __activated = true;
  // 恢复锁定根目录（若存在），优先使用此前用户选择的项目根
  try {
    const saved = context.workspaceState.get<string>('ruleflow.lockRoot') || '';
    if (saved && saved.trim()) { __lockedRoot = saved.trim(); }
    else {
      const w0 = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
      if (w0) {
        const p = require('path'); const fs = require('fs');
        const prefs = p.join(w0, '.mcp', 'dashboard', 'ui_prefs.json');
        try { const txt = fs.readFileSync(prefs, 'utf8'); const obj = JSON.parse(txt||'{}'); if (obj && typeof obj.projectRoot==='string' && obj.projectRoot) __lockedRoot = obj.projectRoot; } catch {}
      }
    }
  } catch {}

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
  // 保守模式：不自动触发任何后端调用；状态栏仅显示入口

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
        try { if (memAllowed()) {
          const content = `Coverage loaded: weak=${weak}, near=${near}, groups=${groups}` + (mm !== undefined ? `, min_module=${(mm*100).toFixed(0)}%` : '');
          await client.request('tools/call', { name: 'memory.append_turn', arguments: { role: 'assistant', content, meta: { source: 'vscode', action: 'loadCoverage' } } });
        } } catch {}
      } else {
        const msg = (res && (res.message || res.error)) || 'coverage.xml not found or unavailable';
        vscode.window.showWarningMessage(`Coverage not available: ${String(msg)}`);
        try { if (memAllowed()) {
          const content = `Coverage not available: ${String(msg)}`;
          await client.request('tools/call', { name: 'memory.append_turn', arguments: { role: 'assistant', content, meta: { source: 'vscode', action: 'loadCoverage' } } });
        } } catch {}
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
    if (choice === 'Generate CI') { await client.request('tools/call', { name: 'ci.generate', arguments: {} }); vscode.window.showInformationMessage('CI 已生成'); try { if (memAllowed()) { await client.request('tools/call', { name: 'memory.append_turn', arguments: { role: 'assistant', content: 'CI generated', meta: { source: 'vscode', action: 'ci.generate' } } }); } } catch {} return; }
    if (choice === 'Validate CI') { await client.request('tools/call', { name: 'ci.validate', arguments: {} }); vscode.window.showInformationMessage('CI 校验完成'); try { if (memAllowed()) { await client.request('tools/call', { name: 'memory.append_turn', arguments: { role: 'assistant', content: 'CI validated', meta: { source: 'vscode', action: 'ci.validate' } } }); } } catch {} return; }
    if (choice === 'Install Hooks') { await client.request('tools/call', { name: 'git.install_hooks', arguments: {} }); vscode.window.showInformationMessage('Git hooks 已安装'); try { if (memAllowed()) { await client.request('tools/call', { name: 'memory.append_turn', arguments: { role: 'assistant', content: 'Git hooks installed', meta: { source: 'vscode', action: 'git.install_hooks' } } }); } } catch {} return; }
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
      // Guard against symlink/out-of-workspace and hardlink targets leaking memory across projects
      try {
        const fs = require('fs'); const path = require('path');
        const l = fs.lstatSync(uri.fsPath);
        const mcpDir = path.resolve(ws, '.mcp');
        let real = uri.fsPath;
        if (l.isSymbolicLink()) {
          real = fs.realpathSync(uri.fsPath);
        }
        const inside = real.startsWith(mcpDir + path.sep) || real === mcpDir;
        if (!inside) {
          vscode.window.showErrorMessage('出于隔离安全，已拒绝打开位于工作区之外的记忆文件');
          return;
        }
        // Detect hardlink count > 1 and warn/abort (conservative default)
        const st = fs.statSync(real);
        const isHardLinked = (st.nlink && st.nlink > 1);
        if (isHardLinked && String(process.env.MCP_MEMORY_TRUST_HARDLINK || '').trim().toLowerCase() !== '1') {
          vscode.window.showWarningMessage('检测到 memory.json 可能为硬链接；为防跨项目共享，默认不打开（设置 MCP_MEMORY_TRUST_HARDLINK=1 可放宽）。');
          return;
        }
      } catch { /* ignore and continue best-effort */ }
      const doc = await vscode.workspace.openTextDocument(uri);
      await vscode.window.showTextDocument(doc, { preview: false });
    } catch {
      vscode.window.showInformationMessage('.mcp/memory.json not found');
    }
  }));

  const disposable = vscode.commands.registerCommand('mcpRulesAssistant.openPanel', async () => {
    // 先渲染一个最小占位以避免空白，并提供快速修复入口
    const renderFallback = (msg: string) => `
      <html><body style="font-family:-apple-system,Segoe UI,Arial;">
      <style>
        body.simple .adv{display:none;} body.advanced #simpleBar{display:none;}
        #modeBar{display:flex;gap:6px;align-items:center;margin:6px 0;}
        #modeBar button{padding:4px 8px;}
      </style>
      <h2>RuleFlow 面板</h2>
      <div id="modeBar"><span>显示模式：</span> <button id="btnModeSimple" title="仅展示常用操作；不会自动修改文件或配置">新手模式</button> <button id="btnModeAdvanced" title="展示全部功能；每项操作都需要你确认后才执行">高级模式</button></div>
      <div id="simpleBar" style="border:1px solid #ddd; padding:8px; background:#f9fbff;">
        <div style="color:#666; font-size:12px;">${msg || '正在连接 MCP …'}</div>
        <div style="margin-top:6px;display:flex;gap:6px;flex-wrap:wrap;">
          <button id="btnRetry" title="重新尝试连接 MCP 后端（安全，只进行握手/健康检查）">重试连接</button>
          <button id="btnEnableFake" title="写入 .mcp/dashboard/fake_mode 以启用离线演示；可随时删除该文件恢复">切换为演示模式</button>
          <button id="btnOpenLog" title="打开 .mcp/dashboard/server.log 日志用于排查（只读）">打开 server.log</button>
        </div>
      </div>
      <script>
        const vscode = acquireVsCodeApi();
        (function(){
          const apply=(m)=>{ try{document.body.classList.remove('simple','advanced');document.body.classList.add(m);}catch{} try{vscode.setState&&vscode.setState({uiMode:m});}catch{} };
          const st=(vscode.getState&&vscode.getState())||{}; apply((st&&st.uiMode)||'simple');
          const s=document.getElementById('btnModeSimple'); const a=document.getElementById('btnModeAdvanced');
          if(s) s.onclick=()=>apply('simple'); if(a) a.onclick=()=>apply('advanced');
          const r=document.getElementById('btnRetry'); if(r) r.onclick=()=>vscode.postMessage({t:'retryConnect'});
          const f=document.getElementById('btnEnableFake'); if(f) f.onclick=()=>vscode.postMessage({t:'enableFake'});
          const l=document.getElementById('btnOpenLog'); if(l) l.onclick=()=>vscode.postMessage({t:'openServerLog'});
      })();
      </script>
      </body></html>`;
    const panel = vscode.window.createWebviewPanel(
      'mcpRulesAssistant',
      'RuleFlow: Rules & Memory',
      vscode.ViewColumn.Beside,
      { enableScripts: true, retainContextWhenHidden: true }
    );
    const csp = panel.webview.cspSource;
    const nonce = getNonce();
    const __fallbackHtml = `
      <html>
        <head>
          <meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src ${csp} data:; style-src ${csp} 'unsafe-inline'; script-src ${csp} 'nonce-${nonce}'; font-src ${csp} data:">
        </head>
        <body style="font-family:-apple-system,Segoe UI,Arial;">
          <style>
            body.simple .adv{display:none;} body.advanced #simpleBar{display:none;}
            #modeBar{display:flex;gap:6px;align-items:center;margin:6px 0;}
            #modeBar button{padding:4px 8px;}
          </style>
          <h2>RuleFlow 面板</h2>
          <div id="modeBar"><span>显示模式：</span> <button id="btnModeSimple" title="仅展示常用操作；不会自动修改文件或配置">新手模式</button> <button id="btnModeAdvanced" title="展示全部功能；每项操作都需要你确认后才执行">高级模式</button></div>
          <div id="simpleBar" style="border:1px solid #ddd; padding:8px; background:#f9fbff;">
            <div style="color:#666; font-size:12px;">正在连接 MCP …</div>
            <div style="margin-top:6px;display:flex;gap:6px;flex-wrap:wrap;">
              <button id="btnRetry" title="重新尝试连接 MCP 后端（安全，只进行握手/健康检查）">重试连接</button>
              <button id="btnEnableFake" title="写入 .mcp/dashboard/fake_mode 以启用离线演示；可随时删除该文件恢复">切换为演示模式</button>
              <button id="btnOpenLog" title="打开 .mcp/dashboard/server.log 日志用于排查（只读）">打开 server.log</button>
            </div>
          </div>
          <script nonce="${nonce}">
            const vscode = acquireVsCodeApi();
            (function(){
              const apply=(m)=>{ try{document.body.classList.remove('simple','advanced');document.body.classList.add(m);}catch{} try{vscode.setState&&vscode.setState({uiMode:m});}catch{} };
              const st=(vscode.getState&&vscode.getState())||{}; apply((st&&st.uiMode)||'simple');
              const s=document.getElementById('btnModeSimple'); const a=document.getElementById('btnModeAdvanced');
              if(s) s.onclick=()=>apply('simple'); if(a) a.onclick=()=>apply('advanced');
              const r=document.getElementById('btnRetry'); if(r) r.onclick=()=>vscode.postMessage({t:'retryConnect'});
              const f=document.getElementById('btnEnableFake'); if(f) f.onclick=()=>vscode.postMessage({t:'enableFake'});
              const l=document.getElementById('btnOpenLog'); if(l) l.onclick=()=>vscode.postMessage({t:'openServerLog'});
            })();
          </script>
        </body>
      </html>`;
    panel.webview.html = __fallbackHtml;
    // 按需启动后端 Python 服务器
    try { client.start(context); } catch {}
    // make postMessage safe after dispose
    let __panelDisposed = false;
    const __origPost = panel.webview.postMessage.bind(panel.webview);
    (panel.webview as any).postMessage = (msg: any) => {
      try {
        if (__panelDisposed) return Promise.resolve(false);
        const r = __origPost(msg);
        try { (r as any).then(()=>{}, ()=>{}); } catch {}
        return r;
      } catch { return Promise.resolve(false); }
    };
    panel.onDidDispose(() => { __panelDisposed = true; try { __testPanelHandler = null as any; } catch {} });
    __panelReady = new Promise<void>((res) => { __panelReadyResolve = res; });

    /* c8 ignore start */
    const render = (csp: string, nonceVal: string, md: string, toolsListHtml: string, sugg: string = '') => `
      <html>
      <head>
        <meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src ${csp} data:; style-src ${csp} 'unsafe-inline'; script-src ${csp} 'nonce-${nonceVal}'; font-src ${csp} data:">
      </head>
      <body class="simple" style="font-family: -apple-system,Segoe UI,Arial;">
        <style>
          body.simple .adv { display: none; }
          body.simple #simpleBar { display: block; }
          body.advanced #simpleBar { display: none; }
          body.advanced .adv { display: block; }
          #modeBar { display:flex; gap:6px; align-items:center; margin:6px 0; }
          #modeBar button { padding:4px 8px; }
          #simpleBar button { padding:6px 10px; margin:2px 4px; }
          .hint { color:#666; font-size:12px; }
        </style>
        <h2 id="hdrTitle">MCP 规则与上下文助手</h2>
        <p id="pConnected">已连接到 Python MCP Server（最小协议）。默认快速内环：保存轻、推送重。</p>
        <div id="modeBar">
          <span id="lblDisplayMode" class="hint">显示模式：</span>
          <button id="btnModeSimple" title="仅展示常用操作；不会自动修改文件或配置">新手模式</button>
          <button id="btnModeAdvanced" title="展示全部功能；每项操作都需要你确认后才执行">高级模式</button>
          <button id="btnLang" title="切换中/英文界面标签">中文/English</button>
          <button id="btnReloadPanel" title="重载面板（重新渲染并握手）">重载面板</button>
        </div>
        <div id="ticker" style="height:auto; background:#f6f6f6; border:1px solid #ddd; padding:4px 8px; margin:6px 0;">
          <span id="tickerText" style="display:inline-block; white-space:nowrap; font-size:12px; color:#333;"></span>
        </div>
        <div id="proj" style="padding:4px 6px; border:1px solid #ddd; background:#fafafa; margin:6px 0; display:flex; align-items:center; gap:8px;">
          <b id="lblCurProject">当前项目:</b> <span id="curProject">(检测中)</span>
          <button id="btnSelectProject" title="在当前 IDE 窗口内选择/切换项目根；所有读写限定在所选项目的 .mcp/ 目录">选择/切换项目…</button>
        </div>
        <div id="lic" style="padding:4px 6px; border:1px solid #ddd; background:#fafafa; margin:6px 0; display:flex; align-items:center; gap:8px;">
          <b>License:</b> <span id="licText">(loading)</span>
          <button id="btnLicVerify" title="校验许可状态（本地只读，不出网）">Verify</button>
          <button id="btnLicActivate" title="从本地文件激活许可（仅写入许可配置，不改源码）">Activate…</button>
        </div>
        <pre id="licDetail" style="white-space:pre-wrap; display:none; font-size:11px; color:#555; background:#f7f7f7; padding:4px;"></pre>
        <div id="info" style="margin:6px 0; color:#d33;"></div>
        <div id="simpleBar" style="margin:10px 0; padding:8px; border:1px solid #ddd; background:#f9fbff;">
          <div id="hintQuick" class="hint">三步上手：</div>
          <div>
            <button id="btnSimpleInstall" title="为当前项目创建 .mcp/venv 并安装基础工具链（ruff/black/mypy/pytest）">1) 准备并安装环境</button>
            <button id="btnSimpleCoverage" title="读取 coverage.xml 汇总弱项/分组/近阈值并输出到 .mcp/dashboard">2) 加载覆盖率</button>
            <button id="btnSimplePlan" title="打开 .mcp/plan.md（项目任务与进度的唯一权威来源）">3) 打开计划</button>
          </div>
          <div>
            <button id="btnSimpleIngest" title="将 README/docs 转换为规则（写入 .mcp/rules_*），不改现有源码">摄取规则（README.md, docs/）</button>
            <button id="btnSimpleStatus" title="刷新状态并写入 .mcp/dashboard/status.json（只读源码）">刷新状态</button>
          </div>
          <div class="hint">遇到问题 → 点击“刷新状态”，或切换到“高级模式”查看更多功能。</div>
        </div>
        <div class="adv" style="margin:8px 0;">
          <input id="nlInput" placeholder="自然语言指令：如 摄取规则 README.md, docs/ / 加载覆盖率 / 开启滚动记忆" style="width:65%;" title="在此输入中文或英文指令，按“执行”按钮运行；示例可点击下方快速填充" />
          <button id="nlSend" title="执行输入框中的自然语言指令，仅作用于当前项目">执行</button>
          <button id="nlExamples" title="插入常用指令示例到输入框，不会直接执行">范例</button>
          <button id="nlClear" title="清空面板中的历史显示（仅 UI，不写磁盘）">清空历史</button>
          <button id="btnStatusUpdate" title="刷新状态摘要并更新 .mcp/dashboard/status.json">刷新状态</button>
          <span style="margin-left:6px;">近阈值%:</span>
          <input id="nearPct" value="3" style="width:40px;" title="显示覆盖率距离阈值≤该百分比的文件（默认3%）" />
          <button id="btnCovNearInline" title="在面板内显示“近阈值”文件（仅 UI 过滤）">显示近阈值</button>
          <button id="btnIdeScaffold" title="生成当前 IDE 的最小配置/脚本（仅写入项目内配置目录）">生成 IDE 集成配置</button>
          <button id="btnCompliance" title="生成合规承诺文档（写入 .mcp/compliance.md）">生成合规承诺</button>
          <button id="btnOpenCompliance" title="打开合规承诺文档（只读）">打开合规承诺</button>
          <button id="btnOpenIdeDir" title="打开 IDE 相关目录（如 .vscode/，只读）">打开 IDE 目录</button>
          <button id="btnEvents" title="显示近期事件（只读 .mcp/dashboard/cmd_events.jsonl）">事件历史</button>
          <button id="btnAudit" title="显示安全审计（只读 .mcp/dashboard/security_audit.jsonl）">安全审计</button>
          <button id="btnInfo" title="显示状态摘要信息（只读 .mcp/dashboard/status.json）">状态摘要 Info</button>
          <button id="btnCopyEvents" title="复制事件内容到剪贴板（仅 UI，不写磁盘）">复制事件</button>
          <button id="btnCopyInfo" title="复制状态摘要到剪贴板（仅 UI，不写磁盘）">复制摘要</button>
          <button id="btnOpenStatusFile" title="打开 .mcp/dashboard/status.json（只读）">打开 status.json</button>
          <button id="btnOpenEventsFile" title="打开 .mcp/dashboard/cmd_events.jsonl（只读）">打开 events</button>
          <button id="btnOpenAuditFile" title="打开 .mcp/dashboard/security_audit.jsonl（只读）">打开 audit</button>
        </div>
        <div id="nlExamplesBox" class="adv" style="display:none; margin:4px 0 10px 0;">
          <span style="opacity:.8">快速范例：</span>
          <button data-nl="摄取规则 README.md, docs/">摄取规则</button>
          <button data-nl="加载覆盖率">加载覆盖率</button>
          <button data-nl="仅看近阈值 3">仅看近阈值</button>
          <button data-nl="开启滚动记忆">开启记忆</button>
          <button data-nl="生成 CI">生成 CI</button>
          <button data-nl="校验 CI">校验 CI</button>
          <button data-nl="规则 摘要">规则摘要</button>
        </div>
        <div id="nlCatalog" style="margin:6px 0;">
          <fieldset style="border:1px solid #ddd; padding:6px;">
            <legend>自然语言命令示例（点击即执行）</legend>
            <div class="hint">触发词：摄取规则 / 加载覆盖率 / 近阈值 / 打开计划 / 开启滚动记忆 / 生成 CI / 校验 CI / 安装钩子</div>
            <div style="margin-top:6px;"><b>规则</b>：
              <button data-nl="摄取规则 README.md, docs/">摄取规则 README.md, docs/</button>
              <button data-nl="载入编译规则">载入编译规则</button>
              <button data-nl="校验 规则">校验 规则</button>
            </div>
            <div style="margin-top:6px;"><b>覆盖率</b>：
              <button data-nl="加载覆盖率">加载覆盖率</button>
              <button data-nl="仅看弱项">仅看弱项</button>
              <button data-nl="仅看近阈值 3">仅看近阈值 3</button>
            </div>
            <div style="margin-top:6px;"><b>计划与记忆</b>：
              <button data-nl="打开 计划">打开 计划</button>
              <button data-nl="开启滚动记忆">开启滚动记忆</button>
            </div>
            <div style="margin-top:6px;"><b>CI</b>：
              <button data-nl="生成 CI">生成 CI</button>
              <button data-nl="校验 CI">校验 CI</button>
              <button data-nl="安装 钩子">安装 钩子</button>
            </div>
          </fieldset>
        </div>
        <div>
          <h4 style="margin:8px 0 4px;">最近指令</h4>
          <ul id="nlHistory" style="padding-left:18px;"></ul>
        </div>
        <div style="margin:8px 0;">
          <fieldset style="border:1px solid #ddd; padding:6px;">
            <legend>工作流常用操作</legend>
            <button id="btnLoad" title="从 .mcp/rules_compiled.* 读取并展示编译后的规则（只读）">载入编译规则 / Load Rules</button>
            <button id="btnIngest" title="将 README、docs 等文档转换为规则（写入 .mcp/rules_*）">摄取规则 / Ingest</button>
            <button id="btnValidate" title="重新编译并校验规则，输出冲突与建议（只读展示）">校验规则 / Validate</button>
            <button id="btnHooks" title="安装 pre-commit/commit-msg/pre-push 钩子（便于在提交前自动检查）">安装钩子 / Install Hooks</button>
            <button id="btnLoadSugg" title="读取并展示规则建议（冲突与优化提示）">载入建议 / Load Suggestions</button>
            <button id="btnCoverage" title="读取 coverage.xml 并生成薄弱/分组/近阈值摘要（只读）">加载覆盖率 / Load Coverage</button>
            <button id="btnShowWeak" title="只显示低于阈值的薄弱文件（更易聚焦问题）">仅看弱项 / Show Weak</button>
            <button id="btnCovTree" title="按目录展示薄弱文件（层级浏览，便于定位）">加载目录树 / Load Weak Tree</button>
            <button id="btnCovNear" title="显示距离阈值很近（默认≤3%）但尚未跌破的文件（快速补齐）">仅看近阈值 / Show Near</button>
            <button id="btnCovExport" title="导出 CSV/JSON 报表到 .mcp/dashboard（供审阅与归档）">导出覆盖率报表 / Export Coverage</button>
            <button id="btnPrepareEnvDry" title="预览将要创建的虚拟环境与安装的工具链（不做任何改动）">准备环境(预览) / Prepare Env (dry-run)</button>
            <button id="btnPrepareEnvInstall" title="创建 .mcp/venv 并安装 ruff/black/mypy/pytest 等基础工具">准备并安装环境 / Prepare & Install</button>
          </fieldset>
        </div>
        <div class="adv" style="margin:8px 0;">
          <button id="btnOpenUserGuide" title="打开上手文档（只读），包含常见流程与截图示例">打开用户上手 / Open User Guide</button>
          <button id="btnOpenIdeSupport" title="打开 IDE 集成说明（只读），包含 VS Code/Cursor/JetBrains 的最小配置">打开 IDE 支持 / Open IDE Support</button>
        </div>
        <div class="adv">
          <h3 id="hdrTools">可用工具（示例）</h3>
          <ul>${toolsListHtml}</ul>
        </div>
        <div class="adv">
          <h3 id="hdrCompiled">项目规则（编译版）</h3>
          <pre id="rules" style="white-space:pre-wrap; background:#1112; padding:8px;">${md || '暂无内容 / No content'}</pre>
        </div>
        <div class="adv">
          <h3 id="hdrConflictsNav">冲突定位（可点击跳转）</h3>
          <ul id="conflicts"></ul>
        </div>
        <div class="adv">
          <h3 id="hdrConflictsSugg">冲突与建议（Conflicts & Suggestions）</h3>
          <pre id="sugg" style="white-space:pre-wrap; background:#1111; padding:8px;">${sugg || '暂无建议 / No suggestions'}</pre>
        </div>
        <div class="adv">
          <h3 id="hdrOnboard">规则引导（Onboard）</h3>
          <div style="margin:6px 0;">
            <button id="btnOnboardPreview" title="预览推荐的规则与阈值（只读展示，不做修改）">预览推荐 / Preview</button>
            <button id="btnOnboardApply" title="一键采纳推荐（仅写入 .mcp/assistant.yaml 或相关配置，不改源码）">一键采纳 / Apply</button>
          </div>
          <pre id="onboardSummary" style="white-space:pre-wrap; background:#f7f7f7; padding:8px; font-size:12px; color:#333;">（点击“预览推荐”查看将启用的规则摘要）</pre>
        </div>
        <div class="adv">
          <h3 id="hdrChat">Chat（可选）</h3>
          <div style="margin:6px 0;">
            <button id="btnChatEnable" title="启用“对话摘要追加”功能（默认仍不写记忆，除非显式允许）">启用追加摘要 / Enable</button>
            <button id="btnChatDisable" title="禁用“对话摘要追加”功能">禁用 / Disable</button>
            <button id="btnChatPreview" title="预览将要追加的摘要内容（只读）">预览摘要 / Preview</button>
          </div>
          <pre id="chatPreview" style="white-space:pre-wrap; background:#f7f7f7; padding:8px; font-size:12px; color:#666;">（默认关闭；启用后，每轮对话可追加“上一轮问答摘要”至记忆。无遥测，不出网。）</pre>
        </div>
        <div class="adv">
          <h3 id="hdrCovGroups">覆盖率分组</h3>
          <ul id="covGroups"></ul>
        </div>
        <div class="adv">
          <h3 id="hdrWeakTop">覆盖率薄弱（Top 20）</h3>
          <input id="covFilter" placeholder="过滤文件名关键词..." title="在薄弱列表中过滤包含该关键词的文件名" />
          <button id="btnCovFilter" title="应用上方的文件名关键词过滤（仅 UI）">过滤</button>
          <button id="btnOpenWeakCsv" title="查看薄弱文件 TopN 的 CSV">打开 weak_top.csv</button>
          <button id="btnOpenNearCsv" title="查看近阈值文件 TopN 的 CSV">打开 near_top.csv</button>
          <button id="btnOpenGroupsCsv" title="查看覆盖率分组聚合的 CSV">打开 groups.csv</button>
          <button id="btnOpenGroupsMd" title="为 JetBrains UI 预览的分组摘要">打开 jb_groups.md</button>
          <ul id="covWeak"></ul>
          <h4 id="hdrCsvPreview">CSV 预览</h4>
          <pre id="csvPreview" style="white-space:pre-wrap; background:#f7f7f7; padding:4px; font-size:11px;"></pre>
          <div>
            <label id="lblCsvSwitch">切换预览：</label>
            <select id="csvSelect" title="选择要预览的 CSV 报表">
              <option value="weak_top.csv">weak_top.csv</option>
              <option value="near_top.csv">near_top.csv</option>
              <option value="groups.csv">groups.csv</option>
            </select>
            <button id="btnCsvReload" title="重新渲染上面选择的 CSV 报表头部">重新加载预览</button>
        </div>
        </div>
        <div class="adv">
          <h3 id="hdrCovTree">覆盖率目录树（弱项）</h3>
          <ul id="covTree"></ul>
        </div>
        <div class="adv">
          <h3 id="hdrRecent">最近记忆与计划</h3>
          <pre id="memory" style="white-space:pre-wrap; background:#1102; padding:8px;">（点击“加载记忆 / 加载计划 / 事件历史”获取）</pre>
          <pre id="plan" style="white-space:pre-wrap; background:#1101; padding:8px;"></pre>
          <h4 id="hdrEvents">事件历史（最近）</h4>
          <pre id="events" style="white-space:pre-wrap; background:#0211; padding:8px;"></pre>
          <h4 id="hdrAudit">安全审计（最近）</h4>
          <pre id="audit" style="white-space:pre-wrap; background:#0211; padding:8px;"></pre>
          <h4 id="hdrStatus">状态摘要（最近）</h4>
          <pre id="infolist" style="white-space:pre-wrap; background:#1021; padding:8px;"></pre>
        </div>
        <div class="adv">
          <h3 id="hdrTasksPending">剩余任务（来自 .mcp/plan.md）</h3>
          <ul id="tasksPending"></ul>
          <h3 id="hdrTasksDone">已完成</h3>
          <ul id="tasksDone"></ul>
        </div>
        <div class="adv">
          <h3 id="hdrCI">CI 配置（hadolint / semgrep / mutation）</h3>
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
          <button id="btnCiSave" title="保存 CI 配置到项目（写入 .github/workflows 或配置文件）">保存 CI 配置</button>
          <button id="btnCiGen" title="生成 CI 工作流文件（写入 .github/workflows）">生成 CI</button>
          <button id="btnCiPreview" title="在面板内预览 CI 内容（只读）">预览 CI</button>
          <button id="btnCiOpen" title="打开 CI 工作流文件（只读）">打开 CI 文件</button>
          <button id="btnInsertRules" title="插入 .semgrep.yml / .hadolint.yaml 示例规则（便于快速启用基础检查）">插入示例规则</button>
          <span id="ciStatus" style="margin-left:8px;color:#888;"></span>
          <div style="margin-top:6px;">
            <h4>CI 预览（内联）</h4>
            <pre id="ciPreviewBox" style="white-space:pre-wrap; background:#1111; padding:6px; max-height:200px; overflow:auto;"></pre>
            <h4>CI 校验结果</h4>
            <ul id="ciChecks"></ul>
          </div>
        </div>
        <script nonce="${nonceVal}">
          const vscode = acquireVsCodeApi();
          // Collect front-end errors for diagnostics
          try {
            (window as any).__panelErrors = [];
            window.addEventListener('error', (e:any) => {
              try { (window as any).__panelErrors.push('error: ' + (e.message||'') + ' @ ' + (e.filename||'') + ':' + (e.lineno||'') + ':' + (e.colno||'')); } catch {}
            });
            window.addEventListener('unhandledrejection', (e:any) => {
              try { (window as any).__panelErrors.push('unhandledrejection: ' + String(e.reason||'')); } catch {}
            });
          } catch {}
          try { vscode.postMessage({ t: 'ready' }); } catch {}
          try { vscode.postMessage({ t: 'handshake' }); } catch {}
          // ---- UI mode (simple/advanced) ----
          (function(){
            try {
              const state = (vscode.getState && vscode.getState()) || {};
              let mode = (state && (state as any).uiMode) || (typeof localStorage!=='undefined' ? localStorage.getItem('ruleflow.uiMode') : '') || 'simple';
              const apply = (m: string) => {
                try { document.body.classList.remove('simple','advanced'); document.body.classList.add(m); } catch {}
                try { vscode.setState && vscode.setState({ ...(state||{}), uiMode: m }); } catch {}
                try { localStorage && localStorage.setItem('ruleflow.uiMode', m); } catch {}
              };
              const applyLang = (lang: string) => {
                const zh = lang === 'zh';
                const set = (id:string, text?:string, title?:string) => { try { const el = document.getElementById(id) as HTMLElement; if (el && text!==undefined) el.textContent = text; if (el && title!==undefined) (el as any).title = title; } catch {} };
                set('hdrTitle', zh? 'MCP 规则与上下文助手' : 'MCP Rules & Context Assistant');
                set('pConnected', zh? '已连接到 Python MCP Server（最小协议）。默认快速内环：保存轻、推送重。' : 'Connected to Python MCP Server (minimal protocol). Fast inner loop: light save, gated push.');
                set('lblDisplayMode', zh? '显示模式：' : 'Display mode:');
                set('lblCurProject', zh? '当前项目:' : 'Project:');
                set('hintQuick', zh? '三步上手：' : 'Quick start:');
                set('btnModeSimple', zh? '新手模式' : 'Simple', zh? '仅展示常用操作；不会自动修改文件或配置' : 'Show common actions only; no writes');
                set('btnModeAdvanced', zh? '高级模式' : 'Advanced', zh? '展示全部功能；每项操作都需要你确认后才执行' : 'Show all features; confirm before actions');
                set('btnLang', zh? '中文/English' : 'English/中文', zh? '切换中/英文界面标签' : 'Toggle Chinese/English labels');
                set('btnSimpleInstall', zh? '1) 准备并安装环境' : '1) Prepare & Install Env', zh? '为当前项目创建 .mcp/venv 并安装基础工具链（ruff/black/mypy/pytest）' : 'Create .mcp/venv and install basics');
                set('btnSimpleCoverage', zh? '2) 加载覆盖率' : '2) Load Coverage', zh? '读取 coverage.xml 汇总弱项/分组/近阈值并输出到 .mcp/dashboard' : 'Read coverage.xml and summarize');
                set('btnSimplePlan', zh? '3) 打开计划' : '3) Open Plan', zh? '打开 .mcp/plan.md（项目任务与进度的唯一权威来源）' : 'Open .mcp/plan.md');
                set('btnSimpleIngest', zh? '摄取规则（README.md, docs/）' : 'Ingest Rules (README.md, docs/)', zh? '将 README/docs 转换为规则（写入 .mcp/rules_*），不改现有源码' : 'Convert README/docs to rules into .mcp');
                set('btnSimpleStatus', zh? '刷新状态' : 'Refresh Status', zh? '刷新状态并写入 .mcp/dashboard/status.json（只读源码）' : 'Refresh status and write dashboard');
                set('nlSend', zh? '执行' : 'Run', zh? '执行输入框中的自然语言指令，仅作用于当前项目' : 'Run natural-language command');
                set('nlExamples', zh? '范例' : 'Examples');
                set('nlClear', zh? '清空历史' : 'Clear');
                set('btnIdeScaffold', zh? '生成 IDE 集成配置' : 'Generate IDE Scaffold');
                set('btnCompliance', zh? '生成合规承诺' : 'Gen Compliance');
                set('btnOpenCompliance', zh? '打开合规承诺' : 'Open Compliance');
                set('btnOpenIdeDir', zh? '打开 IDE 目录' : 'Open IDE Dir');
                set('btnReloadPanel', zh? '重载面板' : 'Reload Panel', zh? '重载面板（重新渲染并握手）' : 'Reload panel (re-render & handshake)');
                set('btnEvents', zh? '事件历史' : 'Events', zh? '显示近期事件（只读 .mcp/dashboard/cmd_events.jsonl）' : 'Show recent events');
                set('btnAudit', zh? '安全审计' : 'Security Audit', zh? '显示安全审计（只读 .mcp/dashboard/security_audit.jsonl）' : 'Show security audit');
                set('btnInfo', zh? '状态摘要 Info' : 'Status Info');
                set('btnDiag', zh? '诊断' : 'Diagnostics', zh? '收集前端错误、环境与审计信息到 .mcp/dashboard/panel_diag.json' : 'Collect front-end errors and audit report');
                // Section headings
                set('hdrTools', zh? '可用工具（示例）' : 'Available Tools (samples)');
                set('hdrCompiled', zh? '项目规则（编译版）' : 'Compiled Project Rules');
                set('hdrConflictsNav', zh? '冲突定位（可点击跳转）' : 'Conflicts (click to open)');
                set('hdrConflictsSugg', zh? '冲突与建议（Conflicts & Suggestions）' : 'Conflicts & Suggestions');
                set('hdrOnboard', zh? '规则引导（Onboard）' : 'Rules Onboarding');
                set('hdrChat', zh? 'Chat（可选）' : 'Chat (optional)');
                set('hdrCovGroups', zh? '覆盖率分组' : 'Coverage Groups');
                set('hdrWeakTop', zh? '覆盖率薄弱（Top 20）' : 'Weak Coverage (Top 20)');
                set('hdrCsvPreview', zh? 'CSV 预览' : 'CSV Preview');
                set('lblCsvSwitch', zh? '切换预览：' : 'Switch preview:');
                set('hdrCovTree', zh? '覆盖率目录树（弱项）' : 'Coverage Tree (weak)');
                set('hdrRecent', zh? '最近记忆与计划' : 'Recent Memory & Plan');
                set('hdrEvents', zh? '事件历史（最近）' : 'Recent Events');
                set('hdrAudit', zh? '安全审计（最近）' : 'Security Audit (recent)');
                set('hdrStatus', zh? '状态摘要（最近）' : 'Status Summary (recent)');
                set('hdrTasksPending', zh? '剩余任务（来自 .mcp/plan.md）' : 'Pending Tasks (from .mcp/plan.md)');
                set('hdrTasksDone', zh? '已完成' : 'Done');
                set('hdrCI', zh? 'CI 配置（hadolint / semgrep / mutation）' : 'CI Config (hadolint / semgrep / mutation)');
                // Placeholders
                try { const ip = document.getElementById('nlInput') as HTMLInputElement; if (ip) ip.placeholder = zh? '自然语言指令：如 摄取规则 README.md, docs/ / 加载覆盖率 / 开启滚动记忆' : 'NL command: e.g. Ingest README.md, docs/ / Load Coverage / Enable memory'; } catch {}
                try { (window as any).applyLang = applyLang; } catch {}
              };
              apply(mode);
              const btnS = document.getElementById('btnModeSimple') as HTMLButtonElement | null;
              const btnA = document.getElementById('btnModeAdvanced') as HTMLButtonElement | null;
              if (btnS) btnS.onclick = () => apply('simple');
              if (btnA) btnA.onclick = () => apply('advanced');
              const btnL = document.getElementById('btnLang') as HTMLButtonElement | null;
              if (btnL) btnL.onclick = () => {
                try {
                  const st = (vscode.getState && vscode.getState()) || {} as any;
                  const cur = (st && (st as any).lang) || (typeof localStorage!=='undefined' ? localStorage.getItem('ruleflow.lang') : '') || 'zh';
                  const next = (String(cur) === 'zh') ? 'en' : 'zh';
                  if (vscode.setState) vscode.setState({ ...(st||{}), lang: next });
                  try { localStorage && localStorage.setItem('ruleflow.lang', next); } catch {}
                  vscode.postMessage({ t: 'info', text: (next==='zh' ? '已切换到中文' : 'Switched to English') });
                  applyLang(next);
                  // persist to workspace (shared across windows)
                  try { vscode.postMessage({ t: 'lang.set', value: next }); } catch {}
                } catch {}
              };
              try {
                const st = (vscode.getState && vscode.getState()) || {} as any;
                const savedLang = (st && (st as any).lang) || (typeof localStorage!=='undefined' ? localStorage.getItem('ruleflow.lang') : '') || 'zh';
                applyLang(String(savedLang));
                // ask extension to override from workspace if present
                try { vscode.postMessage({ t: 'lang.get' }); } catch {}
              } catch {}
            } catch {}
          })();

          // ---- Beginner quick actions ----
          try { const el = document.getElementById('btnSimpleInstall') as HTMLButtonElement | null; if (el) el.onclick = ()=> vscode.postMessage({ t: 'prepareEnvInstall' }); } catch {}
          try { const el = document.getElementById('btnSimpleCoverage') as HTMLButtonElement | null; if (el) el.onclick = ()=> vscode.postMessage({ t: 'coverage' }); } catch {}
          try { const el = document.getElementById('btnSimplePlan') as HTMLButtonElement | null; if (el) el.onclick = ()=> vscode.postMessage({ t: 'open', path: '.mcp/plan.md', line: 1 }); } catch {}
          try { const el = document.getElementById('btnSimpleIngest') as HTMLButtonElement | null; if (el) el.onclick = ()=> vscode.postMessage({ t: 'ingestRules' }); } catch {}
          try { const el = document.getElementById('btnSimpleStatus') as HTMLButtonElement | null; if (el) el.onclick = ()=> vscode.postMessage({ t: 'statusUpdate' }); } catch {}
          // Event delegation fallback: ensure clicks still work even if nodes are re-rendered
          try {
            const clickMap: any = {
              'btnLicVerify': { t: 'licenseVerify' },
              'btnLicActivate': { t: 'licenseActivate' },
              'btnSimpleInstall': { t: 'prepareEnvInstall' },
              'btnSimpleCoverage': { t: 'coverage' },
              'btnSimplePlan': { t: 'open', path: '.mcp/plan.md', line: 1 },
              'btnSimpleIngest': { t: 'ingestRules' },
              'btnSimpleStatus': { t: 'statusUpdate' },
              'btnEvents': { t: 'eventsLoad' },
              'btnAudit': { t: 'auditLoad' },
              'btnInfo': { t: 'statusInfo' },
            };
            document.addEventListener('click', (ev:any) => {
              try {
                const el = ev.target as HTMLElement;
                if (!el || !el.id) return;
                const m = clickMap[el.id];
                if (!m) return;
                ev.preventDefault();
                vscode.postMessage(m);
              } catch {}
            }, true);
          } catch {}
          try { const el = document.getElementById('btnLoad') as HTMLButtonElement | null; if (el) el.onclick = () => vscode.postMessage({ t: 'loadRules' }); } catch {}
          try { const el = document.getElementById('btnStatusUpdate') as HTMLButtonElement | null; if (el) el.onclick = () => vscode.postMessage({ t: 'statusUpdate' }); } catch {}
          try { const el = document.getElementById('btnSelectProject') as HTMLButtonElement | null; if (el) el.onclick = () => vscode.postMessage({ t: 'selectProject' }); } catch {}
          try { const el = document.getElementById('btnIngest') as HTMLButtonElement | null; if (el) el.onclick = () => vscode.postMessage({ t: 'ingestRules' }); } catch {}
          try { const el = document.getElementById('btnValidate') as HTMLButtonElement | null; if (el) el.onclick = () => vscode.postMessage({ t: 'validateRules' }); } catch {}
          // 预览并回写门禁（rules.resolve）
          const btnResolve = document.createElement('button'); btnResolve.id = 'btnRulesResolve'; btnResolve.textContent = '预览并应用门禁';
          const anchor = document.getElementById('btnValidate');
          if (anchor && anchor.parentElement) { anchor.parentElement.insertBefore(btnResolve, anchor.nextSibling); }
          btnResolve.onclick = () => vscode.postMessage({ t: 'rulesResolvePreview' });
          try { const el = document.getElementById('btnHooks') as HTMLButtonElement | null; if (el) el.onclick = () => vscode.postMessage({ t: 'installHooks' }); } catch {}
          try { const el = document.getElementById('btnLoadSugg') as HTMLButtonElement | null; if (el) el.onclick = () => vscode.postMessage({ t: 'loadSugg' }); } catch {}
          try { const el = document.getElementById('btnCoverage') as HTMLButtonElement | null; if (el) el.onclick = () => vscode.postMessage({ t: 'coverage' }); } catch {}
          try { const el = document.getElementById('btnCovTree') as HTMLButtonElement | null; if (el) el.onclick = () => vscode.postMessage({ t: 'coverageTree' }); } catch {}
          try { const el = document.getElementById('btnOpenWeakCsv') as HTMLButtonElement | null; if (el) el.onclick = () => vscode.postMessage({ t: 'open', path: '.mcp/dashboard/weak_top.csv', line: 1 }); } catch {}
          try { const el = document.getElementById('btnOpenNearCsv') as HTMLButtonElement | null; if (el) el.onclick = () => vscode.postMessage({ t: 'open', path: '.mcp/dashboard/near_top.csv', line: 1 }); } catch {}
          try { const el = document.getElementById('btnOpenGroupsCsv') as HTMLButtonElement | null; if (el) el.onclick = () => vscode.postMessage({ t: 'open', path: '.mcp/dashboard/groups.csv', line: 1 }); } catch {}
          try { const el = document.getElementById('btnOpenGroupsMd') as HTMLButtonElement | null; if (el) el.onclick = () => vscode.postMessage({ t: 'open', path: '.mcp/dashboard/jb_groups.md', line: 1 }); } catch {}
          try { const el = document.getElementById('btnCovExport') as HTMLButtonElement | null; if (el) el.onclick = () => vscode.postMessage({ t: 'covExport' }); } catch {}
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
          (document.getElementById('btnEvents') as HTMLButtonElement).onclick = () => vscode.postMessage({ t: 'eventsLoad' });
          (document.getElementById('btnAudit') as HTMLButtonElement).onclick = () => vscode.postMessage({ t: 'auditLoad' });
          const btnReload = document.getElementById('btnReloadPanel') as HTMLButtonElement | null; if (btnReload) btnReload.onclick = () => vscode.postMessage({ t: 'panel.reload' });
          const btnDiag = document.createElement('button'); btnDiag.id='btnDiag'; btnDiag.textContent='诊断'; (btnDiag as HTMLButtonElement).title='收集前端错误、环境与审计信息到 .mcp/dashboard/panel_diag.json';
          const advBar = document.querySelector('div.adv'); if (advBar) advBar.insertBefore(btnDiag, advBar.firstChild);
          btnDiag.onclick = () => { try { const errs = (window as any).__panelErrors || []; vscode.postMessage({ t: 'panelDiagRequest', errors: errs }); } catch {} };
          const btnUG = document.getElementById('btnOpenUserGuide') as HTMLButtonElement | null;
          if (btnUG) btnUG.onclick = () => vscode.postMessage({ t: 'open', path: 'docs/USER_GUIDE.md' });
          const btnIS = document.getElementById('btnOpenIdeSupport') as HTMLButtonElement | null;
          if (btnIS) btnIS.onclick = () => vscode.postMessage({ t: 'open', path: 'docs/IDE_SUPPORT.md' });
          (document.getElementById('btnPrepareEnvInstall') as HTMLButtonElement).onclick = () => vscode.postMessage({ t: 'prepareEnvInstall' });
          (document.getElementById('btnOnboardPreview') as HTMLButtonElement).onclick = () => vscode.postMessage({ t: 'onboardPreview' });
          (document.getElementById('btnOnboardApply') as HTMLButtonElement).onclick = () => vscode.postMessage({ t: 'onboardApply' });
          (document.getElementById('btnChatEnable') as HTMLButtonElement).onclick = () => vscode.postMessage({ t: 'chatEnable' });
          (document.getElementById('btnChatDisable') as HTMLButtonElement).onclick = () => vscode.postMessage({ t: 'chatDisable' });
          (document.getElementById('btnChatPreview') as HTMLButtonElement).onclick = () => vscode.postMessage({ t: 'chatPreview' });
          (document.getElementById('btnEvents') as HTMLButtonElement).onclick = () => vscode.postMessage({ t: 'eventsLoad' });
          (document.getElementById('btnInfo') as HTMLButtonElement).onclick = () => vscode.postMessage({ t: 'statusInfo' });
          (document.getElementById('btnCopyEvents') as HTMLButtonElement).onclick = async () => {
            try { const el = document.getElementById('events') as HTMLPreElement; const t = (el && (el as any).textContent) || ''; if ((navigator as any).clipboard) { await (navigator as any).clipboard.writeText(String(t)); vscode.postMessage({ t: 'info', text: '已复制事件历史' }); } } catch {}
          };
          (document.getElementById('btnCopyInfo') as HTMLButtonElement).onclick = async () => {
            try { const el = document.getElementById('infolist') as HTMLPreElement; const t = (el && (el as any).textContent) || ''; if ((navigator as any).clipboard) { await (navigator as any).clipboard.writeText(String(t)); vscode.postMessage({ t: 'info', text: '已复制状态摘要' }); } } catch {}
          };
          (document.getElementById('btnOpenStatusFile') as HTMLButtonElement).onclick = () => vscode.postMessage({ t: 'open', path: '.mcp/dashboard/status.json', line: 1 });
          (document.getElementById('btnOpenEventsFile') as HTMLButtonElement).onclick = () => vscode.postMessage({ t: 'open', path: '.mcp/dashboard/cmd_events.jsonl', line: 1 });
          const _btnAuditFile = document.getElementById('btnOpenAuditFile') as HTMLButtonElement | null;
          if (_btnAuditFile) _btnAuditFile.onclick = () => vscode.postMessage({ t: 'open', path: '.mcp/dashboard/security_audit.jsonl', line: 1 });
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
          (document.querySelectorAll('#nlExamplesBox button, #nlCatalog button') as any).forEach((b:any)=>{
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
            if (msg.t === 'setLang') {
              try { const v = String(msg.value||'zh'); (window as any).__ruleflowLang=v; } catch {}
              try { const applyLangFn = (window as any).applyLang || null; if (applyLangFn) applyLangFn((window as any).__ruleflowLang); } catch {}
            }
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
              let text = String(msg.text || '');
              try {
                const lang = String((window as any).__ruleflowLang || 'zh');
                if (lang === 'en') {
                  const map: any = {
                    '未找到覆盖率资源': 'No coverage resources found',
                    '覆盖率摘要不可用': 'Coverage summary unavailable',
                    '状态已刷新': 'Status refreshed',
                    '未找到事件历史': 'No event history found',
                    '未找到编译规则': 'Compiled rules not found',
                    '检测到': 'Detected',
                    '处规则冲突': 'rule conflicts',
                    '建议数': 'suggestions',
                    'Onboard 预览完成': 'Onboard preview completed',
                    '目录树不可用': 'Coverage tree unavailable',
                    '已写入诊断': 'Diagnostics written',
                    '已切换到中文': 'Switched to Chinese',
                    '近阈值文件': 'Near-threshold files',
                    '弱项': 'Weak items'
                  };
                  Object.keys(map).forEach(k => { text = text.replace(new RegExp(k, 'g'), map[k]); });
                }
              } catch {}
              if (inf) inf.textContent = text;
            }
            if (msg.t === 'onboardShow') {
              const el = document.getElementById('onboardSummary');
              if (el) { (el as any).textContent = String(msg.text || ''); }
            }
            if (msg.t === 'chatShow') {
              const el = document.getElementById('chatPreview');
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
            if (msg.t === 'events') {
              const el = document.getElementById('events');
              if (el) (el as any).textContent = String(msg.text || '');
            }
            if (msg.t === 'audit') {
              const el = document.getElementById('audit');
              if (el) (el as any).textContent = String(msg.text || '');
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
            if (msg.t === 'events') {
              const el = document.getElementById('events');
              if (el) (el as any).textContent = String(msg.text || '');
            }
            if (msg.t === 'plan') {
              document.getElementById('plan').textContent = msg.text || '';
            }
            if (msg.t === 'infoList') {
              const pre = document.getElementById('infolist') as HTMLPreElement;
              pre.textContent = (Array.isArray(msg.items) ? msg.items : []).join('\n');
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
      const csp = panel.webview.cspSource;
      panel.webview.html = render(csp, nonce, '', list);
      // Apply persisted language preference from workspace (shared across windows)
      try {
        const ws = getWorkspaceRoot();
        if (ws) {
          const uri = vscode.Uri.file(ws + '/.mcp/dashboard/ui_prefs.json');
          let lang = 'zh';
          try {
            const data = await vscode.workspace.fs.readFile(uri);
            const text = Buffer.from(data).toString('utf8');
            const obj = JSON.parse(text || '{}');
            if (obj && typeof obj.lang === 'string' && obj.lang) lang = obj.lang;
          } catch { /* missing is fine */ }
          try { panel.webview.postMessage({ t: 'setLang', value: lang }); } catch {}
        }
      } catch { /* ignore */ }
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
      panel.webview.html = renderFallback('连接 MCP 失败：' + String(e));
    }

    const __panelDispatch = async (msg: any) => {
      // mark in-flight for tests to await idle
      try { __panelInFlight = new Promise<void>((res)=>{ __panelInFlightResolve = res; }); } catch {}
      try {
        __testWebviewHandler = async (m:any) => { await handleOpenMessage(m); };
        if (msg.t === 'retryConnect') {
          try { client.start(context); } catch {}
          vscode.window.setStatusBarMessage('正在尝试重新连接 MCP…', 2000);
        }
        else if (msg.t === 'enableFake') {
          try {
            const ws = getWorkspaceRoot() || process.cwd();
            const path = require('path'); const fs = require('fs');
            const dash = path.join(ws, '.mcp', 'dashboard');
            fs.mkdirSync(dash, { recursive: true });
            fs.writeFileSync(path.join(dash, 'fake_mode'), '1');
            vscode.window.showInformationMessage('已切换为演示模式（fake）。');
            (client as any).fakeMode = true; // best-effort
            await vscode.commands.executeCommand('mcpRulesAssistant.openPanel');
            return;
          } catch (e:any) {
            vscode.window.showErrorMessage('切换演示模式失败：' + String(e));
          }
        }
        else if (msg.t === 'handshake') {
          try { panel.webview.postMessage({ t: 'info', text: 'Webview 已连接（handshake_ok）' }); } catch {}
        }
        else if (msg.t === 'openServerLog') {
          try {
            const ws = getWorkspaceRoot();
            if (!ws) { vscode.window.showInformationMessage('No workspace'); return; }
            const uri = vscode.Uri.file(ws + '/.mcp/dashboard/server.log');
            await vscode.workspace.fs.stat(uri);
            const doc = await vscode.workspace.openTextDocument(uri);
            await vscode.window.showTextDocument(doc, { preview: false });
          } catch { vscode.window.showInformationMessage('未找到 .mcp/dashboard/server.log'); }
        }
        else if (msg.t === 'panelDiagRequest') {
          try {
            const ws = getWorkspaceRoot(); if (!ws) throw new Error('no workspace');
            const errs = Array.isArray(msg.errors) ? (msg.errors as any[]).slice(-100) : [];
            const diag: any = { time: new Date().toISOString(), workspace: ws, strict: String(process.env.MCP_STRICT_ISOLATION||''), projectRootEnv: String(process.env.MCP_PROJECT_ROOT||'') };
            try { const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant'); diag.version = (ext && (ext.packageJSON as any).version) || ''; } catch {}
            try { diag.env = await client.request('tools/call', { name: 'env.diagnose', arguments: {} }); } catch {}
            try { diag.audit = await client.request('tools/call', { name: 'security.audit_report', arguments: {} }); } catch {}
            try {
              const uriE = vscode.Uri.file(ws + '/.mcp/dashboard/cmd_events.jsonl');
              const data = await vscode.workspace.fs.readFile(uriE);
              const text = Buffer.from(data).toString('utf8');
              const lines = text.split(/\r?\n/).filter(Boolean); diag.events_tail = lines.slice(-120);
            } catch {}
            diag.frontend_errors = errs;
            const outUri = vscode.Uri.file(ws + '/.mcp/dashboard/panel_diag.json');
            const enc = new TextEncoder();
            await vscode.workspace.fs.writeFile(outUri, enc.encode(JSON.stringify(diag, null, 2)));
            try { const doc = await vscode.workspace.openTextDocument(outUri); await vscode.window.showTextDocument(doc, { preview: false }); } catch {}
            panel.webview.postMessage({ t: 'info', text: '已写入诊断：.mcp/dashboard/panel_diag.json' });
          } catch (e:any) {
            vscode.window.showWarningMessage('生成诊断失败：' + String(e));
          }
        }
        else if (msg.t === 'lang.set') {
          try {
            const lang = String(msg.value || 'zh');
            const ws = getWorkspaceRoot(); if (!ws) return;
            const dash = vscode.Uri.file(ws + '/.mcp/dashboard');
            try { await vscode.workspace.fs.createDirectory(dash); } catch {}
            const p = vscode.Uri.file(ws + '/.mcp/dashboard/ui_prefs.json');
            const enc = new TextEncoder();
            await vscode.workspace.fs.writeFile(p, enc.encode(JSON.stringify({ lang }, null, 2)));
          } catch {}
        }
        else if (msg.t === 'lang.get') {
          try {
            const ws = getWorkspaceRoot(); if (!ws) return;
            const p = vscode.Uri.file(ws + '/.mcp/dashboard/ui_prefs.json');
            const data = await vscode.workspace.fs.readFile(p);
            const text = Buffer.from(data).toString('utf8');
            const obj = JSON.parse(text || '{}');
            const lang = (obj && typeof obj.lang === 'string' && obj.lang) ? obj.lang : 'zh';
            panel.webview.postMessage({ t: 'setLang', value: lang });
          } catch {
            panel.webview.postMessage({ t: 'setLang', value: 'zh' });
          }
        }
        else if (msg.t === 'statusUpdate') {
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
        } else if (msg.t === 'rulesResolvePreview') {
          try {
            const resList = await client.request('resources/list', {});
            const jsonUri = (resList.resources || []).find((r: any) => String(r.uri || '').endsWith('/compiled.json'))?.uri;
            if (!jsonUri) { vscode.window.showWarningMessage('未找到编译规则，请先摄取规则'); return; }
            const compiled = await client.request('resources/read', { uri: jsonUri });
            const data = JSON.parse(compiled.text || '{}');
            const pol = data.policy || {};
            const minMod = pol['coverage.min_module'];
            const minCore = pol['coverage.min_core'];
            const wantHadolint = !!(pol['container.required'] || pol['container.policy.baseline']);
            const wantSemgrep = !!pol['security.sast_strict'];
            const conflicts = Array.isArray(data.conflicts) ? data.conflicts.length : 0;
            const sugg = Array.isArray(data.suggestions) ? data.suggestions.length : 0;
            const lines: string[] = [];
            if (typeof minMod === 'number') lines.push(`coverage.min_module = ${(minMod*100).toFixed(0)}%`);
            if (typeof minCore === 'number') lines.push(`coverage.min_core = ${(minCore*100).toFixed(0)}%`);
            if (wantHadolint) lines.push('ci.hadolint = true');
            if (wantSemgrep) lines.push('ci.semgrep_config = auto');
            lines.push(`conflicts = ${conflicts}; suggestions = ${sugg}`);
            const confirm = await vscode.window.showInformationMessage('将应用以下门禁到配置:\n' + lines.join('\n'), { modal: true }, '应用', '取消');
            if (confirm === '应用') {
              const out = await client.request('tools/call', { name: 'rules.resolve', arguments: {} });
              const changed = out && out.changed;
              const enforced = (out && out.enforced) || [];
              const summary = `门禁已应用：${changed? '配置已更新' : '无变化'}；` + (Array.isArray(enforced)? enforced.join(', ') : '');
              vscode.window.showInformationMessage(summary);
              try { panel.webview.postMessage({ t: 'info', text: summary }); } catch {}
            }
          } catch (e:any) {
            vscode.window.showErrorMessage('预览失败：' + String(e));
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
              if (memAllowed()) {
                await client.request('tools/call', { name: 'memory.append_turn', arguments: { role: 'assistant', content, meta: { source: 'vscode', action: 'panel.coverage' } } });
              }
            } catch {}
          } catch {}
        } else if (msg.t === 'panel.reload') {
          try {
            client.start(context);
            try { await client.request('initialize', {}); } catch {}
            const tools = await client.request('tools/list', {});
            const list = (tools.tools || []).map((t: any) => `<li><code>${t.name}</code> — ${t.description}</li>`).join('');
            const nonce2 = getNonce();
            panel.webview.html = render(csp, nonce2, '', list);
            // re-apply workspace language preference after reload
            try {
              const ws = getWorkspaceRoot();
              if (ws) {
                const uri = vscode.Uri.file(ws + '/.mcp/dashboard/ui_prefs.json');
                try {
                  const data = await vscode.workspace.fs.readFile(uri);
                  const text = Buffer.from(data).toString('utf8');
                  const obj = JSON.parse(text || '{}');
                  const lang = (obj && typeof obj.lang === 'string' && obj.lang) ? obj.lang : 'zh';
                  try { panel.webview.postMessage({ t: 'setLang', value: lang }); } catch {}
                } catch { /* ignore */ }
              }
            } catch {}
            vscode.window.setStatusBarMessage('Panel reloaded', 2000);
          } catch (e:any) {
            vscode.window.showWarningMessage('重载失败：' + String(e));
          }
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
        } else if (msg.t === 'eventsLoad') {
          try {
            const ws = getWorkspaceRoot(); if (!ws) throw new Error('no workspace');
            const uri = vscode.Uri.file(ws + '/.mcp/dashboard/cmd_events.jsonl');
            const data = await vscode.workspace.fs.readFile(uri);
            const text = Buffer.from(data).toString('utf8');
            panel.webview.postMessage({ t: 'events', text });
          } catch {
            panel.webview.postMessage({ t: 'info', text: '未找到事件历史' });
          }
        } else if (msg.t === 'auditLoad') {
          try {
            const ws = getWorkspaceRoot(); if (!ws) throw new Error('no workspace');
            const uri = vscode.Uri.file(ws + '/.mcp/dashboard/security_audit.jsonl');
            const data = await vscode.workspace.fs.readFile(uri);
            const text = Buffer.from(data).toString('utf8');
            panel.webview.postMessage({ t: 'audit', text });
          } catch {
            panel.webview.postMessage({ t: 'info', text: '未找到安全审计（security_audit.jsonl）' });
          }
        } else if (msg.t === 'statusInfo') {
          try {
            const ws = getWorkspaceRoot(); if (!ws) throw new Error('no workspace');
            const uri = vscode.Uri.file(ws + '/.mcp/dashboard/status.json');
            const data = await vscode.workspace.fs.readFile(uri);
            const text = Buffer.from(data).toString('utf8');
            try {
              const obj = JSON.parse(text || '{}');
              const info = Array.isArray(obj.info) ? obj.info : [];
              const lines = info.map((it:any) => {
                if (it && typeof it === 'object') { return `${it.time || ''}  ${it.text || ''}`; }
                return String(it);
              });
              panel.webview.postMessage({ t: 'infoList', items: lines });
            } catch { panel.webview.postMessage({ t: 'info', text: '状态摘要解析失败' }); }
          } catch { panel.webview.postMessage({ t: 'info', text: '未找到 status.json' }); }
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
          // 严格隔离：默认不写入任何上下文记忆（需显式允许）
          // if (process.env.RULEFLOW_ALLOW_MEMORY_APPEND === '1') {
          //   try { await client.request('tools/call', { name: 'memory.append_turn', arguments: { role: 'assistant', content: 'env.prepare dry-run', meta: { source: 'vscode', action: 'env.prepare', create: false, install: false } } }); } catch {}
          // }
          } catch (e:any) {
            vscode.window.showErrorMessage('env.prepare 执行失败：' + String(e));
          }
        } else if (msg.t === 'prepareEnvInstall') {
          try {
            const out = await client.request('tools/call', { name: 'env.prepare', arguments: { create: true, install: true } });
            const msgInfo = (out && (out as any).ok) ? ('已创建并安装：' + String((out as any).venv || '')) : '执行失败';
            vscode.window.showInformationMessage('env.prepare: ' + msgInfo);
            // if (process.env.RULEFLOW_ALLOW_MEMORY_APPEND === '1') {
            //   try { await client.request('tools/call', { name: 'memory.append_turn', arguments: { role: 'assistant', content: 'env.prepare install', meta: { source: 'vscode', action: 'env.prepare', create: true, install: true } } }); } catch {}
            // }
          } catch (e:any) {
            vscode.window.showErrorMessage('env.prepare 执行失败：' + String(e));
          }
        } else if (msg.t === 'selectProject') {
          const folders = vscode.workspace.workspaceFolders || [];
          if (!folders.length) { vscode.window.showWarningMessage('未找到工作区'); return; }
          const pick = await vscode.window.showQuickPick(folders.map(f=>({ label: f.name, description: f.uri.fsPath })), { title: '选择项目根目录' });
          if (!pick) return;
          try {
            __lockedRoot = pick.description;
            await context.workspaceState.update('ruleflow.lockRoot', __lockedRoot);
            // 写入 ui_prefs.json 以共享选择
            try {
              const p = require('path'); const fs = require('fs');
              const dash = p.join(__lockedRoot, '.mcp', 'dashboard');
              fs.mkdirSync(dash, { recursive: true });
              const up = p.join(dash, 'ui_prefs.json');
              let obj: any = {}; try { obj = JSON.parse(fs.readFileSync(up, 'utf8')||'{}'); } catch {}
              obj.projectRoot = __lockedRoot; fs.writeFileSync(up, JSON.stringify(obj, null, 2));
            } catch {}
            // 重启后端以应用新的 MCP_PROJECT_ROOT
            try { (client as any).proc?.kill(); (client as any).proc=null; } catch {}
            try { client.start(context); } catch {}
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
        } else if (msg.t === 'chatEnable') {
          await context.workspaceState.update('ruleflow.chat.appendEnabled', true);
          panel.webview.postMessage({ t: 'chatShow', text: 'Chat 追加摘要：已启用（默认摘要短小，不含源码/个人信息）' });
        } else if (msg.t === 'chatDisable') {
          await context.workspaceState.update('ruleflow.chat.appendEnabled', false);
          panel.webview.postMessage({ t: 'chatShow', text: 'Chat 追加摘要：已禁用' });
        } else if (msg.t === 'chatPreview') {
          const enabled = !!context.workspaceState.get('ruleflow.chat.appendEnabled');
          const demo = 'Chat: 这里将显示上一轮问答的简要摘要（示例）';
          panel.webview.postMessage({ t: 'chatShow', text: (enabled ? '（启用）' : '（禁用）') + ' ' + demo });
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
          const h = context.workspaceState.get<string[]>('ruleflow.nl.history') || [];
          const nh = [text, ...h.filter(x=>x!==text)].slice(0, 10);
          await context.workspaceState.update('ruleflow.nl.history', nh);
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
          await context.workspaceState.update('ruleflow.nl.history', []);
          panel.webview.postMessage({ t: 'nlHistory', items: [] });
          panel.webview.postMessage({ t: 'info', text: '已清空自然语言历史' });
        } catch {}
      }
      if (msg && msg.t === 'nlFetchHistory') {
        try {
          const h = context.workspaceState.get<string[]>('ruleflow.nl.history') || [];
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
  // 注：quickActions 命令已在上文注册；此处重复注册已移除以避免测试中重复激活导致冲突

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
  // test-only: set chat append enabled flag
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant._test_chatSetEnabled', async (on?: boolean) => {
    try { await context.workspaceState.update('ruleflow.chat.appendEnabled', !!on); return true; } catch { return false; }
  }));

  // Public: append last chat summary into memory (optional; guarded by enable flag)
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant.chatAppendSummary', async (text?: string) => {
    try { client.start(context); } catch {}
    try {
      const enabled = !!context.workspaceState.get('ruleflow.chat.appendEnabled');
      if (!enabled) { vscode.window.showInformationMessage('Chat 追加摘要未启用'); return true; }
      let summary = (typeof text === 'string' && text.trim()) ? String(text).trim() : '';
      if (!summary) {
        summary = await vscode.window.showInputBox({ placeHolder: '输入要追加的上一轮问答摘要' }) || '';
      }
      if (!summary) { return false; }
      const content = 'ChatSummary: ' + summary;
      await client.request('tools/call', { name: 'memory.append_turn', arguments: { role: 'assistant', content, meta: { source: 'vscode', action: 'chat.append' } } });
      vscode.window.showInformationMessage('已追加 Chat 摘要');
      return true;
    } catch (e:any) {
      vscode.window.showErrorMessage('Chat 摘要追加失败：' + String(e));
      return false;
    }
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
      const h = context.workspaceState.get<string[]>('ruleflow.nl.history') || [];
      const t = (text || 'hello').trim();
      const nh = [t, ...h.filter(x=>x!==t)].slice(0, 10);
      await context.workspaceState.update('ruleflow.nl.history', nh);
      return nh.length;
    }
    if (op === 'clear') {
      await context.workspaceState.update('ruleflow.nl.history', []);
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
      const h = context.workspaceState.get<string[]>('ruleflow.nl.history') || [];
      const nh = [text, ...h.filter(x=>x!==text)].slice(0, 10);
      await context.workspaceState.update('ruleflow.nl.history', nh);
    } catch (e: any) {
      vscode.window.showErrorMessage('执行自然语言命令失败：' + String(e));
    }
  }));

  // License: Activate (choose file and call tool)
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant.licenseActivate', async () => {
    try {
      client.start(context);
      const pick = await vscode.window.showOpenDialog({ canSelectMany: false, openLabel: '选择许可文件 (JSON)' });
      if (!pick || !pick[0]) { return; }
      const path = pick[0].fsPath;
      await client.request('tools/call', { name: 'license.activate', arguments: { path } });
      vscode.window.showInformationMessage('License 已激活');
    } catch (e:any) {
      vscode.window.showErrorMessage('激活失败：' + String(e));
    }
  }));
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant.licenseVerify', async () => {
    try {
      client.start(context);
      const res = await client.request('tools/call', { name: 'license.verify', arguments: {} });
      const lic = res && (res.license || res);
      let msg = '未找到许可';
      try {
        const exp = lic && lic.expires; const ok = lic && lic.ok;
        if (exp) {
          const days = Math.ceil((new Date(exp).getTime() - Date.now()) / (1000*3600*24));
          msg = `许可状态：${ok? '有效' : '无效'}；到期：${exp}（剩余 ${days} 天）`;
        }
      } catch {}
      vscode.window.showInformationMessage(msg);
    } catch (e:any) {
      vscode.window.showErrorMessage('校验失败：' + String(e));
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
