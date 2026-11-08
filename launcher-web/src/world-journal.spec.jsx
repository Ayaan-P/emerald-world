// @vitest-environment jsdom
import React from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import WorldJournal from './WorldJournal';
import { App } from './main';
import { loadState, perform } from './api';
vi.mock('./api', () => ({ loadState: vi.fn(), perform: vi.fn(), forgetCapability: vi.fn() }));
afterEach(cleanup);
const world = { key: 'local', name: 'Long-lived world', trainer: 'Player' };
const entry = (seq, text = 'NPC keeper dialogue changed: Repaired → Closed') => ({ seq, recorded_at: 1700000000, title: 'Shared world content changed', details: [text] });
const page = (extra = {}) => ({ world_id: 'stable-world', through: 80, before: 40, has_more: false, coverage_start_seq: 0, entries: [entry(50)], places: [{ id: 'native:LittlerootTown', label: 'Littleroot Town', active: false }], current: { objects: [{ id: 'keeper', text: 'Bridge closed.', x: 8, y: 8 }] }, ...extra });
const props = () => ({ world, available: true, ready: true, busy: false, onRequest: vi.fn().mockResolvedValue(page()), onOpen: vi.fn(), onBack: vi.fn() });
it('reads recorded history and current state without sending a world mutation', async () => {
  const p = props(); render(<WorldJournal {...p} />);
  await screen.findByText('NPC keeper dialogue changed: Repaired → Closed');
  expect(screen.getByText(/Bridge closed/)).toBeTruthy();
  expect(screen.getByText(/not proof that a player completed/)).toBeTruthy();
  expect(p.onRequest).toHaveBeenCalledExactlyOnceWith('journal_read', { world: 'local' });
  expect(p.onOpen).not.toHaveBeenCalled();
});
it('pages older records at the original world and sequence boundary', async () => {
  const p = props(); p.onRequest.mockResolvedValueOnce(page({ has_more: true })).mockResolvedValueOnce(page({ entries: [entry(20, 'Earlier NPC appeared')], before: 20 }));
  render(<WorldJournal {...p} />); fireEvent.click(await screen.findByRole('button', { name: 'Read older changes' }));
  await screen.findByText('Earlier NPC appeared');
  expect(screen.getByText('NPC keeper dialogue changed: Repaired → Closed')).toBeTruthy();
  expect(p.onRequest).toHaveBeenLastCalledWith('journal_read', { world: 'local', world_id: 'stable-world', through: 80, before: 40 });
});
it('selects a place with a fresh page rather than keeping another place history', async () => {
  const p = props(); p.onRequest.mockResolvedValueOnce(page()).mockResolvedValueOnce(page({ entries: [entry(60, 'Selected place only')] }));
  render(<WorldJournal {...p} />); await screen.findByText('NPC keeper dialogue changed: Repaired → Closed');
  fireEvent.change(screen.getByLabelText('Journal place'), { target: { value: 'native:LittlerootTown' } });
  await screen.findByText('Selected place only');
  expect(screen.queryByText('NPC keeper dialogue changed: Repaired → Closed')).toBeNull();
  expect(p.onRequest).toHaveBeenLastCalledWith('journal_read', { world: 'local', place_id: 'native:LittlerootTown' });
});
it('never opens a stopped host or launches a game without an explicit action', () => {
  const p = props(); render(<WorldJournal {...p} available={false} />);
  expect(p.onRequest).not.toHaveBeenCalled(); expect(p.onOpen).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Open host' }));
  expect(p.onOpen).toHaveBeenCalledExactlyOnceWith(world);
  expect(screen.getByText(/game will stay closed/)).toBeTruthy();
});
it('drops a late response after changing worlds', async () => {
  let finish;
  const p = props(); p.onRequest.mockReturnValueOnce(new Promise(resolve => { finish = resolve; })).mockResolvedValueOnce(page({ entries: [entry(9, 'Other world')] }));
  const view = render(<WorldJournal {...p} />);
  view.rerender(<WorldJournal {...p} world={{ ...world, key: 'other' }} />);
  await screen.findByText('Other world'); finish(page({ entries: [entry(10, 'Stale world')] }));
  await waitFor(() => expect(screen.queryByText('Stale world')).toBeNull());
});
it('shows read errors and retries only when requested', async () => {
  const p = props(); p.onRequest.mockRejectedValueOnce(new Error('Host stopped')).mockResolvedValueOnce(page());
  render(<WorldJournal {...p} />); await screen.findByRole('alert');
  expect(p.onRequest).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole('button', { name: 'Refresh journal' }));
  await screen.findByText('NPC keeper dialogue changed: Repaired → Closed');
  expect(p.onRequest).toHaveBeenCalledTimes(2);
});
it('renders recorded text as text and rejects a mismatched pagination response', async () => {
  const p = props(); const text = '<img src=x onerror=alert(1)>';
  p.onRequest.mockResolvedValueOnce(page({ entries: [entry(50, text)], has_more: true })).mockResolvedValueOnce(page({ world_id: 'another-world', entries: [entry(20, 'Wrong world')] }));
  const view = render(<WorldJournal {...p} />); await screen.findByText(text);
  expect(view.container.querySelector('img')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: 'Read older changes' }));
  await screen.findByRole('alert'); expect(screen.queryByText('Wrong world')).toBeNull();
});

it('opens the selected local journal through the actual launcher without launching a game', async () => {
  const state = { engine: 'expansion-native', local_worlds: [world], local_hosts: ['local'], worlds: [], offline_saves: [], presence: null, hosting: { available: false, worlds: [] }, games: [], setup: [], status: 'Ready' };
  loadState.mockResolvedValue(state); perform.mockResolvedValue(page());
  render(<App />);
  fireEvent.click(await screen.findByRole('button', { name: 'Local worlds' }));
  fireEvent.click(screen.getByRole('button', { name: 'World journal' }));
  await screen.findByText('NPC keeper dialogue changed: Repaired → Closed');
  expect(perform).toHaveBeenCalledExactlyOnceWith('journal_read', { world: 'local' });
  expect(screen.getByRole('heading', { name: 'World journal' })).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Back to local worlds' }));
  await screen.findByRole('heading', { name: 'Local worlds', level: 1 });
});
