import test from 'node:test';
import assert from 'node:assert/strict';
import { sessionSummary } from './player-state.js';
const base = { games: [], worlds: [], local_worlds: [], offline_saves: [], hosting: { worlds: [] }, connected: false, trainer: null };
test('a launcher session never claims a connected game without live telemetry', () => {
  const state = { ...base, connected: true, trainer: 'May' };
  assert.equal(sessionSummary(state).status, 'Ready to launch');
  assert.equal(sessionSummary({ ...state, games: ['May'] }).status, 'Waiting for game connection');
  assert.equal(sessionSummary({ ...state, games: ['May'], presence: { state: 'connected' } }).status, 'Game connected');
  assert.equal(sessionSummary({ ...state, games: ['May'], presence: { state: 'disconnected' } }).tone, 'error');
});
test('offline status ignores stale online telemetry and resolves the actual save', () => {
  const session = sessionSummary({ ...base, games: ['offline/May'], offline_world_key: 'solo-2', presence: { state: 'disconnected' },
    offline_saves: [{ world: 'solo-1', trainer: 'May', name: 'First' }, { world: 'solo-2', trainer: 'May', name: 'Second' }] });
  assert.equal(session.name, 'Second');
  assert.equal(session.mode, 'Solo');
  assert.equal(session.status, 'Offline game running');
});
test('local and hosted identities are separate from the trainer identity', () => {
  const state = { ...base, world_key: 'local', trainer: 'May', connected: true, local_host: true, local_worlds: [{ key: 'local', name: 'Cave lab' }] };
  assert.equal(sessionSummary(state).name, 'Cave lab');
  assert.equal(sessionSummary(state).mode, 'Local');
  assert.equal(sessionSummary({ ...state, local_host: false, world_key: 'hosted-id', hosting: { worlds: [{ id: 'id', name: 'Friends' }] } }).name, 'Friends');
});
