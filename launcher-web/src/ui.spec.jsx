// @vitest-environment jsdom
import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { App } from './main';
import GameMirror from './GameMirror';
import { loadState, perform } from './api';

vi.mock('./api', () => ({ loadState: vi.fn(), perform: vi.fn(), forgetCapability: vi.fn() }));

const snapshot = () => ({
  worlds: [{ key: 'remote-1234', name: 'Our Hoenn', trainer: 'May' }],
  offline_saves: [], presence: null, hosting: { available: false, enrolled: false, loaded: false, worlds: [], pending: null }, connected: false, trainer: null, games: [], setup: [], status: 'Ready',
});

beforeEach(() => { loadState.mockResolvedValue(snapshot()); perform.mockResolvedValue(snapshot()); });
afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe('player launcher', () => {
  it('mirrors a user-selected window and sends keys only while controlling it', async () => {
    const track = new EventTarget(); track.readyState = 'live'; track.stop = vi.fn();
    const stream = { getTracks: () => [track], getVideoTracks: () => [track] };
    const picker = vi.fn().mockResolvedValue(stream);
    Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getDisplayMedia: picker } });
    const play = vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue();
    perform.mockImplementation(async action => action === 'screen_info' ? { available: true } : { active: true, session: 'preview-session' });
    try {
      render(<GameMirror gameRunning onBack={() => {}} />);
      const choose = await screen.findByRole('button', { name: /choose game display/i });
      await waitFor(() => expect(choose.disabled).toBe(false));
      fireEvent.click(choose);
      const surface = await screen.findByRole('application', { name: /game screen/i });
      await waitFor(() => expect(surface.querySelector('video').srcObject).toBe(stream));
      expect(picker).toHaveBeenCalledOnce();
      expect(perform).toHaveBeenCalledWith('screen_start', {});
      fireEvent.focus(surface); fireEvent.keyDown(surface, { code: 'KeyZ' });
      await waitFor(() => expect(perform).toHaveBeenCalledWith('screen_keys', { session: 'preview-session', keys: ['KeyZ'] }));
      fireEvent.blur(surface);
      await waitFor(() => expect(perform).toHaveBeenCalledWith('screen_keys', { session: 'preview-session', keys: [] }));
      fireEvent.click(screen.getByRole('button', { name: /stop preview/i }));
      await waitFor(() => expect(perform).toHaveBeenCalledWith('screen_stop', { session: 'preview-session' }));
      expect(track.stop).toHaveBeenCalled();
    } finally { play.mockRestore(); delete navigator.mediaDevices; }
  });

  it('serializes a pending old start and scopes its late cleanup away from the new preview', async () => {
    const tracks = [new EventTarget(), new EventTarget()];
    tracks.forEach(track => { track.readyState = 'live'; track.stop = vi.fn(); });
    const streams = tracks.map(track => ({ getTracks: () => [track], getVideoTracks: () => [track] }));
    const picker = vi.fn().mockResolvedValueOnce(streams[0]).mockResolvedValueOnce(streams[1]);
    Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getDisplayMedia: picker } });
    const play = vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue();
    let resolveOld, starts = 0, owner = null;
    perform.mockImplementation((action, payload) => {
      if (action === 'screen_info') return Promise.resolve({ available: true });
      if (action === 'screen_start') {
        starts++;
        if (starts === 1) { owner = 'old'; return new Promise(resolve => { resolveOld = resolve; }); }
        owner = 'new'; return Promise.resolve({ active: true, session: owner });
      }
      if (action === 'screen_stop' && payload.session === owner) owner = null;
      if (action === 'screen_keys' && payload.session !== owner) return Promise.reject(new Error('Wrong owner'));
      return Promise.resolve({ active: action !== 'screen_stop' });
    });
    try {
      const old = render(<GameMirror gameRunning onBack={() => {}} />);
      let choose = await screen.findByRole('button', { name: /choose game display/i });
      await waitFor(() => expect(choose.disabled).toBe(false)); fireEvent.click(choose);
      await waitFor(() => expect(starts).toBe(1));
      old.unmount();
      expect(tracks[0].stop).toHaveBeenCalled();
      render(<GameMirror gameRunning onBack={() => {}} />);
      choose = await screen.findByRole('button', { name: /choose game display/i });
      await waitFor(() => expect(choose.disabled).toBe(false)); fireEvent.click(choose);
      await waitFor(() => expect(picker).toHaveBeenCalledTimes(2));
      expect(starts).toBe(1); // The replacement cannot overtake the pending HTTP start.
      await act(async () => { resolveOld({ active: true, session: 'old' }); });
      const surface = await screen.findByRole('application');
      await waitFor(() => expect(perform).toHaveBeenCalledWith('screen_stop', { session: 'old' }));
      expect(owner).toBe('new');
      fireEvent.keyDown(surface, { code: 'KeyZ' });
      await waitFor(() => expect(perform).toHaveBeenCalledWith('screen_keys', { session: 'new', keys: ['KeyZ'] }));
      expect(tracks[1].stop).not.toHaveBeenCalled();
      fireEvent.click(screen.getByRole('button', { name: /stop preview/i }));
      await waitFor(() => expect(owner).toBeNull());
      expect(perform.mock.calls.filter(([action]) => action === 'screen_stop').every(([, payload]) => Boolean(payload.session))).toBe(true);
    } finally { cleanup(); play.mockRestore(); delete navigator.mediaDevices; }
  });

  it('stops a relay whose start completes after the game closes', async () => {
    let resolveStart;
    const track = new EventTarget(); track.readyState = 'live'; track.stop = vi.fn();
    const stream = { getTracks: () => [track], getVideoTracks: () => [track] };
    Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getDisplayMedia: vi.fn().mockResolvedValue(stream) } });
    perform.mockImplementation(action => action === 'screen_info' ? Promise.resolve({ available: true })
      : action === 'screen_start' ? new Promise(resolve => { resolveStart = resolve; }) : Promise.resolve({ active: false }));
    try {
      const view = render(<GameMirror gameRunning onBack={() => {}} />);
      const choose = await screen.findByRole('button', { name: /choose game display/i });
      await waitFor(() => expect(choose.disabled).toBe(false)); fireEvent.click(choose);
      await waitFor(() => expect(resolveStart).toBeTypeOf('function'));
      view.rerender(<GameMirror gameRunning={false} onBack={() => {}} />);
      expect(track.stop).toHaveBeenCalled();
      await act(async () => { resolveStart({ active: true, session: 'cancelled' }); });
      await waitFor(() => expect(perform).toHaveBeenCalledWith('screen_stop', { session: 'cancelled' }));
      expect(screen.queryByRole('application')).toBeNull();
      expect(choose.disabled).toBe(true);
    } finally { delete navigator.mediaDevices; }
  });

  it('abandons a pending picker if the game closes', async () => {
    let resolvePicker;
    const picker = vi.fn().mockImplementation(() => new Promise(resolve => { resolvePicker = resolve; }));
    Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getDisplayMedia: picker } });
    perform.mockImplementation(async action => action === 'screen_info' ? { available: true } : { active: true, session: 'preview-session' });
    const track = new EventTarget(); track.readyState = 'live'; track.stop = vi.fn();
    const stream = { getTracks: () => [track], getVideoTracks: () => [track] };
    try {
      const view = render(<GameMirror gameRunning onBack={() => {}} />);
      const choose = await screen.findByRole('button', { name: /choose game display/i });
      await waitFor(() => expect(choose.disabled).toBe(false));
      fireEvent.click(choose);
      view.rerender(<GameMirror gameRunning={false} onBack={() => {}} />);
      resolvePicker(stream);
      await waitFor(() => expect(track.stop).toHaveBeenCalledOnce());
      expect(perform.mock.calls.some(call => call[0] === 'screen_start')).toBe(false);
    } finally { delete navigator.mediaDevices; }
  });

  it('does not start browser control if window sharing is cancelled', async () => {
    const picker = vi.fn().mockRejectedValue(new DOMException('cancel', 'NotAllowedError'));
    Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getDisplayMedia: picker } });
    perform.mockImplementation(async action => action === 'screen_info' ? { available: true } : { active: true, session: 'preview-session' });
    try {
      render(<GameMirror gameRunning onBack={() => {}} />);
      const choose = await screen.findByRole('button', { name: /choose game display/i });
      await waitFor(() => expect(choose.disabled).toBe(false)); fireEvent.click(choose);
      expect((await screen.findByRole('status')).textContent).toMatch(/cancelled/i);
      expect(perform.mock.calls.some(call => call[0] === 'screen_start')).toBe(false);
    } finally { delete navigator.mediaDevices; }
  });

  it('prevents joining with a missing or oversized invitation', async () => {
    const { container } = render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: /join a world/i }));
    const modal = screen.getByRole('dialog');
    expect(within(modal).getByRole('button', { name: /^join and play$/i }).disabled).toBe(true);
    const file = new File(['x'.repeat(4097)], 'invite.json', { type: 'application/json' });
    fireEvent.change(container.querySelector('input[type=file]'), { target: { files: [file] } });
    expect(within(modal).getByRole('alert').textContent).toMatch(/too large/i);
    expect(perform).not.toHaveBeenCalled();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('accepts a dropped invitation without connecting until confirmed', async () => {
    render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: /join a world/i }));
    const modal = screen.getByRole('dialog');
    const raw = JSON.stringify({ version: 1, trainer: 'May' });
    fireEvent.drop(within(modal).getByRole('button', { name: /choose invitation file/i }), {
      dataTransfer: { files: [{ name: 'invite.json', size: raw.length, text: async () => raw }] },
    });
    await waitFor(() => expect(within(modal).getByRole('button', { name: /^join and play$/i }).disabled).toBe(false));
    expect(perform).not.toHaveBeenCalled();
  });

  it('imports an invitation only after the player chooses to join', async () => {
    const { container } = render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: /join a world/i }));
    const raw = JSON.stringify({ version: 1, trainer: 'May' });
    const file = { name: 'invite.json', size: raw.length, text: async () => raw };
    fireEvent.change(container.querySelector('input[type=file]'), { target: { files: [file] } });
    const modal = screen.getByRole('dialog');
    const join = await within(modal).findByRole('button', { name: /^join and play$/i });
    await waitFor(() => expect(join.disabled).toBe(false));
    expect(perform).not.toHaveBeenCalled();
    fireEvent.click(join);
    await waitFor(() => expect(perform).toHaveBeenCalledWith('join', { invitation: raw }));
  });

  it('makes the last saved adventure playable directly from the home page', async () => {
    render(<App />);
    const play = await screen.findByRole('button', { name: /^play now$/i });
    fireEvent.click(play);
    await waitFor(() => expect(perform).toHaveBeenCalledWith('launch', {}));
    expect(perform.mock.calls.map(call => call[0]).slice(-2)).toEqual(['rejoin', 'launch']);
  });

  it('launches the already connected world without reconnecting', async () => {
    loadState.mockResolvedValue({ ...snapshot(), connected: true, world_key: 'remote-1234', trainer: 'May' });
    render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: /^play now$/i }));
    await waitFor(() => expect(perform).toHaveBeenCalledWith('launch', {}));
    expect(perform.mock.calls.some(call => call[0] === 'rejoin')).toBe(false);
  });

  it('joins and starts the game as one player action', async () => {
    const { container } = render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: /join a world/i }));
    const raw = JSON.stringify({ version: 1, trainer: 'May' });
    const file = { name: 'invite.json', size: raw.length, text: async () => raw };
    fireEvent.change(container.querySelector('input[type=file]'), { target: { files: [file] } });
    const modal = screen.getByRole('dialog');
    const button = await within(modal).findByRole('button', { name: /^join and play$/i });
    await waitFor(() => expect(button.disabled).toBe(false));
    fireEvent.click(button);
    await waitFor(() => expect(perform).toHaveBeenCalledWith('launch', {}));
    expect(perform.mock.calls.map(call => call[0]).slice(-2)).toEqual(['join', 'launch']);
  });

  it('keeps the connected world available if the game fails to open', async () => {
    const connected = { ...snapshot(), connected: true, trainer: 'May', world_key: 'remote-1234' };
    perform.mockImplementation(async action => {
      if (action === 'join') { loadState.mockResolvedValue(connected); return connected; }
      if (action === 'launch') throw new Error('Game is not built.');
      return connected;
    });
    const { container } = render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: /join a world/i }));
    const raw = JSON.stringify({ version: 1, trainer: 'May' });
    fireEvent.change(container.querySelector('input[type=file]'), { target: { files: [{ name: 'invite.json', size: raw.length, text: async () => raw }] } });
    const modal = screen.getByRole('dialog');
    const button = await within(modal).findByRole('button', { name: /^join and play$/i });
    await waitFor(() => expect(button.disabled).toBe(false));
    fireEvent.click(button);
    expect((await screen.findByRole('alert')).textContent).toMatch(/Game is not built/);
    await waitFor(() => expect(screen.getByRole('button', { name: /play now/i })).toBeTruthy());
  });

  it('asks before switching away from a running game', async () => {
    const connected = { ...snapshot(), connected: true, trainer: 'May', world_key: 'another-world', games: ['May'] };
    loadState.mockResolvedValue(connected);
    render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: /play our hoenn/i }));
    const modal = screen.getByRole('dialog');
    expect(modal.textContent).toMatch(/save in the game first/i);
    expect(perform).not.toHaveBeenCalled();
    fireEvent.click(within(modal).getByRole('button', { name: /switch and continue/i }));
    await waitFor(() => expect(perform).toHaveBeenCalledWith('launch', {}));
    expect(perform.mock.calls.map(call => call[0]).slice(-3)).toEqual(['disconnect', 'rejoin', 'launch']);
  });

  it('lets the player paste a private invitation and confirm the connection', async () => {
    render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: /join a world/i }));
    const modal = screen.getByRole('dialog');
    fireEvent.click(within(modal).getByRole('button', { name: /paste invitation/i }));
    const raw = JSON.stringify({ version: 1, trainer: 'May' });
    fireEvent.change(within(modal).getByLabelText(/invitation json/i), { target: { value: raw } });
    fireEvent.click(within(modal).getByRole('button', { name: /^use invitation$/i }));
    expect(perform).not.toHaveBeenCalled();
    fireEvent.click(within(modal).getByRole('button', { name: /^join and play$/i }));
    await waitFor(() => expect(perform).toHaveBeenCalledWith('join', { invitation: raw }));
  });

  it('creates a hosted world when an owner account is ready', async () => {
    loadState.mockResolvedValue({ ...snapshot(), hosting: { available: true, enrolled: true, loaded: false, worlds: [], pending: null } });
    render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: /create a world/i }));
    const modal = screen.getByRole('dialog');
    fireEvent.change(within(modal).getByLabelText(/world name/i), { target: { value: 'Our Hoenn' } });
    fireEvent.change(within(modal).getByLabelText(/trainer profile/i), { target: { value: 'May' } });
    fireEvent.click(within(modal).getByRole('button', { name: /create and play/i }));
    await waitFor(() => expect(perform).toHaveBeenCalledWith('host_create', { name: 'Our Hoenn', trainer: 'May' }));
  });

  it('restores an owner profile from a chosen backup', async () => {
    const hosting = { available: true, backup_available: true, enrolled: false, loaded: false, worlds: [], pending: null };
    loadState.mockResolvedValue({ ...snapshot(), hosting });
    const { container } = render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: /create a world/i }));
    const modal = screen.getByRole('dialog');
    fireEvent.click(within(modal).getByRole('button', { name: /^use backup$/i }));
    const raw = JSON.stringify({ kind: 'host-profile', pin: 'a'.repeat(64) });
    const file = { name: 'owner.json', size: raw.length, text: async () => raw };
    fireEvent.change(container.querySelector('input[type=file]'), { target: { files: [file] } });
    await within(modal).findByText('owner.json');
    fireEvent.click(within(modal).getByRole('button', { name: /^restore account$/i }));
    await waitFor(() => expect(perform).toHaveBeenCalledWith('host_restore', { profile: raw }));
  });

  it('warns before exporting the owner credential', async () => {
    const hosting = { available: true, backup_available: true, enrolled: true, loaded: true, worlds: [], pending: null };
    loadState.mockResolvedValue({ ...snapshot(), hosting });
    render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: /back up account/i }));
    const modal = screen.getByRole('dialog');
    expect(modal.textContent).toMatch(/anyone with it can manage/i);
    expect(perform).not.toHaveBeenCalled();
    fireEvent.click(within(modal).getByRole('button', { name: /create backup/i }));
    await waitFor(() => expect(perform).toHaveBeenCalledWith('host_export', {}));
  });

  it('asks before creating access for another world owner', async () => {
    const hosted = { available: true, enrolled: true, loaded: true, worlds: [], pending: null };
    loadState.mockResolvedValue({ ...snapshot(), hosting: hosted });
    render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: /invite an owner/i }));
    const modal = screen.getByRole('dialog');
    expect(modal.textContent).toMatch(/own hosted-world account/i);
    expect(perform).not.toHaveBeenCalled();
    fireEvent.click(within(modal).getByRole('button', { name: /create access file/i }));
    await waitFor(() => expect(perform).toHaveBeenCalledWith('host_invite_account', {}));
  });

  it('offers a private invitation as a download without showing its contents', async () => {
    const hosted = { available: true, enrolled: true, loaded: true, pending: null,
      worlds: [{ id: '1234567890abcdef', name: 'Our Hoenn', trainer: 'May' }] };
    loadState.mockResolvedValue({ ...snapshot(), hosting: hosted });
    perform.mockResolvedValue({ ...snapshot(), hosting: hosted, download: '{"token":"private-test-token"}' });
    const oldCreate = URL.createObjectURL, oldRevoke = URL.revokeObjectURL;
    URL.createObjectURL = vi.fn(() => 'blob:private-invitation');
    URL.revokeObjectURL = vi.fn();
    try {
      render(<App />);
      fireEvent.click(await screen.findByRole('button', { name: /invite friend/i }));
      const modal = await screen.findByRole('dialog');
      expect(modal.textContent).not.toContain('private-test-token');
      expect(within(modal).getByRole('link', { name: /download invitation/i }).getAttribute('href')).toBe('blob:private-invitation');
      fireEvent.click(within(modal).getByRole('button', { name: /done/i }));
      expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:private-invitation');
    } finally { URL.createObjectURL = oldCreate; URL.revokeObjectURL = oldRevoke; }
  });

  it('asks for a trainer before redeeming a hosted-world invite', async () => {
    const { container } = render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: /join a world/i }));
    const raw = JSON.stringify({ kind: 'world-join', version: 1 });
    const file = { name: 'invite.json', size: raw.length, text: async () => raw };
    fireEvent.change(container.querySelector('input[type=file]'), { target: { files: [file] } });
    const modal = screen.getByRole('dialog');
    const trainer = await within(modal).findByLabelText(/choose your trainer profile/i);
    fireEvent.change(trainer, { target: { value: 'May' } });
    fireEvent.click(within(modal).getByRole('button', { name: /^join and play$/i }));
    await waitFor(() => expect(perform).toHaveBeenCalledWith('host_join', { invitation: raw, trainer: 'May' }));
  });

  it('makes the separate offline copy choice explicit', async () => {
    render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: /your worlds/i }));
    fireEvent.click(await screen.findByRole('button', { name: /play offline/i }));
    const modal = screen.getByRole('dialog');
    expect(modal.textContent).toMatch(/never merges back/i);
    fireEvent.click(within(modal).getByRole('button', { name: /copy online save/i }));
    await waitFor(() => expect(perform).toHaveBeenCalledWith('offline', { world: 'remote-1234', copy: true }));
  });

  it('explains game closure before reconnecting', async () => {
    loadState.mockResolvedValue({ ...snapshot(), connected: true, trainer: 'May', games: ['May'] });
    render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: /^reconnect$/i }));
    const modal = screen.getByRole('dialog');
    expect(modal.textContent).toMatch(/save in the game first/i);
    expect(perform).not.toHaveBeenCalled();
    fireEvent.click(within(modal).getByRole('button', { name: /^reconnect and play$/i }));
    await waitFor(() => expect(perform).toHaveBeenCalledWith('reconnect', {}));
  });

  it('shows only reported nearby trainers and connection state', async () => {
    loadState.mockResolvedValue({ ...snapshot(), connected: true, trainer: 'May', games: ['May'],
      presence: { state: 'connected', nearby: [{ trainer: 'Brendan', ready: true, rendered: true }] } });
    render(<App />);
    expect(await screen.findByText('Brendan')).toBeTruthy();
    expect(screen.getByText('Game connected')).toBeTruthy();
    expect(screen.getByText('Available')).toBeTruthy();
  });

  it('starts a solo adventure without an invitation', async () => {
    render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: /new solo adventure/i }));
    const modal = screen.getByRole('dialog');
    fireEvent.change(within(modal).getByLabelText(/trainer profile/i), { target: { value: 'May' } });
    fireEvent.click(within(modal).getByRole('button', { name: /start adventure/i }));
    await waitFor(() => expect(perform).toHaveBeenCalledWith('solo_new', { trainer: 'May' }));
  });

  it('copies an optional save into a new solo adventure', async () => {
    const { container } = render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: /new solo adventure/i }));
    const modal = screen.getByRole('dialog');
    const bytes = new Uint8Array([1, 2, 3]);
    const file = { name: 'emerald.sav', size: bytes.length, arrayBuffer: async () => bytes.buffer };
    fireEvent.change(container.querySelector('input[accept^=".sav"]'), { target: { files: [file] } });
    await within(modal).findByText('emerald.sav');
    fireEvent.click(within(modal).getByRole('button', { name: /start adventure/i }));
    await waitFor(() => expect(perform).toHaveBeenCalledWith('solo_new', { trainer: 'Player', seed: 'AQID' }));
  });

  it('can resume an offline adventure with no saved connection', async () => {
    loadState.mockResolvedValue({ ...snapshot(), worlds: [], offline_saves: [{ world: 'solo-a', trainer: 'May', name: 'Solo adventure' }] });
    render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: /^play solo adventure$/i }));
    await waitFor(() => expect(perform).toHaveBeenCalledWith('solo_resume', { world: 'solo-a', trainer: 'May' }));
  });

  it('lets players search and favorite saved worlds', async () => {
    render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: /your worlds/i }));
    const search = screen.getByRole('searchbox', { name: /search saved worlds/i });
    fireEvent.change(search, { target: { value: 'unmatched' } });
    expect(screen.getByText(/no worlds match/i)).toBeTruthy();
    fireEvent.change(search, { target: { value: 'May' } });
    fireEvent.click(screen.getByRole('button', { name: /add our hoenn to favorites/i }));
    await waitFor(() => expect(perform).toHaveBeenCalledWith('favorite', { world: 'remote-1234', favorite: true }));
  });

  it('renames a saved world locally', async () => {
    render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: /your worlds/i }));
    fireEvent.click(await screen.findByRole('button', { name: /^rename$/i }));
    const modal = screen.getByRole('dialog');
    fireEvent.change(within(modal).getByLabelText(/world name/i), { target: { value: 'Our Hoenn' } });
    fireEvent.click(within(modal).getByRole('button', { name: /save name/i }));
    await waitFor(() => expect(perform).toHaveBeenCalledWith('rename', { world: 'remote-1234', label: 'Our Hoenn' }));
  });

  it('backs up a saved trainer only when requested', async () => {
    const originalCreate = URL.createObjectURL, originalRevoke = URL.revokeObjectURL;
    URL.createObjectURL = vi.fn(() => 'blob:private-save'); URL.revokeObjectURL = vi.fn();
    perform.mockImplementation(async action => action === 'save_backup_info' ? { available: true } :
      { data: 'AQID', filename: 'emerald-trainer-backup.sav' });
    try {
      render(<App />);
      fireEvent.click(await screen.findByRole('button', { name: /save backups/i }));
      fireEvent.click(await screen.findByRole('button', { name: /create backup/i }));
      await waitFor(() => expect(perform).toHaveBeenCalledWith('save_backup', {
        world: 'remote-1234', trainer: 'May', offline: false,
      }));
      expect(await screen.findByRole('link', { name: /download save/i })).toBeTruthy();
      expect(screen.queryByText('AQID')).toBeNull();
      fireEvent.click(screen.getByRole('button', { name: /^done$/i }));
      expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:private-save');
    } finally { URL.createObjectURL = originalCreate; URL.revokeObjectURL = originalRevoke; }
  });

  it('confirms before closing a running offline game', async () => {
    loadState.mockResolvedValue({ ...snapshot(), games: ['offline/May'] });
    render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: /close game/i }));
    expect(perform).not.toHaveBeenCalled();
    const modal = screen.getByRole('dialog');
    expect(modal.textContent).toMatch(/save in the game first/i);
    fireEvent.click(within(modal).getByRole('button', { name: /close game/i }));
    await waitFor(() => expect(perform).toHaveBeenCalledWith('leave', { game: 'offline/May' }));
  });
});
