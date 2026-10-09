/**
 * NexusIT / RelayDesk — SOP Quick-Fix Playbook Runner & Live Terminal Emulator
 */
import { apiRequest } from './api.js';
import { showToast } from './app.js';
import { escapeHtml } from './utils.js';

// IDs must match PLAYBOOK_CATALOG in backend/routers/tickets.py
const PLAYBOOK_OPTIONS = [
  { id: 'remote_dns_flush', name: 'Flush Remote DNS & Restart VPN Adapter', desc: 'Flushes the DNS resolver cache and cycles the AnyConnect adapter.' },
  { id: 'ad_password_reset', name: 'Reset AD Password & Send Temp Token', desc: 'Resets the Active Directory password and issues a one-time token.' },
  { id: 'exchange_resync', name: 'Re-sync Exchange Mailbox', desc: 'Refreshes Autodiscover and rebuilds the cached Outlook profile.' },
  { id: 'edr_scan', name: 'Trigger EDR Fast Scan', desc: 'Runs an on-demand CrowdStrike Falcon scan on the endpoint.' },
  { id: 'gpupdate_force', name: 'Force Group Policy & Kerberos Sync', desc: 'Runs gpupdate /force and re-issues the Kerberos TGT.' },
  { id: 'restart_spooler', name: 'Clear Print Spooler Queue', desc: 'Purges stalled spooler jobs and restarts the Spooler service.' }
];

export function openPlaybookModal(ticketId, hostname = 'CORP-HOST') {
  const modalHtml = `
    <div class="modal-overlay open" id="playbook-modal">
      <div class="modal-card" style="max-width: 680px;">
        <div class="modal-header">
          <div>
            <div style="font-weight: 700; font-size: 15px;">Automated SOP Remediation Playbooks</div>
            <div style="font-size: 11.5px; color: var(--text-muted); margin-top: 2px;">Target Host: <strong style="font-family: monospace; color: var(--text-main);">${escapeHtml(hostname)}</strong> <span style="color: #b45309;">(demo simulation)</span></div>
          </div>
          <button class="btn btn-ghost btn-sm close-pb-modal">✕</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label class="form-label">Select Standard Operating Procedure (SOP)</label>
            <select id="pb-select" class="form-select">
              ${PLAYBOOK_OPTIONS.map(p => `
                <option value="${p.id}">${p.name} — ${p.desc}</option>
              `).join('')}
            </select>
          </div>

          <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--text-muted); margin-bottom: 6px;">Live Execution Terminal (PowerShell Remoting)</div>
          <div class="terminal-window" id="terminal-screen">
            <div class="terminal-line" style="color: #8b949e;">[NexusIT Execution Agent v2.4 initialized]</div>
            <div class="terminal-line" style="color: #8b949e;">Ready. Select a playbook above and click "Execute SOP".</div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary btn-sm close-pb-modal">Close</button>
          <button id="run-pb-btn" class="btn btn-primary btn-sm">Execute SOP</button>
        </div>
      </div>
    </div>
  `;

  document.body.insertAdjacentHTML('beforeend', modalHtml);

  const modal = document.getElementById('playbook-modal');
  const term = document.getElementById('terminal-screen');
  const runBtn = document.getElementById('run-pb-btn');
  const select = document.getElementById('pb-select');

  document.querySelectorAll('.close-pb-modal').forEach(b => {
    b.addEventListener('click', () => modal.remove());
  });

  runBtn.addEventListener('click', async () => {
    const playbookId = select.value;
    runBtn.disabled = true;
    runBtn.textContent = 'Running...';
    select.disabled = true;

    term.innerHTML = `
      <div class="terminal-line terminal-info">[SIMULATION] Connecting to target host: ${escapeHtml(hostname)}...</div>
    `;

    try {
      const res = await apiRequest(`/tickets/${ticketId}/execute-playbook`, {
        method: 'POST',
        body: { playbook_id: playbookId, target_device: hostname }
      });

      const lines = (res.command_output || 'Playbook completed successfully.').split('\n');
      let idx = 0;

      const interval = setInterval(() => {
        if (idx < lines.length) {
          const line = lines[idx];
          const div = document.createElement('div');
          div.className = 'terminal-line';
          if (line.includes('[SUCCESS]') || line.includes('PASS') || line.includes('completed')) {
            div.className += ' terminal-success';
          } else if (line.includes('WARN') || line.includes('WARNING')) {
            div.className += ' terminal-warning';
          } else if (line.includes('ERROR') || line.includes('FAIL')) {
            div.className += ' terminal-error';
          }
          div.textContent = line;
          term.appendChild(div);
          term.scrollTop = term.scrollHeight;
          idx++;
        } else {
          clearInterval(interval);
          runBtn.disabled = false;
          runBtn.textContent = 'Re-run Playbook';
          select.disabled = false;
          showToast('Remediation playbook executed successfully!', 'success');
        }
      }, 160);
    } catch (err) {
      const div = document.createElement('div');
      div.className = 'terminal-line terminal-error';
      div.textContent = `[EXECUTION FAILED]: ${err.message}`;
      term.appendChild(div);
      runBtn.disabled = false;
      runBtn.textContent = 'Execute SOP';
      select.disabled = false;
      showToast('Playbook failed: ' + err.message, 'error');
    }
  });
}
