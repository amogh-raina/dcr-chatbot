// randomUUID may be unavailable on HTTP origins such as 0.0.0.0.
// getRandomValues still supplies cryptographically random session identifiers.
export function newSessionId(cryptoApi = globalThis.crypto) {
  if (typeof cryptoApi?.randomUUID === 'function') return cryptoApi.randomUUID();
  const bytes = new Uint8Array(16);
  cryptoApi.getRandomValues(bytes);
  return Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
}
