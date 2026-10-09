/**
 * NexusIT / RelayDesk — Standard API Client
 */

const API_BASE = (window.location.port && window.location.port !== '8000')
  ? 'http://localhost:8000'
  : window.location.origin;

// FastAPI returns a string for HTTP errors and a list of field errors for 422s
function formatErrorDetail(detail) {
  if (!detail) return '';
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map(d => {
      const field = Array.isArray(d.loc) ? d.loc.filter(p => p !== 'body').join('.') : '';
      return field ? `${field}: ${d.msg}` : d.msg;
    }).join('; ');
  }
  return String(detail);
}

// Auth uses an httpOnly session cookie set by /auth/login. JavaScript never
// sees the token; the browser attaches the cookie (credentials: 'include').
// The X-Requested-With header is the server's CSRF check for cookie sessions.
export async function apiRequest(endpoint, options = {}) {
  const headers = {
    'Accept': 'application/json',
    'X-Requested-With': 'XMLHttpRequest',
    ...(options.headers || {})
  };

  if (options.body && !(options.body instanceof FormData) && typeof options.body === 'object') {
    headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(options.body);
  }

  try {
    const url = endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint.startsWith('/') ? '' : '/'}${endpoint}`;
    const res = await fetch(url, { ...options, headers, credentials: 'include' });

    if (res.status === 401 && !window.location.pathname.endsWith('login.html')) {
      localStorage.removeItem('nexus_user');
      window.location.href = '/login.html';
      throw new Error('Session expired. Please log in again.');
    }

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(formatErrorDetail(errData.detail) || `Request failed with status ${res.status}`);
    }

    if (res.status === 204) return null;
    return await res.json();
  } catch (err) {
    console.error('API Error:', err);
    throw err;
  }
}
