// @vitest-environment jsdom
import React from 'react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { App } from './main';
import { loadState, perform } from './api';
vi.mock('./api', () => ({ loadState: vi.fn(), perform: vi.fn(), forgetCapability: vi.fn() }));
const base = { engine: 'expansion-native', local_worlds: [], local_hosts: [], worlds: [], offline_saves: [], presence: null, hosting: { available: true, enrolled: false, loaded: false, worlds: [], pending: null }, connected: false, trainer: null, games: [], setup: [], status: 'Ready' };
beforeEach(() => { loadState.mockResolvedValue(base); perform.mockResolvedValue(base); });
afterEach(() => { cleanup(); vi.clearAllMocks(); });
async function localDialog() {
  fireEvent.click(await screen.findByRole('button', { name: 'Create local world' }));
  const dialog = screen.getByRole('dialog');
  fireEvent.change(within(dialog).getByLabelText('World name'), { target: { value: 'Cave lab' } });
  return dialog;
}
it('selects a hosted generation target while keeping a solo game untouched', async () => {
  const world = { id: 'owned', name: 'Cloud grove', trainer: 'Owner' };
  const solo = { ...base, world_key: 'solo', games: ['offline/Player'], trainer: 'Player', hosting: { ...base.hosting, enrolled: true, loaded: true, worlds: [world] } };
  loadState.mockResolvedValue(solo);
  perform.mockImplementation(async () => {
    const selected = { ...solo, area_world_key: 'hosted-owned', area_authoring: true, cave_authoring: true, cave_persistent: true, hosted_area_world: world };
    loadState.mockResolvedValue(selected);
    return selected;
  });
  render(<App />);
  fireEvent.click(await screen.findByRole('button', { name: 'Explore' }));
  fireEvent.click(screen.getByRole('button', { name: 'Select Cloud grove for generation' }));
  await waitFor(() => expect(screen.getByLabelText('Area theme').disabled).toBe(false));
  expect(perform.mock.calls).toEqual([['host_select_area', { world: 'owned' }]]);
  expect(screen.queryByRole('dialog')).toBeNull();
  expect(screen.getByRole('heading', { name: 'Explore' })).toBeTruthy();
});
it('separates Local and Hosted and keeps release notes and generation forms off Play', async () => {
  render(<App />);
  await screen.findByText('Expansion · Native PC');
  expect(screen.getByRole('heading', { name: 'Local' })).toBeTruthy();
  expect(screen.getByRole('heading', { name: 'Hosted' })).toBeTruthy();
  expect(screen.getByRole('button', { name: 'Generate caves & areas' })).toBeTruthy();
  expect(screen.queryByText(/RC8|Your adventure|Your world is open/i)).toBeNull();
  expect(screen.queryByLabelText('Area theme')).toBeNull();
});
it('creates and launches a local world without requiring hosted-owner access', async () => {
  render(<App />);
  const dialog = await localDialog();
  fireEvent.click(within(dialog).getByRole('button', { name: 'Create and play' }));
  await waitFor(() => expect(perform.mock.calls.map(call => call[0])).toEqual(['local_create', 'launch']));
  expect(perform).toHaveBeenCalledWith('local_create', { name: 'Cave lab', trainer: 'Player' });
});
it('lets a local creator set up areas first without launching or calling a model', async () => {
  const connected = { ...base, connected: true, local_host: true, world_key: 'local', trainer: 'Player', cave_authoring: true, local_worlds: [{ key: 'local', name: 'Cave lab', trainer: 'Player' }] };
  perform.mockImplementation(async () => { loadState.mockResolvedValue(connected); return connected; });
  render(<App />);
  const dialog = await localDialog();
  fireEvent.click(within(dialog).getByRole('button', { name: 'Set up areas first' }));
  expect(await screen.findByLabelText('Area theme')).toBeTruthy();
  expect(perform.mock.calls.map(call => call[0])).toEqual(['local_create']);
  expect(screen.getByLabelText('Area type').value).toBe('cave');
});
it('opens an existing local world for editing without switching back to Play', async () => {
  const world = { key: 'local', name: 'Cave lab', trainer: 'Player', has_save: true };
  const connected = { ...base, local_worlds: [world], connected: true, local_host: true, world_key: 'local', trainer: 'Player', cave_authoring: true };
  loadState.mockResolvedValue({ ...base, local_worlds: [world] });
  perform.mockImplementation(async () => { loadState.mockResolvedValue(connected); return connected; });
  render(<App />);
  fireEvent.click(await screen.findByRole('button', { name: 'Generate caves & areas' }));
  fireEvent.click(screen.getByRole('button', { name: 'Open local world' }));
  expect(await screen.findByLabelText('Area theme')).toBeTruthy();
  expect(perform.mock.calls.map(call => call[0])).toEqual(['local_resume']);
});
it('retains hosted invitation joining when owner management is unavailable', async () => {
  loadState.mockResolvedValue({ ...base, hosting: { ...base.hosting, available: false } });
  render(<App />);
  fireEvent.click(await screen.findByRole('button', { name: 'Hosted worlds' }));
  expect(screen.getByRole('button', { name: 'Add host access' }).disabled).toBe(true);
  expect(screen.getAllByRole('button', { name: 'Join a world' }).every(button => !button.disabled)).toBe(true);
});
it('shows the configured hosting endpoint without claiming server health', async () => {
  loadState.mockResolvedValue({ ...base, hosting: { ...base.hosting, enrolled: true, endpoint: { host: 'host.example', port: 8766 } } });
  render(<App />);
  fireEvent.click(await screen.findByRole('button', { name: 'Hosted worlds' }));
  expect(screen.getByText('host.example:8766')).toBeTruthy();
  expect(screen.queryByText('Server online')).toBeNull();
  expect(perform).not.toHaveBeenCalled();
});
it('keeps a detached local host visible and confirms stopping that host only', async () => {
  loadState.mockResolvedValue({ ...base, local_hosts: ['local'], local_worlds: [{ key: 'local', name: 'Cave lab', trainer: 'Player' }] });
  render(<App />);
  fireEvent.click(await screen.findByRole('button', { name: '1 local host running' }));
  fireEvent.click(screen.getByRole('button', { name: 'Stop host' }));
  const dialog = screen.getByRole('dialog');
  expect(dialog.textContent).toMatch(/disconnects its players/);
  expect(perform).not.toHaveBeenCalled();
  fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }));
  expect(perform).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Stop host' }));
  fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Stop host' }));
  await waitFor(() => expect(perform).toHaveBeenCalledWith('local_stop', { world: 'local' }));
});
it('explains local disconnect without claiming the host stops', async () => {
  loadState.mockResolvedValue({ ...base, connected: true, local_host: true, trainer: 'Player', games: ['Player'] });
  render(<App />);
  fireEvent.click(await screen.findByRole('button', { name: 'Disconnect' }));
  expect(screen.getByRole('dialog').textContent).toContain('local host keeps running');
  expect(perform).not.toHaveBeenCalled();
});
it('reports stale telemetry as waiting rather than a connected game', async () => {
  loadState.mockResolvedValue({ ...base, connected: true, trainer: 'Player', games: ['Player'], presence: { state: 'waiting', nearby: [] } });
  render(<App />);
  const session = await screen.findByRole('region', { name: 'Current session' });
  expect(session.textContent).toContain('Waiting for game connection');
  expect(within(session).queryByText('Game connected')).toBeNull();
});
it('validates local names and prevents repeated create clicks', async () => {
  let finish;
  perform.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  render(<App />);
  const dialog = await localDialog();
  const create = within(dialog).getByRole('button', { name: 'Create and play' });
  const trainer = within(dialog).getByLabelText('Trainer profile');
  fireEvent.change(trainer, { target: { value: 'bad name' } });
  expect(create.disabled).toBe(true);
  fireEvent.change(trainer, { target: { value: 'May' } });
  fireEvent.click(create); fireEvent.click(create);
  expect(perform).toHaveBeenCalledTimes(1);
  await act(async () => { finish(base); });
});

it('stops polling after a successful quit and does not label it an error', async () => {
  render(<App />);
  fireEvent.click(await screen.findByRole('button', { name: 'Settings' }));
  fireEvent.click(screen.getByRole('button', { name: 'Quit launcher' }));
  fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Quit launcher' }));
  expect(await screen.findByRole('status')).toHaveProperty('textContent', 'Launcher closed. You can close this tab.');
  expect(screen.queryByRole('alert')).toBeNull();
});

it('hides old presence after the launcher connection fails', async () => {
  vi.useFakeTimers();
  loadState.mockResolvedValueOnce({ ...base, connected: true, trainer: 'Player', games: ['Player'], presence: { state: 'connected', nearby: [{ trainer: 'May', ready: true, rendered: true }] } }).mockRejectedValue(new Error('Launcher offline'));
  try {
    render(<App />);
    await act(async () => { await Promise.resolve(); });
    expect(screen.getByText('May')).toBeTruthy();
    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    const session = screen.getByRole('region', { name: 'Current session' });
    expect(session.textContent).toContain('Game status is unknown');
    expect(session.textContent).not.toContain('Game connected');
    expect(screen.queryByText('May')).toBeNull();
  } finally { vi.useRealTimers(); }
});
