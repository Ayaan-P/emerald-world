// @vitest-environment jsdom
import React from 'react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import AreaLibrary, { floorPath, validPreview } from './AreaLibrary';
import ExpeditionPanel from './ExpeditionPanel';
import { App } from './main';
import { loadState, perform } from './api';
vi.mock('./api', () => ({ loadState: vi.fn(), perform: vi.fn(), forgetCapability: vi.fn() }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });
const cave = { identity: 'a'.repeat(64), label: 'Quiet cave', kind: 'cave', active: false };
const outdoor = { identity: 'b'.repeat(64), label: 'Wide islands', kind: 'xl_wilds', active: true };
const adventure = { identity: 'c'.repeat(64), label: 'Forest mystery', kind: 'event_wilds', active: false };
const state = { engine: 'expansion-native', local_worlds: [{ key: 'local', name: 'Cave lab', trainer: 'Player' }], local_hosts: ['local'], world_key: 'local', local_host: true, connected: true, trainer: 'Player', games: [], worlds: [], offline_saves: [], setup: [], hosting: { available: false, worlds: [] }, cave_authoring: true, generated_areas: [cave, outdoor, adventure] };
function data(area = cave, side = 31) {
  return { world: 'local', identity: area.identity, label: area.label, kind: area.kind, side, layout: 'saved_base',
    entrance: [1, 1], exit: [side - 2, side - 2], characters: [], wildlife: [], wildlife_cohort: null,
    rows: ['#'.repeat(side), ...Array(side - 2).fill('#' + '.'.repeat(side - 2) + '#'), '#'.repeat(side)] };
}
const base = { world: 'local', areas: [cave, outdoor, adventure], disabled: false, occupied: false, pending: null, onReview: vi.fn() };
beforeEach(() => { loadState.mockResolvedValue(state); perform.mockResolvedValue(data()); });

it('searches names and filters distinct area types without making requests', () => {
  const inspect = vi.fn();
  render(<AreaLibrary {...base} onInspect={inspect} />);
  fireEvent.click(screen.getByRole('button', { name: 'Outdoors' }));
  expect(screen.queryByText(cave.label)).toBeNull();
  expect(screen.getByText(outdoor.label)).toBeTruthy();
  expect(screen.queryByText(adventure.label)).toBeNull();
  fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'QUIET' } });
  expect(screen.getByRole('status').textContent).toContain('No matching areas');
  fireEvent.click(screen.getByRole('button', { name: 'Clear filters' }));
  fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'quiet' } });
  expect(screen.getByText(cave.label)).toBeTruthy();
  expect(screen.queryByText(outdoor.label)).toBeNull();
  expect(inspect).not.toHaveBeenCalled();
});

it('previews saved geometry, zooms and reviews activation without applying it', async () => {
  const inspect = vi.fn().mockResolvedValue(data());
  const review = vi.fn();
  render(<AreaLibrary {...base} onInspect={inspect} onReview={review} />);
  fireEvent.click(screen.getByRole('button', { name: `Preview map: ${cave.label}` }));
  const map = await screen.findByRole('img', { name: `Saved layout of ${cave.label}` });
  expect(inspect).toHaveBeenCalledWith({ world: 'local', identity: cave.identity });
  expect(screen.getByText(/Live terrain and player positions are not shown/)).toBeTruthy();
  expect(map.querySelectorAll('path')).toHaveLength(1);
  expect(map.getAttribute('viewBox')).toBe('0 0 31 31');
  fireEvent.click(screen.getByRole('button', { name: '4×' }));
  expect(map.style.width).toBe('400%');
  const viewport = screen.getByRole('region', { name: 'Scrollable saved map' });
  viewport.scrollLeft = 10; viewport.scrollTop = 20;
  fireEvent.click(screen.getByRole('button', { name: 'Fit' }));
  expect(map.style.width).toBe('100%');
  expect(viewport.scrollLeft + viewport.scrollTop).toBe(0);
  expect(review).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Review activation' }));
  expect(review).toHaveBeenCalledWith({ type: 'activate', world: 'local', identity: cave.identity, label: cave.label, adventure: false });
});

it('ignores late results after Escape and restores focus without restarting', async () => {
  let finish;
  const inspect = vi.fn(() => new Promise(resolve => { finish = resolve; }));
  render(<AreaLibrary {...base} onInspect={inspect} />);
  const opener = screen.getByRole('button', { name: `Preview map: ${cave.label}` });
  opener.focus(); fireEvent.click(opener); fireEvent.click(opener);
  expect(inspect).toHaveBeenCalledTimes(1);
  fireEvent.keyDown(screen.getByRole('region', { name: 'Map preview' }), { key: 'Escape' });
  expect(document.activeElement).toBe(opener);
  await act(async () => finish(data()));
  expect(screen.queryByRole('region', { name: 'Map preview' })).toBeNull();
});

it('discards preview and search on a world switch, including late responses', async () => {
  let finish;
  const inspect = vi.fn(() => new Promise(resolve => { finish = resolve; }));
  const { rerender } = render(<ExpeditionPanel state={state} ready onInspect={inspect} />);
  fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'Quiet' } });
  fireEvent.click(screen.getByRole('button', { name: `Preview map: ${cave.label}` }));
  rerender(<ExpeditionPanel state={{ ...state, world_key: 'other' }} ready onInspect={inspect} />);
  await act(async () => finish(data()));
  expect(screen.queryByRole('region', { name: 'Map preview' })).toBeNull();
  expect(screen.getByRole('searchbox').value).toBe('');
});

it('retries a failed read only by explicit request and rejects mismatched responses', async () => {
  const inspect = vi.fn().mockRejectedValueOnce(new Error('private internal detail')).mockResolvedValueOnce({ ...data(), world: 'wrong' }).mockResolvedValue(data());
  render(<AreaLibrary {...base} onInspect={inspect} />);
  fireEvent.click(screen.getByRole('button', { name: `Preview map: ${cave.label}` }));
  expect((await screen.findByRole('alert')).textContent).not.toContain('private');
  expect(inspect).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole('button', { name: 'Retry preview' }));
  await waitFor(() => expect(screen.getByRole('alert')).toBeTruthy());
  expect(screen.queryByRole('img')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: 'Retry preview' }));
  await screen.findByRole('img');
  expect(inspect).toHaveBeenCalledTimes(3);
});

it('keeps preview available while occupied, but prevents replacing the area', async () => {
  const inspect = vi.fn().mockResolvedValue(data());
  render(<AreaLibrary {...base} occupied onInspect={inspect} />);
  fireEvent.click(screen.getByRole('button', { name: `Preview map: ${cave.label}` }));
  await screen.findByRole('img');
  expect(screen.getByRole('button', { name: 'Review activation' }).disabled).toBe(true);
  expect(screen.getByRole('button', { name: 'Use this area' }).disabled).toBe(true);
});

it('shows exact wildlife levels and character markers without dialogue or chance claims', async () => {
  const value = { ...data(adventure, 63), characters: [{ number: 1, x: 2, y: 1 }], wildlife: [{ species: 10, name: 'Rookidee', levels: [5, 7] }], wildlife_cohort: 'expansion-native' };
  render(<AreaLibrary {...base} onInspect={vi.fn().mockResolvedValue(value)} />);
  fireEvent.click(screen.getByRole('button', { name: `Preview map: ${adventure.label}` }));
  const map = await screen.findByRole('img');
  expect(map.querySelectorAll('.map-character')).toHaveLength(1);
  fireEvent.click(screen.getByText('Wildlife · 1 species'));
  expect(screen.getByText('Rookidee')).toBeTruthy();
  expect(screen.getByText('Lv. 5, 7')).toBeTruthy();
  expect(screen.getByText(/Stored roster · Expansion/)).toBeTruthy();
  expect(screen.queryByText(/chance|probability|percent/)).toBeNull();
});

it('invalidates a preview removed from the latest archive and survives host loss', async () => {
  const { rerender } = render(<ExpeditionPanel state={state} ready onInspect={vi.fn().mockResolvedValue(data())} />);
  fireEvent.click(screen.getByRole('button', { name: `Preview map: ${cave.label}` }));
  await screen.findByRole('img');
  rerender(<ExpeditionPanel state={{ ...state, generated_areas: [outdoor] }} ready />);
  expect(screen.queryByRole('region', { name: 'Map preview' })).toBeNull();
  rerender(<ExpeditionPanel state={{ ...state, local_host: false }} ready />);
  expect(screen.queryByRole('region', { name: 'Area library' })).toBeNull();
});

it('does not change the active area from preview and preserves explicit activation confirmation', async () => {
  const onActivate = vi.fn().mockResolvedValue(true);
  const onAuthor = vi.fn();
  render(<ExpeditionPanel state={state} ready onInspect={vi.fn().mockResolvedValue(data())} onActivate={onActivate} onAuthor={onAuthor} />);
  fireEvent.click(screen.getByRole('button', { name: `Preview map: ${cave.label}` }));
  await screen.findByRole('img');
  fireEvent.click(screen.getByRole('button', { name: 'Review activation' }));
  expect(onActivate).not.toHaveBeenCalled();
  const confirmation = screen.getByRole('region', { name: 'Review area change' });
  expect(confirmation.textContent).toContain('No model call is made');
  fireEvent.click(within(confirmation).getByRole('button', { name: 'Activate saved area' }));
  await waitFor(() => expect(onActivate).toHaveBeenCalledWith({ world: 'local', identity: cave.identity, confirmed: true }));
  expect(onAuthor).not.toHaveBeenCalled();
});

it('bounds the initial library and keeps search across undisplayed areas', () => {
  const areas = Array.from({ length: 50 }, (_, index) => ({ ...cave, identity: String(index), label: `Cave ${index}` }));
  render(<AreaLibrary {...base} areas={areas} onInspect={vi.fn()} />);
  expect(screen.getAllByRole('article')).toHaveLength(24);
  fireEvent.click(screen.getByRole('button', { name: 'Show more areas (26)' }));
  expect(screen.getAllByRole('article')).toHaveLength(48);
  fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'Cave 49' } });
  expect(screen.getAllByRole('article')).toHaveLength(1);
});

it('validates bounded geometry and metadata before rendering', () => {
  expect(validPreview(data(), 'local', cave.identity)).toBe(true);
  for (const changes of [{ rows: ['broken'] }, { side: 500 }, { characters: Array(4).fill({}) }, { entrance: [Infinity, 1] }, { wildlife: [{ name: 'A', levels: [101], species: 1 }] }, { layout: 'live' }, { characters: [null] }, { wildlife: [null] }]) {
    expect(validPreview({ ...data(), ...changes }, 'local', cave.identity)).toBe(false);
  }
  expect(floorPath(['#..#.', '.####'])).toBe('M1 0h2v1h-2zM4 0h1v1h-1zM0 1h1v1h-1z');
  expect(floorPath(data(cave, 127).rows).length).toBeLessThan(4000);
});

it('routes inspect through App without replacing the session snapshot', async () => {
  render(<App />);
  fireEvent.click(await screen.findByRole('button', { name: 'Generate caves & areas' }));
  fireEvent.click(screen.getByRole('button', { name: `Preview map: ${cave.label}` }));
  await screen.findByRole('img');
  expect(perform).toHaveBeenCalledTimes(1);
  expect(perform).toHaveBeenCalledWith('inspect_area', { world: 'local', identity: cave.identity });
  expect(screen.getByRole('button', { name: 'Play now' }).disabled).toBe(false);
  expect(screen.getByText('Cave lab')).toBeTruthy();
});

it('keeps unavailable preview disabled without removing existing activation access', () => {
  render(<AreaLibrary {...base} />);
  expect(screen.getByRole('button', { name: `Preview map: ${cave.label}` }).disabled).toBe(true);
  expect(screen.getByRole('button', { name: 'Use this area' }).disabled).toBe(false);
});

it('shows a later adventure after paging instead of claiming none exists', () => {
  const areas = [...Array.from({ length: 24 }, (_, index) => ({ ...cave, identity: String(index), label: `Cave ${index}` })), adventure];
  render(<AreaLibrary {...base} areas={areas} onInspect={vi.fn()} />);
  expect(screen.queryByText('No published adventures.')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: 'Show more areas (1)' }));
  expect(screen.getByText(adventure.label)).toBeTruthy();
});
