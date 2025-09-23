(function(){
  try {
    // Check if VSCode API is already acquired by inline scripts
    const vscode = window.vscode || acquireVsCodeApi();
    if (!window.vscode) window.vscode = vscode;
    console.log('[panel_bootstrap] Starting initialization');
    // Handshake ping as early as possible
    try { 
      vscode.postMessage({ t: 'handshake' }); 
      console.log('[panel_bootstrap] Handshake sent');
      // Redundant ready signal to help extension mark panel as ready even if inline script fails
      try { vscode.postMessage({ t: 'ready' }); } catch {}
    } catch (e) {
      console.error('[panel_bootstrap] Handshake failed:', e);
    }
    // Event delegation: map known buttons by id to messages
    const clickMap = {
      // License & Project
      'btnLicVerify': { t: 'licenseVerify' },
      'btnLicActivate': { t: 'licenseActivate' },
      'btnSelectProject': { t: 'selectProject' },
      
      // Simple mode buttons (beginner workflow)
      'btnSimpleInstall': { t: 'prepareEnvInstall' },
      'btnSimpleCoverage': { t: 'coverage' },
      'btnSimplePlan': { t: 'open', path: '.mcp/plan.md', line: 1 },
      'btnSimpleIngest': { t: 'ingestRules' },
      'btnSimpleStatus': { t: 'statusUpdate' },
      
      // Core workflow buttons
      'btnLoad': { t: 'loadRules' },
      'btnIngest': { t: 'ingestRules' },
      'btnValidate': { t: 'validateRules' },
      'btnHooks': { t: 'installHooks' },
      'btnLoadSugg': { t: 'loadSugg' },
      'btnCoverage': { t: 'coverage' },
      'btnShowWeak': { t: 'showWeak' },
      'btnCovTree': { t: 'coverageTree' },
      'btnCovNear': { t: 'covNearPrompt' },
      'btnCovNearInline': { t: 'covNearPrompt' },
      'btnCovExport': { t: 'covExport' },
      
      // Environment & preparation
      'btnPrepareEnvDry': { t: 'prepareEnvDry' },
      'btnPrepareEnvInstall': { t: 'prepareEnvInstall' },
      
      // Onboarding
      'btnOnboardPreview': { t: 'onboardPreview' },
      'btnOnboardApply': { t: 'onboardApply' },
      
      // Chat & memory
      'btnChatEnable': { t: 'chatEnable' },
      'btnChatDisable': { t: 'chatDisable' },
      'btnChatPreview': { t: 'chatPreview' },
      'btnMemory': { t: 'memory' },
      'btnPlan': { t: 'plan' },
      
      // CI operations
      'btnCiSave': { t: 'ciSave' },
      'btnCiGen': { t: 'ciGen' },
      'btnCiPreview': { t: 'ciPreviewInline' },
      'btnCiOpen': { t: 'ciOpen' },
      'btnCiValidate': { t: 'ciValidate' },
      'btnInsertRules': { t: 'insertSamples' },
      
      // File operations
      'btnOpenWeakCsv': { t: 'open', path: '.mcp/dashboard/weak_top.csv', line: 1 },
      'btnOpenNearCsv': { t: 'open', path: '.mcp/dashboard/near_top.csv', line: 1 },
      'btnOpenGroupsCsv': { t: 'open', path: '.mcp/dashboard/groups.csv', line: 1 },
      'btnOpenGroupsMd': { t: 'open', path: '.mcp/dashboard/jb_groups.md', line: 1 },
      'btnOpenStatusFile': { t: 'open', path: '.mcp/dashboard/status.json', line: 1 },
      'btnOpenEventsFile': { t: 'open', path: '.mcp/dashboard/cmd_events.jsonl', line: 1 },
      'btnOpenAuditFile': { t: 'open', path: '.mcp/dashboard/security_audit.jsonl', line: 1 },
      'btnOpenUserGuide': { t: 'open', path: 'docs/USER_GUIDE.md' },
      'btnOpenIdeSupport': { t: 'open', path: 'docs/IDE_SUPPORT.md' },
      
      // IDE & compliance
      'btnIdeScaffold': { t: 'ideScaffold' },
      'btnCompliance': { t: 'compliance' },
      'btnOpenCompliance': { t: 'openCompliance' },
      'btnOpenIdeDir': { t: 'openIdeDir' },
      
      // Status & diagnostics
      'btnEvents': { t: 'eventsLoad' },
      'btnAudit': { t: 'auditLoad' },
      'btnInfo': { t: 'statusInfo' },
      'btnStatusUpdate': { t: 'statusUpdate' },
      'btnDiag': { t: 'panelDiagRequest' },
      // Some layouts place a top-level diagnostics button with a different id
      'btnDiagTop': { t: 'panelDiagRequest' },
      
      // Natural language
      'nlSend': { t: 'nl' },
      'nlExamples': { t: 'nlExamples' },
      'nlClear': { t: 'nlClearHistory' },
      
      // UI controls
      'btnReloadPanel': { t: 'panel.reload' },
      'btnModeSimple': { t: 'mode.simple' },
      'btnModeAdvanced': { t: 'mode.advanced' },
      'btnLang': { t: 'lang.toggle' }
    };
    document.addEventListener('click', function(ev){
      try {
        let el = ev.target;
        // Normalize to an Element (handle text nodes)
        if (el && el.nodeType === 3 && el.parentElement) { el = el.parentElement; }
        if (!(el && el.closest)) { return; }
        const button = el.closest('button, a, [role="button"], [id]');
        if (!button) { return; }
        const id = button.id || '';
        console.log('[panel_bootstrap] Click detected on:', button.tagName, id, button.className);
        const m = id ? clickMap[id] : undefined;
        if (!m) {
          console.log('[panel_bootstrap] No mapping found for ID:', id);
          return;
        }
        ev.preventDefault();
        // Local fallback for immediate UX (mode/lang) even if extension not yet responding
        try {
          if (id === 'btnModeSimple' || id === 'btnModeAdvanced') {
            const mode = (id === 'btnModeAdvanced') ? 'advanced' : 'simple';
            document.body && document.body.classList && (function(){
              try { document.body.classList.remove('simple','advanced'); document.body.classList.add(mode); } catch {}
            })();
            console.log('[panel_bootstrap] Fallback applied: mode =', mode);
          }
          if (id === 'btnLang') {
            const cur = (window.__ruleflowLang || 'zh');
            const next = (cur === 'zh') ? 'en' : 'zh';
            try { window.__ruleflowLang = next; } catch {}
            try { const applyLang = (window).applyLang; if (typeof applyLang === 'function') applyLang(next); } catch {}
            console.log('[panel_bootstrap] Fallback applied: lang =', (window.__ruleflowLang||'zh'));
            try { vscode.postMessage({ t: 'lang.set', value: next }); } catch {}
          }
        } catch {}
        // Post a generic diagnostic click event
        try { vscode.postMessage({ t: 'panel.click', id }); } catch {}
        console.log('[panel_bootstrap] Sending message:', m);
        try { vscode.postMessage(m); } catch {}
        // Robust fallback: only trigger command URI when postMessage may be unavailable
        try {
          var cmdMap = {
            'prepareEnvInstall': 'mcpRulesAssistant.envPrepareInstall',
            'statusUpdate': 'mcpRulesAssistant.statusUpdate',
            'coverage': 'mcpRulesAssistant.loadCoverage',
            'panelDiagRequest': 'mcpRulesAssistant.panelDiag'
          };
          var t = m && m.t;
          var cmd = cmdMap[t];
          var allowFallback = !(window.__ruleflowHandshakeOk);
          if (cmd && allowFallback) {
            var a = document.createElement('a');
            a.href = 'command:' + cmd;
            // Hide and click
            a.style.display = 'none';
            document.body.appendChild(a);
            a.click();
            setTimeout(function(){ try { document.body.removeChild(a); } catch {} }, 0);
          }
        } catch (e) {
          console.error('[panel_bootstrap] Fallback command URI failed:', e);
        }
      } catch (e) {
        console.error('[panel_bootstrap] Click handler error:', e);
      }
    }, { passive: false, capture: true });
    
    // Add wheel event listener with passive option
    document.addEventListener('wheel', function(ev) {
      // Handle wheel events if needed
    }, { passive: true });
    
    // Add touchstart event listener with passive option
    document.addEventListener('touchstart', function(ev) {
      // Handle touch events if needed
    }, { passive: true });
    console.log('[panel_bootstrap] Event listener attached');
    // Diagnostics: verify DOM presence
    try {
      var blen = (document && document.body && document.body.innerHTML && document.body.innerHTML.length) || 0;
      console.log('[panel_bootstrap] body.innerHTML length =', blen);
      console.log('[panel_bootstrap] has #simpleBar =', !!document.getElementById('simpleBar'));
      console.log('[panel_bootstrap] has #hdrTitle =', !!document.getElementById('hdrTitle'));
    } catch (e) {
      console.error('[panel_bootstrap] DOM diagnostics failed:', e);
    }
  } catch (e) {
    console.error('[panel_bootstrap] Initialization failed:', e);
  }
})();

