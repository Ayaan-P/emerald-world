// @vitest-environment jsdom
import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { App } from './main';
import { loadState, perform } from './api';

vi.mock('./api', () => ({ loadState: vi.fn(), perform: vi.fn(), forgetCapability: vi.fn() }));

const snapshot = () => ({
  worlds: [{ key: 'remote-1234', name: 'Our Hoenn', trainer: 'May' }],
  offline_saves: [], presence: null, connected: false, trainer: null, games: [], setup: [], status: 'Ready',
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

  it('makes the separate offline copy choice explicit', async () => {
    render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: /your worlds/i }));
    fireEvent.click(await screen.findByRole('button', { name: /play offline/i }));
    const modal = screen.getByRole('dialog');
    expect(modal.textContent).toMatch(/never merges back/i);
    fireEvent.click(within(modal).getByRole('button', { name: /copy online save/i }));
    await waitFor(() => expect(perform).toHaveBeenCalledWith('offline', { world: 'remote-1234', copy: true }));
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
