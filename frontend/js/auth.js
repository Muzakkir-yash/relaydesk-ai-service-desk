/**
 * NexusIT / RelayDesk — Authentication Module
 *
 * The session token lives in an httpOnly cookie that JavaScript cannot read.
 * localStorage only caches the (non-secret) user profile for rendering the
 * UI; the server re-checks the cookie on every request.
 */
import { apiRequest } from './api.js';

// Tokens stored by older versions of the app — removed on load
localStorage.removeItem('nexus_token');

export function getUser() {
  const userJson = localStorage.getItem('nexus_user');
  if (!userJson) return null;
  try {
    return JSON.parse(userJson);
  } catch {
    return null;
  }
}

export function setSession(user) {
  localStorage.setItem('nexus_user', JSON.stringify(user));
}

export function clearSession() {
  localStorage.removeItem('nexus_user');
}

export async function login(email, password) {
  await apiRequest('/auth/login', {
    method: 'POST',
    body: { email, password }
  });
  const user = await apiRequest('/auth/me');
  setSession(user);
  return user;
}

export async function register(userData) {
  await apiRequest('/auth/register', {
    method: 'POST',
    body: {
      name: userData.name,
      email: userData.email,
      password: userData.password,
      team: userData.team || 'General',
      primary_device: userData.primary_device || {
        branch: userData.branch || 'US-NYC',
        office_location: userData.office_location || 'New York HQ',
        device_name: userData.device_name || 'CORP-WORKSTATION'
      }
    }
  });
  return await login(userData.email, userData.password);
}

export async function logout() {
  try {
    await apiRequest('/auth/logout', { method: 'POST' });
  } catch {
    // Clear the local profile even if the server is unreachable
  }
  clearSession();
  window.location.href = '/login.html';
}

export function requireAuth(allowedRoles = []) {
  const user = getUser();

  // No cached profile means no session; an expired cookie is caught by the
  // first API call, which redirects to the login page on 401.
  if (!user) {
    window.location.href = '/login.html';
    return null;
  }

  if (allowedRoles.length > 0 && !allowedRoles.includes(user.role)) {
    // Redirect to their default landing page
    if (user.role === 'technician') window.location.href = '/queue.html';
    else if (user.role === 'admin') window.location.href = '/metrics.html';
    else window.location.href = '/tickets.html';
    return null;
  }

  return user;
}
