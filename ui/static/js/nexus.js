/**
 * NEXUS SOC Dashboard — Frontend Logic
 * Auto-refresh, live log streaming, workflow visualization.
 */

'use strict';

// ── Config ──────────────────────────────────────────────────────────────────
const API = {
  status    : '/api/status',
  executions: '/api/executions',
  workflows : '/api/workflows',
};
const REFRESH_MS = 8000;

// ── State ────────────────────────────────────────────────────────────────────
let metrics = { success: 0, failed: 0, total: 0, duration: 0 };
let _timer   = null;

// ── Utilities ────────────────────────────────────────────────────────────────

async function fetchJSON(url) {
  try {
    const r = await fetch(url, { cache: 'no-store' });
    if (!r.ok) return null;
    return r.json();
  } catch { return null; }
}

function timeAgo(ts) {
  const d = Date.now() / 1000 - ts;
  if (d < 60)   return `${~~d}s ago`;
  if (d < 3600) return `${~~(d / 60)}m ago`;
  return `${~~(d / 3600)}h ago`;
}

function el(id) { return document.getElementById(id); }

function addTermLine(text, cls = '') {
  const out = el('terminal-output');
  if (!out) return;
  const div = document.createElement('div');
  div.className = `term-line ${cls}`;
  div.textContent = text;
  out.appendChild(div);
  // Keep max 200 lines
  while (out.children.length > 200) out.removeChild(out.firstChild);
  out.scrollTop = out.scrollHeight;
}

// ── Clock ────────────────────────────────────────────────────────────────────

function updateClock() {
  const now = new Date();
  const h   = String(now.getHours()).padStart(2, '0');
  const m   = String(now.getMinutes()).padStart(2, '0');
  const s   = String(now.getSeconds()).padStart(2, '0');
  const clk = el('clock');
  if (clk) clk.textContent = `${h}:${m}:${s}`;
  const fts = el('footer-ts');
  if (fts) fts.textContent = now.toLocaleDateString('en-GB', {
    day:'2-digit', month:'short', year:'numeric'
  });
}
setInterval(updateClock, 1000);
updateClock();

// ── Status ────────────────────────────────────────────────────────────────────

async function loadStatus() {
  const d = await fetchJSON(API.status);
  if (!d) return;
  const s = el('agent-status');
  if (s) {
    s.textContent = d.status.toUpperCase();
    s.className   = d.status === 'online' ? 'green' : 'red';
  }
}

// ── Execution log ─────────────────────────────────────────────────────────────

async function loadExecutions() {
  const data = await fetchJSON(API.executions);
  if (!data) return;

  // Update metrics
  metrics.total    = data.length;
  metrics.success  = data.filter(e => e.success).length;
  metrics.failed   = data.length - metrics.success;
  metrics.duration = data.reduce((a, e) => a + (e.duration || 0), 0).toFixed(1);

  const ms = el('m-success'); if (ms) ms.textContent = metrics.success;
  const mf = el('m-failed');  if (mf) mf.textContent = metrics.failed;
  const mt = el('m-total');   if (mt) mt.textContent = metrics.total;
  const md = el('m-duration');if (md) md.textContent = `${metrics.duration}s`;

  // Exec log (latest 8)
  const log = el('exec-log');
  if (!log) return;
  const recent = data.slice(-8).reverse();
  if (!recent.length) { log.innerHTML = '<div class="term-line dim">No executions</div>'; return; }

  log.innerHTML = recent.map(e => `
    <div class="exec-item">
      <span class="exec-tool ${e.success ? 'ok' : 'err'}">${e.success ? '✓' : '✗'} ${e.tool || '?'}</span>
      <span class="exec-dur">${e.duration || 0}s</span>
    </div>
  `).join('');

  // Also push to terminal if new
  const last = data[data.length - 1];
  if (last && last._seen !== true) {
    addTermLine(
      `[exec] ${last.tool} ${last.args?.slice(0,3).join(' ') || ''} → ${last.success ? 'OK' : 'FAIL'} (${last.duration}s)`,
      last.success ? 'ok' : 'err'
    );
  }
}

// ── Workflow log ──────────────────────────────────────────────────────────────

async function loadWorkflows() {
  const data = await fetchJSON(API.workflows);
  const wfEl = el('workflow-steps');
  const badge = el('workflow-badge');
  if (!data || !data.length) {
    if (wfEl) wfEl.innerHTML = '<div class="step-placeholder">No active workflow</div>';
    if (badge) { badge.textContent = 'IDLE'; badge.className = 'badge'; }
    el('progress-bar').style.width = '0%';
    return;
  }

  const last  = data[data.length - 1];
  const steps = last.steps || [];
  const done  = steps.filter(s => s.success !== undefined).length;
  const total = steps.length;
  const pct   = total ? Math.round(done / total * 100) : 0;

  if (badge) {
    badge.textContent = last.success ? 'DONE' : (done < total ? 'RUNNING' : 'PARTIAL');
    badge.className   = 'badge ' + (last.success ? 'green' : (done < total ? 'amber' : 'red'));
  }
  el('progress-bar').style.width = pct + '%';

  if (wfEl) {
    wfEl.innerHTML = steps.map(s => {
      const cls = s.success === true  ? 'done'
                : s.success === false ? 'failed'
                : 'running';
      const icon = s.success === true  ? '✓'
                 : s.success === false ? '✗'
                 : '►';
      const cnt = s.output_count ? ` — ${s.output_count} results` : '';
      return `
        <div class="workflow-step ${cls}">
          <span class="step-icon">${icon}</span>
          <span class="step-name">${s.name || s.tool}</span>
          <span class="step-tool">[${s.tool}]</span>
          <span class="step-dur">${s.duration || 0}s${cnt}</span>
        </div>
      `;
    }).join('');
  }
}

// ── Findings (from nuclei/vuln outputs) ──────────────────────────────────────

function renderFindings(findings) {
  const tbl = el('findings-table');
  const cnt = el('finding-count');
  if (!tbl) return;
  if (!findings.length) {
    tbl.innerHTML = '<div class="term-line dim">No findings</div>';
    if (cnt) { cnt.textContent = '0'; cnt.className = 'badge'; }
    return;
  }
  if (cnt) {
    cnt.textContent = findings.length;
    cnt.className   = findings.length > 0 ? 'badge red' : 'badge';
  }
  tbl.innerHTML = findings.slice(-20).map(f => {
    const sev  = (f.severity || 'info').toLowerCase();
    const name = f.name || f.template || f.finding || '—';
    const host = f.host || f.url || '';
    return `
      <div class="finding-row">
        <span class="sev-badge sev-${sev}">${sev.toUpperCase()}</span>
        <span>${name}</span>
        <span style="color:var(--dim);font-size:.7rem;overflow:hidden;text-overflow:ellipsis">${host}</span>
      </div>
    `;
  }).join('');
}

// ── Actions ───────────────────────────────────────────────────────────────────

function triggerRecon() {
  const target = prompt('Target domain (e.g. example.com):');
  if (!target) return;
  addTermLine(`[►] Starting recon workflow → ${target}`, 'info');
  fetch(`/api/recon?target=${encodeURIComponent(target)}`)
    .catch(() => addTermLine('[!] API not available — run dashboard_launcher.py', 'warn'));
}

function triggerWeb() {
  const url = prompt('Target URL (e.g. https://example.com):');
  if (!url) return;
  addTermLine(`[►] Starting web assessment → ${url}`, 'info');
  fetch(`/api/web?target=${encodeURIComponent(url)}`)
    .catch(() => addTermLine('[!] API not available — run dashboard_launcher.py', 'warn'));
}

function openTerminal() {
  fetch('/api/terminal/open')
    .then(() => addTermLine('[►] Terminal window opened', 'ok'))
    .catch(() => addTermLine('[!] Terminal API unavailable', 'warn'));
}

// ── Load all ──────────────────────────────────────────────────────────────────

async function loadAll() {
  await Promise.all([loadStatus(), loadExecutions(), loadWorkflows()]);
}

// ── Init ──────────────────────────────────────────────────────────────────────

window.addEventListener('DOMContentLoaded', () => {
  loadAll();
  _timer = setInterval(loadAll, REFRESH_MS);
  addTermLine('NEXUS SOC Dashboard initialized', 'info');
  addTermLine(`Auto-refresh every ${REFRESH_MS / 1000}s`, 'dim');
});

// Expose for inline onclick
window.triggerRecon  = triggerRecon;
window.triggerWeb    = triggerWeb;
window.openTerminal  = openTerminal;
window.loadAll       = loadAll;
