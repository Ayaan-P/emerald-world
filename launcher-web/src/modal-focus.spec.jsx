// @vitest-environment jsdom
import React from 'react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { App } from './main';
import { loadState, perform } from './api';
vi.mock('./api', () => ({ loadState: vi.fn(), perform: vi.fn(), forgetCapability: vi.fn() }));
const state = { worlds: [], offline_saves: [], presence: null, hosting: { available: false, enrolled: false, loaded: false, worlds: [], pending: null }, connected: false, trainer: null, games: [], setup: [], status: 'Ready' };
beforeEach(() => { loadState.mockResolvedValue(state); });
afterEach(() => { cleanup(); vi.clearAllMocks(); });
it('focuses replacement dialog content and restores the original opener', async () => {
  const hosted = { ...state, hosting: { ...state.hosting, available: true, enrolled: true, loaded: true, backup_available: true } };
  loadState.mockResolvedValue(hosted);
  perform.mockResolvedValue({ ...hosted, download: 'private owner backup', download_kind: 'backup' });
  const createURL = URL.createObjectURL, revokeURL = URL.revokeObjectURL;
  URL.createObjectURL = vi.fn(() => 'blob:owner'); URL.revokeObjectURL = vi.fn();
  try {
    render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: /^hosted worlds$/i }));
    fireEvent.click(screen.getByText('Owner account', { selector: 'summary' }));
    const opener = await screen.findByRole('button', { name: /back up account/i });
    opener.focus(); fireEvent.click(opener);
    const first = screen.getByRole('dialog');
    const confirm = within(first).getByRole('button', { name: /create backup/i });
    confirm.focus(); fireEvent.click(confirm);
    await screen.findByRole('heading', { name: /your backup is ready/i });
    expect(document.activeElement).toBe(screen.getByRole('dialog'));
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(document.activeElement).toBe(opener);
  } finally { URL.createObjectURL = createURL; URL.revokeObjectURL = revokeURL; }
});
it('keeps dialog focus stable while a request runs and restores its opener', async () => {
  let reject;
  perform.mockImplementation(() => new Promise((resolve, fail) => { reject = fail; }));
  render(<App />);
  const opener = await screen.findByRole('button', { name: /new solo save/i });
  opener.focus(); fireEvent.click(opener);
  const dialog = screen.getByRole('dialog'), input = within(dialog).getByLabelText('Trainer profile');
  input.focus();
  fireEvent.click(within(dialog).getByRole('button', { name: /start adventure/i }));
  expect(document.activeElement).toBe(input);
  fireEvent.keyDown(document, { key: 'Escape' });
  expect(screen.getByRole('dialog')).toBeTruthy();
  await act(async () => { reject(new Error('Could not start')); });
  expect(document.activeElement).toBe(input);
  fireEvent.click(within(dialog).getByRole('button', { name: /cancel/i }));
  expect(document.activeElement).toBe(opener);
});
