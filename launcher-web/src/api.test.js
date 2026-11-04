import test from 'node:test';
import assert from 'node:assert/strict';
import { getCapability, loadState, perform } from './api.js';

test('capability leaves the URL and is attached to local requests', async () => {
  const storage = new Map();
  globalThis.window = { location: { hash: '#test-capability', pathname: '/' } };
  globalThis.history = { replaceState: () => { window.location.hash = ''; } };
  globalThis.sessionStorage = { setItem: (k, v) => storage.set(k, v), getItem: k => storage.get(k) };
  assert.equal(getCapability(), 'test-capability');
  assert.equal(window.location.hash, '');
  const calls = [];
  globalThis.fetch = async (path, options) => {
    calls.push({ path, options });
    return { ok: true, json: async () => ({ worlds: [] }) };
  };
  const controller = new AbortController();
  await loadState({ signal: controller.signal });
  await perform('rejoin', { world: 'one' });
  assert.equal(calls[0].options.headers.Authorization, 'Bearer test-capability');
  assert.equal(calls[0].options.signal, controller.signal);
  assert.equal(calls[1].options.headers['Content-Type'], 'application/json');
  assert.deepEqual(JSON.parse(calls[1].options.body), { action: 'rejoin', payload: { world: 'one' } });
});
