(function(){
  try {
    const vscode = acquireVsCodeApi();
    console.log('[panel_bootstrap] Starting initialization');
    // Handshake ping as early as possible
    try { 
      vscode.postMessage({ t: 'handshake' }); 
      console.log('[panel_bootstrap] Handshake sent');
    } catch (e) {
      console.error('[panel_bootstrap] Handshake failed:', e);
    }
    // Event delegation: map known buttons by id to messages
    const clickMap = {
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
      'btnReloadPanel': { t: 'panel.reload' },
      'btnModeSimple': { t: 'mode.simple' },
      'btnModeAdvanced': { t: 'mode.advanced' },
      'btnLang': { t: 'lang.toggle' }
    };
    document.addEventListener('click', function(ev){
      try {
        const el = ev.target;
        console.log('[panel_bootstrap] Click detected on:', el.tagName, el.id, el.className);
        if (!el || !el.id) {
          console.log('[panel_bootstrap] No element ID found');
          return;
        }
        const m = clickMap[el.id];
        if (!m) {
          console.log('[panel_bootstrap] No mapping found for ID:', el.id);
          return;
        }
        ev.preventDefault();
        console.log('[panel_bootstrap] Sending message:', m);
        vscode.postMessage(m);
      } catch (e) {
        console.error('[panel_bootstrap] Click handler error:', e);
      }
    }, true);
    console.log('[panel_bootstrap] Event listener attached');
  } catch (e) {
    console.error('[panel_bootstrap] Initialization failed:', e);
  }
})();

