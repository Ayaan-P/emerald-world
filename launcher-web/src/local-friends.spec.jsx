// @vitest-environment jsdom
import React from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import LocalFriends from './LocalFriends';
import { App } from './main';
import { loadState, perform } from './api';
vi.mock('./api', () => ({ loadState: vi.fn(), perform: vi.fn(), forgetCapability: vi.fn() }));

const world = { key: 'e-localworld12', name: 'Cave lab', trainer: 'Owner' };
const listener = { running: true, selected: true, configured: true, listening: true, endpoint: { host: '192.168.1.20', port: 8765 }, pin: 'a'.repeat(64) };
const state = { engine: 'expansion-native', local_worlds: [world], local_hosts: [world.key], local_sharing: { [world.key]: listener }, worlds: [], offline_saves: [], hosting: { available: false, worlds: [] }, games: [], setup: [], connected: true, local_host: true, world_key: world.key, trainer: 'Owner', status: 'Ready' };
function props(sharing = listener) {
  return { state: { ...state, local_sharing: { [world.key]: sharing } }, worldKey: world.key, ready: true, busy: false, onBack: vi.fn(), onOpen: vi.fn(), onAction: vi.fn(async () => true) };
}
const change = (label, value) => fireEvent.change(screen.getByLabelText(label), { target: { value } });
const review = () => within(screen.getByRole('heading', { name: /^(Enable local sharing|Stop local sharing|Create invitation for)/ }).parentElement);
const invite = () => { change('Friend’s trainer profile', 'Friend'); fireEvent.click(screen.getByRole('button', { name: 'Review invitation' })); };
afterEach(() => { cleanup(); vi.clearAllMocks(); vi.unstubAllGlobals(); });

it('defaults to loopback and requires a review before binding any listener', async () => {
  const p = props({ ...listener, configured: false, listening: false, endpoint: undefined, pin: undefined });
  render(<LocalFriends {...p} />);
  expect(screen.getByLabelText('Listen address').value).toBe('127.0.0.1');
  expect(p.onAction).not.toHaveBeenCalled();
  change('Listen address', '192.168.1.20'); change('Listen port', '9876');
  fireEvent.click(screen.getByRole('button', { name: 'Review sharing' }));
  expect(p.onAction).not.toHaveBeenCalled();
  expect(screen.getByLabelText('Listen address').disabled).toBe(true);
  fireEvent.click(review().getByRole('button', { name: 'Cancel' }));
  expect(p.onAction).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Review sharing' }));
  fireEvent.click(review().getByRole('button', { name: 'Enable sharing' }));
  await waitFor(() => expect(p.onAction).toHaveBeenCalledExactlyOnceWith('local_share_start', { world: world.key, listen_host: '192.168.1.20', port: 9876, confirmed: true }));
});

it('discloses wildcard exposure and rejects invalid ports before review', () => {
  render(<LocalFriends {...props({ ...listener, configured: false, listening: false })} />);
  change('Listen address', '0.0.0.0'); change('Listen port', '65536');
  expect(screen.getByRole('button', { name: 'Review sharing' }).disabled).toBe(true);
  change('Listen port', '8765');
  fireEvent.click(screen.getByRole('button', { name: 'Review sharing' }));
  expect(review().getByText(/All network interfaces/)).toBeTruthy();
});

it('opens a detached host deliberately without starting sharing or the game', () => {
  const p = props({ ...listener, selected: false }); render(<LocalFriends {...p} />);
  expect(screen.getByText('TLS listener active')).toBeTruthy();
  expect(screen.queryByLabelText('Friend’s trainer profile')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: 'Open host' }));
  expect(p.onOpen).toHaveBeenCalledExactlyOnceWith(world);
  expect(p.onAction).not.toHaveBeenCalled();
});

it('fails closed on an old bridge without sharing state', () => {
  render(<LocalFriends {...props(undefined)} state={{ ...state, local_sharing: undefined }} />);
  expect(screen.getByText('Sharing status unavailable')).toBeTruthy();
  expect(screen.queryByRole('button', { name: 'Review sharing' })).toBeNull();
});

it('uses an explicit new trainer and freezes the reviewed endpoint and server pin', async () => {
  const p = props(); render(<LocalFriends {...p} />);
  change('Friend’s trainer profile', 'Owner');
  expect(screen.getByRole('button', { name: 'Review invitation' }).disabled).toBe(true);
  change('Address your friend will use', 'world.example'); change('Invitation port', '9876'); invite();
  expect(review().getByText(listener.pin)).toBeTruthy();
  expect(screen.getByLabelText('Friend’s trainer profile').disabled).toBe(true);
  expect(p.onAction).not.toHaveBeenCalled();
  fireEvent.click(review().getByRole('button', { name: 'Create invitation' }));
  await waitFor(() => expect(p.onAction).toHaveBeenCalledExactlyOnceWith('local_invite', {
    world: world.key, trainer: 'Friend', host: 'world.example', port: 9876, existing: false, confirmed: true,
    reviewed_pin: listener.pin, reviewed_listener: listener.endpoint,
  }));
});

it('requires an explicit existing-trainer choice and explains that old credentials are not revoked', async () => {
  const p = props(); render(<LocalFriends {...p} />);
  fireEvent.click(screen.getByRole('button', { name: 'Existing trainer' }));
  expect(screen.getByText(/does not rotate or revoke/)).toBeTruthy(); invite();
  expect(review().getByText(/Grants access to this existing trainer identity/)).toBeTruthy();
  fireEvent.click(review().getByRole('button', { name: 'Create invitation' }));
  await waitFor(() => expect(p.onAction.mock.calls[0][1].existing).toBe(true));
});

it('blocks a stale listener review instead of sending a changed destination silently', () => {
  const p = props(); const view = render(<LocalFriends {...p} />); invite();
  view.rerender(<LocalFriends {...props({ ...listener, pin: 'b'.repeat(64) })} onAction={p.onAction} />);
  expect(review().getByRole('button', { name: 'Create invitation' }).disabled).toBe(true);
  expect(screen.getByRole('alert').textContent).toMatch(/Sharing changed/);
  fireEvent.click(review().getByRole('button', { name: 'Create invitation' }));
  expect(p.onAction).not.toHaveBeenCalled();
});

it('does not repeat an uncertain invitation and requires a successful explicit refresh', async () => {
  const p = props(); let finish;
  p.onAction.mockImplementation(action => action === 'local_invite' ? new Promise(resolve => { finish = resolve; }) : Promise.resolve(false));
  render(<LocalFriends {...p} />); invite();
  fireEvent.click(review().getByRole('button', { name: 'Create invitation' }));
  fireEvent.click(review().getByRole('button', { name: 'Create invitation' }));
  await act(async () => { finish(false); });
  expect(review().getByRole('button', { name: 'Create invitation' }).disabled).toBe(true);
  expect(p.onAction).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole('button', { name: 'Refresh sharing' }));
  await waitFor(() => expect(p.onAction).toHaveBeenCalledTimes(2));
  expect(screen.getByRole('alert').textContent).toMatch(/not confirmed/);
  p.onAction.mockResolvedValue(true);
  fireEvent.click(screen.getByRole('button', { name: 'Refresh sharing' }));
  await waitFor(() => expect(screen.queryByRole('alert')).toBeNull());
  expect(screen.getByLabelText('Friend’s trainer profile').value).toBe('Friend');
  expect(p.onAction.mock.calls.filter(call => call[0] === 'local_invite')).toHaveLength(1);
});

it('confirms stopping only sharing and leaves the local host and game alone', async () => {
  const p = props(); render(<LocalFriends {...p} />);
  fireEvent.click(screen.getByRole('button', { name: 'Stop sharing' }));
  expect(review().getByText(/Your local host and game stay running/)).toBeTruthy();
  fireEvent.click(review().getByRole('button', { name: 'Stop sharing' }));
  await waitFor(() => expect(p.onAction).toHaveBeenCalledExactlyOnceWith('local_share_stop', { world: world.key, confirmed: true }));
});

it('opens local invitations from the launcher and downloads the actual fixed-trainer format', async () => {
  const originalCreate = URL.createObjectURL, originalRevoke = URL.revokeObjectURL;
  URL.createObjectURL = vi.fn(() => 'blob:fixture'); URL.revokeObjectURL = vi.fn();
  try {
    loadState.mockResolvedValue(state);
    perform.mockResolvedValue({ ...state, download: JSON.stringify({ trainer: 'Friend' }), download_kind: 'local_friend' });
    render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: 'Local worlds' }));
    fireEvent.click(screen.getByRole('button', { name: 'Invite friends' })); invite();
    fireEvent.click(review().getByRole('button', { name: 'Create invitation' }));
    const dialog = await screen.findByRole('dialog');
    expect(dialog.textContent).toContain('named trainer in this local world');
    expect(dialog.textContent).not.toContain('binds to the trainer who redeems');
    expect(within(dialog).getByRole('link', { name: 'Download invitation' }).getAttribute('download')).toBe('emerald-world-invitation.json');
    expect(perform.mock.calls.map(call => call[0])).toEqual(['local_invite']);
    fireEvent.click(within(dialog).getByRole('button', { name: 'Done' }));
    expect(screen.getByRole('heading', { name: 'Invite friends' })).toBeTruthy();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:fixture');
  } finally { cleanup(); URL.createObjectURL = originalCreate; URL.revokeObjectURL = originalRevoke; }
});

it('keeps Open host on the friends page without launching the game', async () => {
  loadState.mockResolvedValue({ ...state, connected: false, world_key: null, local_sharing: { [world.key]: { ...listener, selected: false } } });
  perform.mockImplementation(async () => { loadState.mockResolvedValue(state); return state; });
  render(<App />);
  fireEvent.click(await screen.findByRole('button', { name: 'Local worlds' }));
  fireEvent.click(screen.getByRole('button', { name: 'Invite friends' }));
  fireEvent.click(screen.getByRole('button', { name: 'Open host' }));
  await screen.findByLabelText('Friend’s trainer profile');
  expect(screen.getByRole('heading', { name: 'Invite friends' })).toBeTruthy();
  expect(perform.mock.calls.map(call => call[0])).toEqual(['local_resume']);
});
