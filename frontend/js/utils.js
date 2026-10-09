/**
 * NexusIT / RelayDesk — Shared rendering helpers.
 * Use these for every value interpolated into an innerHTML template.
 */

const HTML_ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };

/** Escape a value for safe use in HTML text or a quoted attribute. */
export function escapeHtml(value) {
  if (value === null || value === undefined) return '';
  return String(value).replace(/[&<>"']/g, ch => HTML_ESCAPES[ch]);
}

/**
 * Return an attribute-safe URL, or '#' if the scheme is not allowed.
 * Blocks javascript:, vbscript: and other script-capable schemes.
 */
export function safeUrl(url) {
  if (typeof url !== 'string') return '#';
  const trimmed = url.trim();
  if (/^(https?:|data:(image|application|text\/plain|audio|video)\/?[\w.+-]*[;,])/i.test(trimmed)
      || trimmed.startsWith('/') && !trimmed.startsWith('//')) {
    return escapeHtml(trimmed);
  }
  return '#';
}
