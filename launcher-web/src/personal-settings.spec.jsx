// @vitest-environment jsdom
import React from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import PersonalSettings from './PersonalSettings';
import { App } from './main';
import { loadState, perform } from './api';
vi.mock('./api', () => ({ loadState: vi.fn(), perform: vi.fn(), forgetCapability: vi.fn() }));

const defaults = { scale: 3, fullscreen: 'auto', a: 'z', b: 'x', select: 'backspace', start: 'return', up: 'up', down: 'down', left: 'left', right: 'right', l: 'a', r: 's' };
const profiles = [{ id: 'online/world/Player', name: 'Cave lab', trainer: 'Player', offline: false }, { id: 'offline/world/Player', name: 'Solo copy', trainer: 'Player', offline: true }];
const info = { available: true, defaults, keys: [...new Set([...Object.values(defaults).filter(item => typeof item === 'string'), 'j', 'k', 'space'])], profiles };
const saved = (values = defaults, revision = 'revision1', custom = []) => ({ values, revision, custom, exists: false });
function props() {
  return { ready: true, busy: false, onDirtyChange: vi.fn(), onRequest: vi.fn(async action => action === 'personal_settings_info' ? info : saved()) };
}
afterEach(() => { cleanup(); vi.clearAllMocks(); });
const scale = value => fireEvent.change(screen.getByLabelText('Window scale'), { target: { value: String(value) } });

it('loads actual per-profile settings without writing a file or applying defaults', async () => {
  const p = props(); render(<PersonalSettings {...p} />);
  expect((await screen.findByLabelText('Window scale')).value).toBe('3');
  expect(screen.getByLabelText('A / Confirm').value).toBe('z');
  expect(screen.getByRole('button', { name: 'Save settings' }).disabled).toBe(true);
  expect(p.onRequest.mock.calls.map(call => call[0])).toEqual(['personal_settings_info', 'personal_settings_read']);
});
it('sends only explicit changes for the selected trainer and native file revision', async () => {
  const p = props(); p.onRequest.mockImplementation(async action => action === 'personal_settings_info' ? info : action === 'personal_settings_save' ? saved({ ...defaults, scale: 4 }, 'revision2') : saved());
  render(<PersonalSettings {...p} />);
  await screen.findByLabelText('Window scale'); scale(4);
  fireEvent.click(screen.getByRole('button', { name: 'Save settings' }));
  await screen.findByText('Settings saved for Player. They apply next launch.');
  expect(p.onRequest).toHaveBeenLastCalledWith('personal_settings_save', { profile: profiles[0].id, changes: { scale: 4 }, expected_revision: 'revision1' });
  expect(screen.getByRole('button', { name: 'Save settings' }).disabled).toBe(true);
});
it('keeps a custom binding unchanged when editing display settings', async () => {
  const p = props(); p.onRequest.mockImplementation(async action => action === 'personal_settings_info' ? info : saved({ ...defaults, a: null }, 'revision1', ['a']));
  render(<PersonalSettings {...p} />);
  await screen.findByLabelText('Window scale'); scale(4);
  expect(screen.getByLabelText('A / Confirm').value).toBe('');
  fireEvent.click(screen.getByRole('button', { name: 'Save settings' }));
  await waitFor(() => expect(p.onRequest).toHaveBeenLastCalledWith('personal_settings_save', { profile: profiles[0].id, changes: { scale: 4 }, expected_revision: 'revision1' }));
});
it('switches solo and world profiles only after an explicit draft discard', async () => {
  const p = props(); render(<PersonalSettings {...p} />);
  await screen.findByLabelText('Window scale'); scale(5);
  fireEvent.change(screen.getByLabelText('Trainer profile'), { target: { value: profiles[1].id } });
  expect(screen.getByLabelText('Trainer profile').value).toBe(profiles[0].id);
  fireEvent.click(screen.getByRole('button', { name: 'Keep editing' }));
  expect(screen.getByLabelText('Window scale').value).toBe('5');
  fireEvent.change(screen.getByLabelText('Trainer profile'), { target: { value: profiles[1].id } });
  fireEvent.click(screen.getByRole('button', { name: 'Discard draft' }));
  await waitFor(() => expect(p.onRequest).toHaveBeenLastCalledWith('personal_settings_read', { profile: profiles[1].id }));
  expect(screen.getByLabelText('Trainer profile').value).toBe(profiles[1].id);
  expect(p.onRequest.mock.calls.filter(call => call[0] === 'personal_settings_save')).toHaveLength(0);
});
it('does not retry an uncertain save until explicitly reloaded', async () => {
  const p = props(); let finish;
  p.onRequest.mockImplementation(async action => action === 'personal_settings_info' ? info : action === 'personal_settings_save' ? new Promise(resolve => { finish = resolve; }) : saved());
  render(<PersonalSettings {...p} />);
  await screen.findByLabelText('Window scale'); scale(4);
  fireEvent.click(screen.getByRole('button', { name: 'Save settings' }));
  fireEvent.click(screen.getByRole('button', { name: 'Save settings' }));
  finish(false);
  await screen.findByText(/last save was not confirmed/);
  expect(screen.getByRole('button', { name: 'Save settings' }).disabled).toBe(true);
  expect(p.onRequest.mock.calls.filter(call => call[0] === 'personal_settings_save')).toHaveLength(1);
  fireEvent.click(screen.getByRole('button', { name: 'Discard draft & reload' }));
  await waitFor(() => expect(screen.queryByText(/last save was not confirmed/)).toBeNull());
  expect(screen.getByLabelText('Window scale').value).toBe('3');
});
it('reports missing support, absent profiles and failed reads without fake controls', async () => {
  const p = props(); p.onRequest.mockResolvedValue({ available: false, profiles: [] });
  const view = render(<PersonalSettings {...p} />);
  await screen.findByText(/Editing is available for Expansion profiles/);
  expect(screen.queryByLabelText('Window scale')).toBeNull();
  view.unmount();
  p.onRequest.mockResolvedValue({ ...info, profiles: [] });
  const empty = render(<PersonalSettings {...p} />);
  await screen.findByText('Start an adventure to create a trainer profile.');
  empty.unmount();
  p.onRequest.mockResolvedValue(false);
  render(<PersonalSettings {...p} />);
  await screen.findByText(/Settings could not be loaded/);
  expect(screen.queryByLabelText('Window scale')).toBeNull();
});
it('warns about shared keys and applies defaults to the draft only', async () => {
  const p = props(); render(<PersonalSettings {...p} />);
  await screen.findByLabelText('A / Confirm');
  fireEvent.change(screen.getByLabelText('A / Confirm'), { target: { value: 'x' } });
  expect(screen.getByText(/Some buttons share a key/)).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Use defaults' }));
  expect(screen.getByLabelText('A / Confirm').value).toBe('z');
  expect(screen.getByRole('button', { name: 'Save settings' }).disabled).toBe(true);
  expect(p.onRequest.mock.calls.filter(call => call[0] === 'personal_settings_save')).toHaveLength(0);
});
it('guards leaving settings in the launcher and does not confuse settings responses with session snapshots', async () => {
  const base = { engine: 'expansion-native', local_worlds: [], local_hosts: [], worlds: [], offline_saves: [], hosting: { available: false, worlds: [] }, games: [], setup: [], status: 'Ready', connected: false };
  loadState.mockResolvedValue(base);
  perform.mockImplementation(async action => action === 'personal_settings_info' ? info : saved());
  render(<App />);
  fireEvent.click(await screen.findByRole('button', { name: 'Settings' }));
  await screen.findByLabelText('Window scale'); scale(4);
  fireEvent.click(screen.getByRole('button', { name: 'Play' }));
  expect(screen.getByRole('heading', { name: 'Leave settings?' })).toBeTruthy();
  fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Keep editing' }));
  expect(screen.getByLabelText('Window scale').value).toBe('4');
  fireEvent.click(screen.getByRole('button', { name: 'Play' }));
  fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Discard draft' }));
  expect(screen.getByRole('heading', { name: 'Local' })).toBeTruthy();
});
