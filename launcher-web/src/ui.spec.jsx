// @vitest-environment jsdom
import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { App } from './main';
import { loadState, perform } from './api';

vi.mock('./api', () => ({ loadState: vi.fn(), perform: vi.fn(), forgetCapability: vi.fn() }));

const snapshot = () => ({
  worlds: [{ key: 'remote-1234', name: 'Our Hoenn', trainer: 'May' }],
  offline_saves: [], presence: null, hosting: { available: false, enrolled: false, loaded: false, worlds: [], pending: null }, connected: false, trainer: null, games: [], setup: [], status: 'Ready',
});

beforeEach(() => { loadState.mockResolvedValue(snapshot()); perform.mockResolvedValue(snapshot()); });
afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe('player launcher', () => {
  it('prevents joining with a missing or oversized invitation', async () => {
    const { container } = render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: /join a world/i }));
    const modal = screen.getByRole('dialog');
    expect(within(modal).getByRole('button', { name: /^join world$/i }).disabled).toBe(true);
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
    await waitFor(() => expect(within(modal).getByRole('button', { name: /^join world$/i }).disabled).toBe(false));
    expect(perform).not.toHaveBeenCalled();
  });

  it('imports an invitation only after the player chooses to join', async () => {
    const { container } = render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: /join a world/i }));
    const raw = JSON.stringify({ version: 1, trainer: 'May' });
    const file = { name: 'invite.json', size: raw.length, text: async () => raw };
    fireEvent.change(container.querySelector('input[type=file]'), { target: { files: [file] } });
    const modal = screen.getByRole('dialog');
    const join = await within(modal).findByRole('button', { name: /^join world$/i });
    await waitFor(() => expect(join.disabled).toBe(false));
    expect(perform).not.toHaveBeenCalled();
    fireEvent.click(join);
    await waitFor(() => expect(perform).toHaveBeenCalledWith('join', { invitation: raw }));
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
    fireEvent.click(within(modal).getByRole('button', { name: /^join world$/i }));
    await waitFor(() => expect(perform).toHaveBeenCalledWith('join', { invitation: raw }));
  });

  it('creates a hosted world when an owner account is ready', async () => {
    loadState.mockResolvedValue({ ...snapshot(), hosting: { available: true, enrolled: true, loaded: false, worlds: [], pending: null } });
    render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: /create a world/i }));
    const modal = screen.getByRole('dialog');
    fireEvent.change(within(modal).getByLabelText(/world name/i), { target: { value: 'Our Hoenn' } });
    fireEvent.change(within(modal).getByLabelText(/trainer profile/i), { target: { value: 'May' } });
    fireEvent.click(within(modal).getByRole('button', { name: /create and connect/i }));
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
    fireEvent.click(within(modal).getByRole('button', { name: /^join world$/i }));
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
    fireEvent.click(within(modal).getByRole('button', { name: /^reconnect$/i }));
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
    fireEvent.click(await screen.findByRole('button', { name: /^play solo$/i }));
    const modal = screen.getByRole('dialog');
    fireEvent.change(within(modal).getByLabelText(/trainer profile/i), { target: { value: 'May' } });
    fireEvent.click(within(modal).getByRole('button', { name: /start adventure/i }));
    await waitFor(() => expect(perform).toHaveBeenCalledWith('solo_new', { trainer: 'May' }));
  });

  it('copies an optional save into a new solo adventure', async () => {
    const { container } = render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: /^play solo$/i }));
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
    fireEvent.click(await screen.findByRole('button', { name: /^continue$/i }));
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
