import { test } from 'node:test';
import assert from 'node:assert/strict';
import { webcrypto } from 'node:crypto';
import { newSessionId } from './sessionId.js';

test('uses randomUUID when available', () => {
  assert.equal(newSessionId({ randomUUID: () => 'secure-session-id' }), 'secure-session-id');
});
test('creates distinct session IDs when randomUUID is unavailable', () => {
  const httpCrypto = { getRandomValues: values => webcrypto.getRandomValues(values) };
  const ids = Array.from({ length: 10 }, () => newSessionId(httpCrypto));
  assert.equal(new Set(ids).size, 10);
  for (const id of ids) assert.match(id, /^[a-f0-9]{32}$/);
});
