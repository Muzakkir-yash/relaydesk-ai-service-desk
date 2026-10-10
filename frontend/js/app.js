/**
 * NexusIT / RelayDesk — Core UI Framework & Layout Engine
 * User-Friendly Navigation, Fast Persona Switcher, Audio Alerts & Responsive Shell
 */
import { getUser, logout } from './auth.js';
import { apiRequest } from './api.js';
import { escapeHtml } from './utils.js';

export function playAlertChime() {
  try {
    if (localStorage.getItem('nexus_sound_alerts') === 'false') return;

    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    const now = ctx.currentTime;

    const osc1 = ctx.createOscillator();
    const gain1 = ctx.createGain();
    osc1.type = 'sine';
    osc1.frequency.setValueAtTime(880, now);
    gain1.gain.setValueAtTime(0.08, now);
    gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.18);
    osc1.connect(gain1);
    gain1.connect(ctx.destination);
    osc1.start(now);
    osc1.stop(now + 0.18);

    const osc2 = ctx.createOscillator();
    const gain2 = ctx.createGain();
    osc2.type = 'sine';
    osc2.frequency.setValueAtTime(1174.66, now + 0.1);
    gain2.gain.setValueAtTime(0.06, now + 0.1);
    gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
    osc2.connect(gain2);
    gain2.connect(ctx.destination);
    osc2.start(now + 0.1);
    osc2.stop(now + 0.35);
  } catch (err) {
    console.debug('Audio chime unable to play:', err);
  }
}

export function showToast(message, type = 'info') {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }

  const icons = {
    success: '✓',
    error: '✕',
    info: 'ℹ'
  };

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <span style="display:inline-flex; align-items:center; justify-content:center; width:20px; height:20px; border-radius:50%; background:${type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#4f46e5'}; color:white; font-size:11px; font-weight:800; flex-shrink:0;">
      ${icons[type] || '•'}
    </span>
    <span style="flex:1;">${escapeHtml(message)}</span>
  `;

  container.appendChild(toast);

  if (type === 'error' || type === 'info') {
    playAlertChime();
  }

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(30px)';
    toast.style.transition = 'all 0.25s ease';
    setTimeout(() => toast.remove(), 250);
  }, 3500);
}

const ICONS = {
  tickets: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 9a3 3 0 0 1 0 6v2a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-2a3 3 0 0 1 0-6V7a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2Z"/><path d="M13 5v2"/><path d="M13 17v2"/><path d="M13 11v2"/></svg>`,
  newTicket: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M8 12h8"/><path d="M12 8v8"/></svg>`,
  queue: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/><path d="M12 18H2"/></svg>`,
  kb: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1-2.5-2.5Z"/><path d="M6 6h10"/><path d="M6 10h10"/></svg>`,
  metrics: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></svg>`,
  users: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>`,
  audit: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M16 13H8"/><path d="M16 17H8"/><path d="M10 9H8"/></svg>`,
  guide: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/></svg>`,
  logout: `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" x2="9" y1="12" y2="12"/></svg>`
};

const NAV_CONFIG = {
  enduser: [
    { to: '/tickets.html', label: 'My Tickets', icon: ICONS.tickets },
    { to: '/new-ticket.html', label: 'Submit Ticket', icon: ICONS.newTicket },
    { to: '/kb.html', label: 'Knowledge Base', icon: ICONS.kb },
  ],
  technician: [
    { to: '/queue.html', label: 'Ticket Queue', icon: ICONS.queue },
    { to: '/new-ticket.html', label: 'Submit Ticket', icon: ICONS.newTicket },
    { to: '/kb.html', label: 'Knowledge Base', icon: ICONS.kb },
    { to: '/metrics.html', label: 'Metrics', icon: ICONS.metrics },
  ],
  admin: [
    { to: '/metrics.html', label: 'Dashboard', icon: ICONS.metrics },
    { to: '/queue.html', label: 'Ticket Queue', icon: ICONS.queue },
    { to: '/kb.html', label: 'Knowledge Base', icon: ICONS.kb },
    { to: '/tickets.html', label: 'All Tickets', icon: ICONS.tickets },
    { to: '/users.html', label: 'User Directory', icon: ICONS.users },
    { to: '/audit.html', label: 'Audit Log', icon: ICONS.audit },
  ],
};

export function renderLayout(pageTitle = 'NexusIT', activeNav = '') {
  const user = getUser();
  const currentRole = user?.role || 'enduser';
  const navItems = NAV_CONFIG[currentRole] || NAV_CONFIG.enduser;
  const initials = escapeHtml((user?.name?.trim()?.[0] || user?.email?.trim()?.[0] || 'U').toUpperCase());
  const soundEnabled = localStorage.getItem('nexus_sound_alerts') !== 'false';

  const sidebarHtml = `
    <aside class="sidebar" id="app-sidebar">
      <div class="sidebar-header">
        <div class="brand-logo-wrap">
          <img src="/assets/logo.jpg" alt="NexusIT" style="width: 100%; height: 100%; object-fit: cover;" />
        </div>
        <div>
          <div class="brand-title">NexusIT</div>
          <div class="brand-subtitle">Enterprise Service Desk</div>
        </div>
      </div>
      
      <div class="sidebar-body">
        <div>
          <div class="nav-section-title">Navigation</div>
          <ul class="nav-list">
            ${navItems.map(item => `
              <li>
                <a href="${item.to}" class="nav-link ${activeNav === item.to || window.location.pathname.endsWith(item.to) ? 'active' : ''}">
                  <span class="nav-icon">${item.icon}</span>
                  <span>${item.label}</span>
                </a>
              </li>
            `).join('')}
          </ul>
        </div>

        <div>
          <div class="nav-section-title">Assistance</div>
          <ul class="nav-list">
            <li>
              <a href="javascript:void(0)" id="open-guide-btn" class="nav-link">
                <span class="nav-icon">${ICONS.guide}</span>
                <span>System Guide & Tour</span>
              </a>
            </li>
          </ul>
        </div>
      </div>

      <div class="sidebar-footer">
        <div class="user-profile-widget">
          <div class="user-avatar">${initials}</div>
          <div class="user-info">
            <div class="user-name">${escapeHtml(user?.name || user?.email || 'User')}</div>
            <div class="user-role-tag">${user?.role === 'technician' ? `TECH • ${escapeHtml(user?.support_level || 'L1')}`: user?.role === 'admin' ? 'ADMINISTRATOR' : 'END USER'}</div>
          </div>
          <button id="change-pw-btn" class="btn btn-ghost btn-sm" title="Change password" style="padding: 6px; border-radius: var(--radius-sm);">🔑</button>
          <button id="logout-btn" class="btn btn-ghost btn-sm" title="Sign out" style="padding: 6px; border-radius: var(--radius-sm);">
            ${ICONS.logout}
          </button>
        </div>
      </div>
    </aside>
  `;

  const headerHtml = `
    <header class="top-header">
      <div style="display: flex; align-items: center; gap: 12px;">
        <button id="mobile-menu-btn" class="btn btn-ghost btn-sm" style="display: none; padding: 6px 10px;" title="Toggle Menu">
          ☰
        </button>
        <div class="page-title">${escapeHtml(pageTitle)}</div>
      </div>
      
      <div class="header-actions">
        <!-- Live Office & Connection Status -->
        <div style="display: flex; align-items: center; gap: 7px; background: #ffffff; border: 1px solid var(--border-main); padding: 5px 12px; border-radius: var(--radius-full); font-size: 11.5px; font-weight: 600; color: var(--text-body); box-shadow: var(--shadow-xs);">
          <span style="width: 7px; height: 7px; border-radius: 50%; background: #10b981; display: inline-block;"></span>
          <span>${escapeHtml(user?.primary_device?.office_location || user?.office_location || user?.branch || 'Connected')}</span>
        </div>

        <!-- Sound Toggle -->
        <button id="sound-toggle-btn" class="btn btn-ghost btn-sm" title="Toggle audio chime notifications" style="padding: 6px 10px;">
          ${soundEnabled ? '🔔 Sound' : '🔕 Muted'}
        </button>

        ${(currentRole === 'technician' || currentRole === 'admin') ? `
          <button id="mim-broadcast-btn" class="btn btn-secondary btn-sm" style="color: #dc2626; border-color: #fecaca; background: #fef2f2;">
            Broadcast Outage
          </button>
        ` : ''}

        <button id="guide-top-btn" class="btn btn-primary btn-sm" style="padding: 6px 12px;">
          💡 Guide
        </button>
      </div>
    </header>
  `;

  // Insert into page structure
  const appContainer = document.querySelector('.app-container');
  if (appContainer) {
    appContainer.insertAdjacentHTML('afterbegin', sidebarHtml);
    const mainWrapper = document.querySelector('.main-wrapper');
    if (mainWrapper) {
      mainWrapper.insertAdjacentHTML('afterbegin', headerHtml);
    }
  }

  // Responsive mobile menu toggle
  const mobileBtn = document.getElementById('mobile-menu-btn');
  const sidebar = document.getElementById('app-sidebar');
  if (window.innerWidth <= 768 && mobileBtn) {
    mobileBtn.style.display = 'inline-flex';
    mobileBtn.addEventListener('click', () => {
      sidebar?.classList.toggle('mobile-open');
    });
  }

  // Bind logout
  document.getElementById('logout-btn')?.addEventListener('click', () => logout());
  document.getElementById('change-pw-btn')?.addEventListener('click', () => openChangePasswordModal());

  // Sound Toggle handler (silent toggle without popup toast)
  const soundBtn = document.getElementById('sound-toggle-btn');
  soundBtn?.addEventListener('click', () => {
    const isNowMuted = localStorage.getItem('nexus_sound_alerts') !== 'false';
    localStorage.setItem('nexus_sound_alerts', isNowMuted ? 'false' : 'true');
    soundBtn.textContent = isNowMuted ? '🔕 Muted' : '🔔 Sound';
    soundBtn.title = isNowMuted ? 'Audio Alerts: Muted (Click to Enable)' : 'Audio Alerts: Enabled (Click to Mute)';
  });
  
  // Bind Guide modal
  const openGuide = () => renderSystemGuideModal();
  document.getElementById('open-guide-btn')?.addEventListener('click', openGuide);
  document.getElementById('guide-top-btn')?.addEventListener('click', openGuide);

  // Bind Broadcast modal for Tech/Admin
  document.getElementById('mim-broadcast-btn')?.addEventListener('click', () => renderBroadcastModal());

  // Check and display Global Outage Banner
  loadGlobalOutageBanner();
}

export async function loadGlobalOutageBanner() {
  try {
    // The endpoint returns a list of active banners, newest first
    const banners = await apiRequest('/announcements/active');
    const banner = Array.isArray(banners) ? banners[0] : banners;
    if (!banner || !banner.is_active) return;

    const contentBody = document.querySelector('.content-body');
    if (!contentBody) return;

    const role = getUser()?.role;
    const isStaff = role === 'technician' || role === 'admin';

    // Check if dismissed in session
    if (sessionStorage.getItem(`dismiss_outage_${banner.id}`)) return;

    const bannerHtml = `
      <div class="outage-banner" id="global-outage-banner">
        <div style="display: flex; align-items: center; gap: 14px;">
          <span class="outage-badge">MAJOR INCIDENT</span>
          <div>
            <div class="outage-title">${escapeHtml(banner.title)}</div>
            <div class="outage-desc">${escapeHtml(banner.message)}</div>
          </div>
        </div>
        <div style="display: flex; align-items: center; gap: 8px;">
          ${banner.workaround ? `
            <button id="view-workaround-btn" class="btn btn-secondary btn-sm" style="font-weight: 700; border-color: #fde68a; background: #ffffff;">
              View Workaround
            </button>
          ` : ''}
          ${isStaff ? `
            <button id="resolve-outage-btn" class="btn btn-secondary btn-sm" style="font-weight: 700; border-color: #bbf7d0; background: #f0fdf4; color: #166534;" title="End this incident for everyone">
              ✓ Mark resolved
            </button>
          ` : ''}
          <button id="dismiss-outage-btn" class="btn btn-ghost btn-sm" style="padding: 4px 8px;" title="Hide for me">✕</button>
        </div>
      </div>
    `;

    contentBody.insertAdjacentHTML('afterbegin', bannerHtml);

    document.getElementById('dismiss-outage-btn')?.addEventListener('click', () => {
      sessionStorage.setItem(`dismiss_outage_${banner.id}`, 'true');
      document.getElementById('global-outage-banner')?.remove();
    });

    document.getElementById('view-workaround-btn')?.addEventListener('click', () => {
      renderWorkaroundModal(banner);
    });

    // Staff end the incident for everyone (the ✕ only hides it for one person)
    document.getElementById('resolve-outage-btn')?.addEventListener('click', async () => {
      if (!confirm(`Mark "${banner.title}" as resolved? The banner disappears for everyone.`)) return;
      try {
        await apiRequest(`/announcements/${banner.id}`, { method: 'PATCH', body: { is_active: false } });
        document.getElementById('global-outage-banner')?.remove();
        showToast('Incident marked as resolved.', 'success');
      } catch (err) {
        showToast('Could not resolve incident: ' + err.message, 'error');
      }
    });
  } catch (err) {
    console.debug('No active outage announcements:', err);
  }
}

export function renderWorkaroundModal(banner) {
  const modalHtml = `
    <div class="modal-overlay open" id="workaround-modal">
      <div class="modal-card">
        <div class="modal-header">
          <div style="font-weight: 700; font-size: 15px; color: #92400e; display: flex; align-items: center; gap: 8px;">
            <span>⚠️</span>
            <span>${escapeHtml(banner.title)} — Active Workaround</span>
          </div>
          <button class="btn btn-ghost btn-sm close-modal-btn">✕</button>
        </div>
        <div class="modal-body">
          <div style="padding: 16px; background: #fffbeb; border: 1px solid #fde68a; border-radius: var(--radius-md); font-size: 13.5px; line-height: 1.6; color: #78350f; white-space: pre-wrap;">${escapeHtml(banner.workaround)}</div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-primary btn-sm close-modal-btn">Close</button>
        </div>
      </div>
    </div>
  `;
  document.body.insertAdjacentHTML('beforeend', modalHtml);
  document.querySelectorAll('.close-modal-btn').forEach(btn => {
    btn.addEventListener('click', () => document.getElementById('workaround-modal')?.remove());
  });
}

export function renderBroadcastModal() {
  const modalHtml = `
    <div class="modal-overlay open" id="broadcast-modal">
      <div class="modal-card">
        <div class="modal-header">
          <div style="font-weight: 700; font-size: 16px; color: #dc2626;">Broadcast Major Incident Alert</div>
          <button class="btn btn-ghost btn-sm close-broadcast-btn">✕</button>
        </div>
        <form id="broadcast-form" class="modal-body">
          <div class="form-group">
            <label class="form-label">Outage Incident Title</label>
            <input type="text" id="bc-title" class="form-input" placeholder="e.g. VPN Gateway Intermittent Degradation" required />
          </div>
          <div class="form-group">
            <label class="form-label">Impact Scope & Summary</label>
            <textarea id="bc-message" class="form-textarea" placeholder="Describe the impact on enterprise users..." required></textarea>
          </div>
          <div class="form-group">
            <label class="form-label">Temporary Workaround (Optional)</label>
            <textarea id="bc-workaround" class="form-textarea" placeholder="Step-by-step interim workaround for affected users..."></textarea>
          </div>
        </form>
        <div class="modal-footer">
          <button type="button" class="btn btn-secondary btn-sm close-broadcast-btn">Cancel</button>
          <button type="submit" form="broadcast-form" class="btn btn-danger btn-sm">Broadcast to All Users</button>
        </div>
      </div>
    </div>
  `;
  document.body.insertAdjacentHTML('beforeend', modalHtml);

  document.querySelectorAll('.close-broadcast-btn').forEach(btn => {
    btn.addEventListener('click', () => document.getElementById('broadcast-modal')?.remove());
  });

  document.getElementById('broadcast-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const title = document.getElementById('bc-title').value;
    const message = document.getElementById('bc-message').value;
    const workaround = document.getElementById('bc-workaround').value;

    try {
      await apiRequest('/announcements', {
        method: 'POST',
        body: { title, message, workaround, severity: 'major', is_active: true }
      });
      showToast('Global announcement broadcasted successfully!', 'success');
      document.getElementById('broadcast-modal')?.remove();
      setTimeout(() => window.location.reload(), 800);
    } catch (err) {
      showToast('Failed to broadcast: ' + err.message, 'error');
    }
  });
}

export function renderSystemGuideModal() {
  const modalHtml = `
    <div class="modal-overlay open" id="system-guide-modal">
      <div class="modal-card" style="max-width: 620px;">
        <div class="modal-header">
          <div style="font-weight: 800; font-size: 16px; color: var(--text-main); display: flex; align-items: center; gap: 8px;">
            <span>💡</span>
            <span>NexusIT Service Desk — Architecture & Guide</span>
          </div>
          <button class="btn btn-ghost btn-sm close-guide-btn">✕</button>
        </div>
        <div class="modal-body" style="display: flex; flex-direction: column; gap: 16px;">
          <div style="padding: 16px; background: #eef2ff; border: 1px solid #c7d2fe; border-radius: var(--radius-lg); font-size: 13px; color: #3730a3; line-height: 1.6;">
            <strong>Context-Preserving AI Handover:</strong> Tickets are auto-triaged with live SLA countdowns, self-service automated deflection, and complete diagnostic briefings for technicians so users never repeat themselves.
          </div>

          <div>
            <div style="font-weight: 700; font-size: 13.5px; color: var(--text-main); margin-bottom: 8px;">Role-Based Access Control (RBAC):</div>
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;">
              <div style="background: var(--bg-card-subtle); padding: 14px 10px; text-align: center; border-radius: var(--radius-md); border: 1px solid var(--border-main);">
                <span style="font-size: 18px; margin-bottom: 4px; display: block;">👤</span>
                <strong style="font-size: 13px; color: var(--text-main);">End User</strong>
                <div style="font-size: 11px; color: var(--primary); font-weight: 600; margin-top: 4px;">Submit & Track Requests</div>
              </div>
              <div style="background: var(--bg-card-subtle); padding: 14px 10px; text-align: center; border-radius: var(--radius-md); border: 1px solid var(--border-main);">
                <span style="font-size: 18px; margin-bottom: 4px; display: block;">🔧</span>
                <strong style="font-size: 13px; color: var(--text-main);">Technician</strong>
                <div style="font-size: 11px; color: #7c3aed; font-weight: 600; margin-top: 4px;">Queue Triage & Remote Tools</div>
              </div>
              <div style="background: var(--bg-card-subtle); padding: 14px 10px; text-align: center; border-radius: var(--radius-md); border: 1px solid var(--border-main);">
                <span style="font-size: 18px; margin-bottom: 4px; display: block;">🛡️</span>
                <strong style="font-size: 13px; color: var(--text-main);">Administrator</strong>
                <div style="font-size: 11px; color: #d97706; font-weight: 600; margin-top: 4px;">Metrics, SLA & User Management</div>
              </div>
            </div>
          </div>

          <div style="background: var(--bg-card-subtle); padding: 14px; border-radius: var(--radius-md); border: 1px solid var(--border-main); font-size: 12.5px; color: var(--text-muted); line-height: 1.6;">
            <strong>Security Notice:</strong> Role-based access control (RBAC) is enforced server-side. To switch accounts, log out and sign in with the designated corporate credentials.
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-primary btn-sm close-guide-btn">Got It</button>
        </div>
      </div>
    </div>
  `;
  document.body.insertAdjacentHTML('beforeend', modalHtml);

  const modalEl = document.getElementById('system-guide-modal');
  modalEl?.addEventListener('click', (e) => {
    if (e.target === modalEl) modalEl.remove();
  });

  document.querySelectorAll('.close-guide-btn').forEach(btn => {
    btn.addEventListener('click', () => document.getElementById('system-guide-modal')?.remove());
  });
}


export function openChangePasswordModal() {
  document.getElementById('change-pw-modal')?.remove();
  document.body.insertAdjacentHTML('beforeend', `
    <div class="modal-overlay open" id="change-pw-modal">
      <div class="modal-card" style="max-width: 420px;">
        <div class="modal-header">
          <h3 style="font-size: 16px; font-weight: 800; color: var(--text-main);">Change password</h3>
          <button class="btn btn-ghost btn-sm close-pw-modal">✕</button>
        </div>
        <form id="change-pw-form" class="modal-body">
          <div class="form-group">
            <label class="form-label" for="cp-current">Current password</label>
            <input type="password" id="cp-current" class="form-input" required autocomplete="current-password" />
          </div>
          <div class="form-group">
            <label class="form-label" for="cp-new">New password (at least 8 characters)</label>
            <input type="password" id="cp-new" class="form-input" minlength="8" maxlength="128" required autocomplete="new-password" />
          </div>
          <div class="form-group">
            <label class="form-label" for="cp-confirm">Confirm new password</label>
            <input type="password" id="cp-confirm" class="form-input" minlength="8" maxlength="128" required autocomplete="new-password" />
          </div>
          <p style="font-size: 11.5px; color: var(--text-muted);">Other devices signed in to your account will be signed out.</p>
        </form>
        <div class="modal-footer">
          <button type="button" class="btn btn-secondary btn-sm close-pw-modal">Cancel</button>
          <button type="submit" form="change-pw-form" class="btn btn-primary btn-sm">Save</button>
        </div>
      </div>
    </div>
  `);
  const modal = document.getElementById('change-pw-modal');
  modal.querySelectorAll('.close-pw-modal').forEach(b => b.addEventListener('click', () => modal.remove()));
  document.getElementById('change-pw-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const newPassword = document.getElementById('cp-new').value;
    if (newPassword !== document.getElementById('cp-confirm').value) {
      showToast("The new passwords don't match.", 'error');
      return;
    }
    try {
      await apiRequest('/auth/change-password', {
        method: 'POST',
        body: { current_password: document.getElementById('cp-current').value, new_password: newPassword }
      });
      modal.remove();
      showToast('Password changed.', 'success');
    } catch (err) {
      showToast(err.message, 'error');
    }
  });
}
