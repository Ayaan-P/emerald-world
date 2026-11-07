// @vitest-environment jsdom
import React from 'react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import WorldOptions from './WorldOptions';
import { App } from './main';
import { loadState, perform } from './api';
vi.mock('./api', () => ({ loadState: vi.fn(), perform: vi.fn(), forgetCapability: vi.fn() }));

const key = 'e-localworld12';
const world = { key, name: 'Cave lab', trainer: 'Player' };
const rule = (enabled = false, seed = 1, revision = 4, players = 0) => ({ status: 'ready', version: 1, revision, players, rules: { wild_shuffle: { enabled, seed } } });
const state = value => ({ engine: 'expansion-native', local_worlds: [world], local_hosts: [key], worlds: [], offline_saves: [], presence: null, hosting: { available: false, enrolled: false, worlds: [] }, games: [], setup: [], status: 'Ready', world_options: { [key]: value } });
function props(value = rule()) {
  return { state: state(value), worldKey: key, ready: true, busy: false,
    onChoose: vi.fn(), onBack: vi.fn(), onOpen: vi.fn(), onSave: vi.fn(),
    onRefresh: vi.fn(), onDirtyChange: vi.fn() };
}
afterEach(() => { cleanup(); vi.clearAllMocks(); });
beforeEach(() => { loadState.mockResolvedValue(state(rule())); perform.mockResolvedValue(state(rule())); });
function enable() { fireEvent.click(screen.getByLabelText('Wild shuffle')); }
function review() { fireEvent.click(screen.getByRole('button', { name: 'Review changes' })); }

it('loads saved values without applying presets, migrating defaults or advertising unwired controls', () => {
  const p = props(rule(true, 12)); render(<WorldOptions {...p} />);
  expect(screen.getByLabelText('Wild shuffle').checked).toBe(true);
  expect(screen.getByLabelText('Shuffle seed').value).toBe('12');
  expect(screen.getByRole('button', { name: 'Expansion playground' }).disabled).toBe(true);
  expect(screen.getByText('Shared gameplay. Display and controls stay personal.')).toBeTruthy();
  expect(screen.queryByRole('checkbox', { name: /Mega|Tera|followers/i })).toBeNull();
  expect(p.onSave).not.toHaveBeenCalled();
  expect(p.onOpen).not.toHaveBeenCalled();
});
it('fails closed with an older or unknown backend and never fabricates active defaults', () => {
  const p = props({ status: 'unsupported' }); const view = render(<WorldOptions {...p} />);
  expect(screen.getByText(/needs the world-rules update/)).toBeTruthy();
  expect(screen.queryByLabelText('Wild shuffle')).toBeNull();
  expect(screen.getByRole('button', { name: 'Use default' }).disabled).toBe(true);
  for (const value of [undefined, { ...rule(), version: 2 }, { ...rule(), rules: null }, { ...rule(), rules: { ...rule().rules, mega: true } }]) {
    view.rerender(<WorldOptions {...p} state={state(value)} />);
    expect(screen.queryByLabelText('Wild shuffle')).toBeNull();
  }
  expect(p.onSave).not.toHaveBeenCalled();
});
it('opens a stopped host only on request and does not launch the game', () => {
  const p = props({ status: 'stopped' }); render(<WorldOptions {...p} />);
  expect(p.onOpen).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Open host' }));
  expect(p.onOpen).toHaveBeenCalledWith(world);
  expect(screen.getByText(/game will stay closed/)).toBeTruthy();
});
it('reviews a default reset with exact changed values before applying a world-scoped revision', async () => {
  const p = props(rule(true, 12));
  p.onSave.mockResolvedValue(state(rule(false, 1, 5)));
  render(<WorldOptions {...p} />);
  fireEvent.click(screen.getByRole('button', { name: 'Use default' }));
  expect(p.onSave).not.toHaveBeenCalled();
  review();
  expect(screen.getByRole('heading', { name: 'Apply to Cave lab?' })).toBe(document.activeElement);
  expect(screen.getByText('On → Off')).toBeTruthy();
  expect(screen.getByText('12 → 1')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Keep editing' }));
  expect(p.onSave).not.toHaveBeenCalled();
  review();
  fireEvent.click(screen.getByRole('button', { name: 'Apply changes' }));
  await screen.findByText('World options saved.');
  expect(p.onSave).toHaveBeenCalledExactlyOnceWith({ world: key, expected_revision: 4, confirmed: true, rules: { wild_shuffle: { enabled: false, seed: 1 } } });
});
it('preserves draft on polls and blocks a conflicting revision until explicit discard and reload', async () => {
  const p = props(); const view = render(<WorldOptions {...p} />);
  enable();
  view.rerender(<WorldOptions {...p} state={state(rule())} />);
  expect(screen.getByLabelText('Wild shuffle').checked).toBe(true);
  expect(screen.getByRole('button', { name: 'Review changes' }).disabled).toBe(false);
  view.rerender(<WorldOptions {...p} state={state(rule(false, 5, 5))} />);
  expect(screen.getByRole('alert').textContent).toContain('changed while you were editing');
  expect(screen.getByLabelText('Wild shuffle').checked).toBe(true);
  expect(screen.getByRole('button', { name: 'Review changes' }).disabled).toBe(true);
  p.onRefresh.mockResolvedValue(state(rule(false, 5, 5)));
  fireEvent.click(screen.getAllByRole('button', { name: 'Discard draft & reload' })[0]);
  await waitFor(() => expect(screen.queryByRole('alert')).toBeNull());
  expect(screen.getByLabelText('Shuffle seed').value).toBe('5');
  expect(p.onSave).not.toHaveBeenCalled();
});
it('blocks applying while players are present and rechecks after review without disconnecting anyone', () => {
  const p = props(); const view = render(<WorldOptions {...p} />);
  enable(); review();
  view.rerender(<WorldOptions {...p} state={state(rule(false, 1, 4, 2))} />);
  expect(screen.getByRole('button', { name: 'Apply changes' }).disabled).toBe(true);
  expect(screen.getByText(/All players must leave/)).toBeTruthy();
  view.rerender(<WorldOptions {...p} state={state(rule())} />);
  expect(screen.getByRole('button', { name: 'Apply changes' }).disabled).toBe(false);
  expect(p.onSave).not.toHaveBeenCalled();
});
it('bounds seeds and never sends partial or invalid values', () => {
  const p = props(); render(<WorldOptions {...p} />);
  for (const value of ['', '0', '21', '1.5']) {
    fireEvent.change(screen.getByLabelText('Shuffle seed'), { target: { value } });
    expect(screen.getByLabelText('Shuffle seed').getAttribute('aria-invalid')).toBe('true');
    expect(screen.getByRole('button', { name: 'Review changes' }).disabled).toBe(true);
  }
  fireEvent.change(screen.getByLabelText('Shuffle seed'), { target: { value: '20' } });
  expect(screen.getByRole('button', { name: 'Review changes' }).disabled).toBe(false);
  expect(p.onSave).not.toHaveBeenCalled();
});
it('does not repeat an uncertain write, even after fresh polling, until manually reloaded', async () => {
  const p = props(); let finish;
  p.onSave.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  const view = render(<WorldOptions {...p} />); enable(); review();
  fireEvent.click(screen.getByRole('button', { name: 'Apply changes' }));
  fireEvent.click(screen.getByRole('button', { name: 'Apply changes' }));
  expect(p.onSave).toHaveBeenCalledTimes(1);
  finish(false);
  await screen.findByText(/last save was not confirmed/);
  view.rerender(<WorldOptions {...p} state={state(rule())} />);
  expect(screen.getByRole('button', { name: 'Review changes' }).disabled).toBe(true);
  p.onRefresh.mockResolvedValue(state(rule(true, 1, 5)));
  fireEvent.click(screen.getAllByRole('button', { name: 'Discard draft & reload' })[0]);
  await waitFor(() => expect(screen.queryByText(/last save was not confirmed/)).toBeNull());
  expect(screen.getByLabelText('Wild shuffle').checked).toBe(true);
  expect(p.onSave).toHaveBeenCalledTimes(1);
});
it('blocks edits and commits when launcher connectivity or compatibility is lost', () => {
  const p = props(); const view = render(<WorldOptions {...p} />); enable(); review();
  view.rerender(<WorldOptions {...p} ready={false} />);
  expect(screen.getByRole('button', { name: 'Apply changes' }).disabled).toBe(true);
  expect(screen.getByLabelText('Wild shuffle').disabled).toBe(true);
  view.rerender(<WorldOptions {...p} state={state({ status: 'error' })} />);
  expect(screen.getByRole('button', { name: 'Apply changes' }).disabled).toBe(true);
});
it('guards leaving a draft and switching worlds through the actual launcher', async () => {
  const other = { key: 'other', name: 'Other world', trainer: 'Other' };
  loadState.mockResolvedValue({ ...state(rule()), local_worlds: [world, other] });
  render(<App />);
  fireEvent.click(await screen.findByRole('button', { name: 'Local worlds' }));
  fireEvent.click(screen.getAllByRole('button', { name: 'World options' })[0]);
  enable();
  fireEvent.click(screen.getByRole('button', { name: 'Hosted worlds' }));
  let dialog = screen.getByRole('dialog');
  expect(within(dialog).getByRole('heading', { name: 'Leave world options?' })).toBeTruthy();
  fireEvent.click(within(dialog).getByRole('button', { name: 'Keep editing' }));
  fireEvent.change(screen.getByLabelText('Local world'), { target: { value: 'other' } });
  dialog = screen.getByRole('dialog');
  fireEvent.click(within(dialog).getByRole('button', { name: 'Discard draft' }));
  expect(screen.getByLabelText('Local world').value).toBe('other');
  expect(perform).not.toHaveBeenCalled();
});
it('applies through the bridge and stays on the selected world-options page', async () => {
  perform.mockImplementation(async (action) => {
    const next = state(action === 'rules_replace' ? rule(true, 1, 5) : rule());
    loadState.mockResolvedValue(next); return next;
  });
  render(<App />);
  fireEvent.click(await screen.findByRole('button', { name: 'Local worlds' }));
  fireEvent.click(screen.getByRole('button', { name: 'World options' }));
  enable(); review(); fireEvent.click(screen.getByRole('button', { name: 'Apply changes' }));
  await screen.findByText('World options saved.');
  expect(screen.getByRole('heading', { name: 'World options' })).toBeTruthy();
  expect(perform).toHaveBeenCalledExactlyOnceWith('rules_replace', { world: key, expected_revision: 4, confirmed: true, rules: { wild_shuffle: { enabled: true, seed: 1 } } });
});
it('opens a stopped world for options without launching or navigating to generated areas', async () => {
  loadState.mockResolvedValue(state({ status: 'stopped' }));
  perform.mockImplementation(async () => { const next = state(rule()); loadState.mockResolvedValue(next); return next; });
  render(<App />);
  fireEvent.click(await screen.findByRole('button', { name: 'Local worlds' }));
  fireEvent.click(screen.getByRole('button', { name: 'World options' }));
  fireEvent.click(screen.getByRole('button', { name: 'Open host' }));
  await screen.findByLabelText('Wild shuffle');
  expect(screen.getByRole('heading', { name: 'World options' })).toBeTruthy();
  expect(perform).toHaveBeenCalledExactlyOnceWith('local_resume', { world: key, trainer: 'Player' });
});
