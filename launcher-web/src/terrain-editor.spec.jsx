// @vitest-environment jsdom
import React from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import TerrainEditor, { validTerrain } from './TerrainEditor';
import { App } from './main';
import { loadState, perform } from './api';
vi.mock('./api', () => ({ loadState: vi.fn(), perform: vi.fn(), forgetCapability: vi.fn() }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });
const area = { identity: 'a'.repeat(64), label: 'Forest mystery', kind: 'event_wilds', active: true };
const initial = { world: 'local', identity: area.identity, revision: 0, players: 0, rows: ['#'.repeat(63), ...Array(61).fill('#' + '.'.repeat(61) + '#'), '#'.repeat(63)], tiles: [], characters: [{ x: 2, y: 1 }] };
const props = { world: 'local', area, available: true, ready: true, busy: false, onBack: vi.fn() };
function handler() {
  return vi.fn(async (action, payload) => action === 'terrain_review' ? { ...initial, proposed_tiles: payload.tiles }
    : action === 'terrain_apply' ? { ...initial, revision: 1, saved: true, changed: true, tiles: payload.tiles } : initial);
}
async function paint() {
  const grid = await screen.findByRole('grid', { name: 'Terrain map' });
  fireEvent.click(screen.getByRole('button', { name: 'Tall grass' }));
  fireEvent.keyDown(grid, { key: ' ' });
  return grid;
}

it('edits a local draft and applies only the exact reviewed replacement', async () => {
  const request = handler(); render(<TerrainEditor {...props} onRequest={request} />);
  await paint();
  expect(request).toHaveBeenCalledTimes(1);
  expect(JSON.parse(screen.getByLabelText('Draft overlay JSON').value)).toEqual([{ x: 3, y: 3, terrain: 'tall_grass' }]);
  fireEvent.click(screen.getByRole('button', { name: 'Review terrain' }));
  await screen.findByRole('heading', { name: 'Apply terrain changes?' });
  expect(request).toHaveBeenCalledTimes(2);
  expect(screen.getByRole('button', { name: 'Water' }).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: 'Apply terrain' }));
  await screen.findByText(/Terrain saved at revision 1/);
  expect(request).toHaveBeenLastCalledWith('terrain_apply', { world: 'local', identity: area.identity, expected_revision: 0, tiles: [{ x: 3, y: 3, terrain: 'tall_grass' }], confirmed: true });
  expect(screen.getByRole('button', { name: 'Review terrain' }).disabled).toBe(true);
});

it('keeps connected games safe and refreshes review without losing the draft', async () => {
  let players = 1;
  const request = vi.fn(async (action, payload) => ({ ...initial, players, ...(action === 'terrain_review' ? { proposed_tiles: payload.tiles } : {}) }));
  render(<TerrainEditor {...props} onRequest={request} />);
  await paint(); fireEvent.click(screen.getByRole('button', { name: 'Review terrain' }));
  await screen.findByRole('heading', { name: 'Apply terrain changes?' });
  expect(screen.getByRole('button', { name: 'Apply terrain' }).disabled).toBe(true);
  players = 0;
  fireEvent.click(screen.getByRole('button', { name: 'Refresh review' }));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Apply terrain' }).disabled).toBe(false));
  expect(JSON.parse(screen.getByLabelText('Draft overlay JSON').value)).toHaveLength(1);
  expect(request.mock.calls.every(([action]) => action !== 'terrain_apply')).toBe(true);
});

it('supports keyboard selection, protected cells, undo and restoring the base as a draft', async () => {
  const request = handler(); render(<TerrainEditor {...props} onRequest={request} />);
  const grid = await paint();
  fireEvent.keyDown(grid, { key: 'ArrowRight' }); fireEvent.keyDown(grid, { key: 'Enter' });
  expect(JSON.parse(screen.getByLabelText('Draft overlay JSON').value)).toHaveLength(2);
  fireEvent.click(screen.getByRole('button', { name: 'Undo' }));
  expect(JSON.parse(screen.getByLabelText('Draft overlay JSON').value)).toHaveLength(1);
  fireEvent.click(screen.getByRole('button', { name: 'Restore base layout' }));
  expect(JSON.parse(screen.getByLabelText('Draft overlay JSON').value)).toEqual([]);
  for (let i = 0; i < 5; i++) fireEvent.keyDown(grid, { key: 'ArrowLeft' });
  fireEvent.keyDown(grid, { key: ' ' });
  expect(screen.getByRole('alert').textContent).toContain('protected');
  expect(request).toHaveBeenCalledTimes(1);
});

it('rejects stale review and keeps the draft instead of automatically overwriting', async () => {
  const request = handler(); render(<TerrainEditor {...props} onRequest={request} />);
  await paint(); request.mockResolvedValue({ ...initial, revision: 2, proposed_tiles: [] });
  fireEvent.click(screen.getByRole('button', { name: 'Review terrain' }));
  expect((await screen.findByRole('alert')).textContent).toContain('Terrain changed');
  expect(screen.queryByRole('button', { name: 'Apply terrain' })).toBeNull();
  expect(JSON.parse(screen.getByLabelText('Draft overlay JSON').value)).toHaveLength(1);
});

it('requires reload after an uncertain save and never retries automatically', async () => {
  const request = handler(); render(<TerrainEditor {...props} onRequest={request} />);
  await paint(); fireEvent.click(screen.getByRole('button', { name: 'Review terrain' }));
  await screen.findByRole('button', { name: 'Apply terrain' });
  request.mockResolvedValueOnce(false);
  fireEvent.click(screen.getByRole('button', { name: 'Apply terrain' }));
  await screen.findByText(/Nothing retries automatically/);
  expect(screen.getByRole('button', { name: 'Grass' }).disabled).toBe(true);
  expect(request.mock.calls.filter(([name]) => name === 'terrain_apply')).toHaveLength(1);
  request.mockResolvedValueOnce({ ...initial, revision: 1, tiles: [{ x: 3, y: 3, terrain: 'tall_grass' }] });
  fireEvent.click(screen.getByRole('button', { name: 'Discard draft & reload' }));
  await waitFor(() => expect(screen.queryByText(/Nothing retries automatically/)).toBeNull());
  expect(screen.getByRole('button', { name: 'Review terrain' }).disabled).toBe(true);
});

it('guards repeated saves and disables edits when the active area changes', async () => {
  let finish; const request = handler();
  const { rerender } = render(<TerrainEditor {...props} onRequest={request} />);
  await paint(); fireEvent.click(screen.getByRole('button', { name: 'Review terrain' }));
  await screen.findByRole('button', { name: 'Apply terrain' });
  request.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
  const apply = screen.getByRole('button', { name: 'Apply terrain' }); fireEvent.click(apply); fireEvent.click(apply);
  expect(request.mock.calls.filter(([name]) => name === 'terrain_apply')).toHaveLength(1);
  await act(async () => finish(false));
  rerender(<TerrainEditor {...props} available={false} onRequest={request} />);
  expect(screen.getByText(/no longer the selected active local area/)).toBeTruthy();
  expect(screen.getByRole('button', { name: 'Discard draft & reload' }).disabled).toBe(true);
});

it('rejects malformed snapshots and discards late reads after unmount', async () => {
  for (const changes of [{ characters: [null] }, { rows: ['bad'] }, { tiles: Array(513).fill({}) }, { players: -1 }, { revision: true }]) expect(validTerrain({ ...initial, ...changes }, 'local', area.identity)).toBe(false);
  let finish; const dirty = vi.fn();
  const { unmount } = render(<TerrainEditor {...props} onDirtyChange={dirty} onRequest={() => new Promise(resolve => { finish = resolve; })} />);
  unmount(); await act(async () => finish(initial));
  expect(dirty).toHaveBeenLastCalledWith(false);
});

it('opens from the active adventure and confirms navigation away from its draft', async () => {
  const state = { engine: 'expansion-native', local_worlds: [{ key: 'local', name: 'Cave lab', trainer: 'Player' }], local_hosts: ['local'], world_key: 'local', local_host: true, connected: true, trainer: 'Player', games: [], worlds: [], offline_saves: [], setup: [], hosting: { available: false, worlds: [] }, cave_authoring: true, generated_areas: [area] };
  loadState.mockResolvedValue(state); perform.mockImplementation(handler());
  render(<App />);
  fireEvent.click(await screen.findByRole('button', { name: 'Generate caves & areas' }));
  fireEvent.click(screen.getByRole('button', { name: 'Edit terrain' }));
  await paint(); fireEvent.click(screen.getByRole('button', { name: 'Back to areas' }));
  const dialog = await screen.findByRole('dialog');
  expect(dialog.textContent).toContain('Leave terrain editor?');
  fireEvent.click(within(dialog).getByRole('button', { name: 'Keep editing' }));
  expect(screen.getByRole('grid')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Back to areas' }));
  fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Discard draft' }));
  expect(screen.queryByRole('grid')).toBeNull();
  expect(screen.getByRole('button', { name: 'Edit terrain' })).toBeTruthy();
});

it('maps a mouse click to the selected brush and keeps zoom read-only', async () => {
  const request = handler(); render(<TerrainEditor {...props} onRequest={request} />);
  const grid = await screen.findByRole('grid');
  const svg = grid.querySelector('svg');
  svg.getBoundingClientRect = () => ({ left: 10, top: 20, width: 630, height: 630 });
  fireEvent.click(screen.getByRole('button', { name: 'Water' }));
  fireEvent.click(svg, { clientX: 65, clientY: 75 });
  expect(JSON.parse(screen.getByLabelText('Draft overlay JSON').value)).toEqual([{ x: 5, y: 5, terrain: 'water' }]);
  fireEvent.click(screen.getByRole('button', { name: '4×' }));
  expect(svg.style.width).toBe('400%');
  expect(request).toHaveBeenCalledTimes(1);
});
