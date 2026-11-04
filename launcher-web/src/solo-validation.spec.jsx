// @vitest-environment jsdom
import React from 'react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { App } from './main';
import { loadState, perform } from './api';
vi.mock('./api', () => ({ loadState: vi.fn(), perform: vi.fn(), forgetCapability: vi.fn() }));
const state = { worlds: [], offline_saves: [], presence: null, hosting: { available: false, enrolled: false, loaded: false, worlds: [], pending: null }, connected: false, trainer: null, games: [], setup: [], status: 'Ready' };
beforeEach(() => { loadState.mockResolvedValue(state); perform.mockResolvedValue(state); });
afterEach(() => { cleanup(); vi.clearAllMocks(); });
it('validates the solo profile before starting the adventure', async () => {
  render(<App />); fireEvent.click(await screen.findByRole('button', { name: /play solo/i }));
  const modal = screen.getByRole('dialog'), input = within(modal).getByLabelText('Trainer profile');
  const start = within(modal).getByRole('button', { name: /start adventure/i });
  for (const value of ['', 'A B', 'é', ' spaces ']) {
    fireEvent.change(input, { target: { value } });
    expect(start.disabled).toBe(true);
    if (value) expect(input.getAttribute('aria-invalid')).toBe('true');
  }
  fireEvent.change(input, { target: { value: 'Ash_123-xy' } });
  expect(start.disabled).toBe(false);
  expect(input.getAttribute('aria-invalid')).toBe('false');
  expect(input.getAttribute('aria-describedby')).toBe('solo-trainer-help');
  expect(perform).not.toHaveBeenCalled();
});


it('lets the player cancel a stalled save import without starting with a stale file', async () => {
  let finish;
  const pending = new Promise(resolve => { finish = resolve; });
  const { container } = render(<App />);
  fireEvent.click(await screen.findByRole('button', { name: /play solo/i }));
  const modal = screen.getByRole('dialog');
  const input = container.querySelector('input[accept^=".sav"]');
  fireEvent.change(input, { target: { files: [{ name: 'slow.sav', size: 3, arrayBuffer: () => pending }] } });
  expect(within(modal).getByRole('button', { name: /start adventure/i }).disabled).toBe(true);
  fireEvent.click(within(modal).getByRole('button', { name: /cancel import/i }));
  expect(within(modal).getByRole('button', { name: /start adventure/i }).disabled).toBe(false);
  await act(async () => { finish(new Uint8Array([1, 2, 3]).buffer); await pending; });
  expect(within(modal).queryByText('slow.sav')).toBeNull();
  fireEvent.click(within(modal).getByRole('button', { name: /start adventure/i }));
  await waitFor(() => expect(perform).toHaveBeenCalledWith('solo_new', { trainer: 'Player' }));
});
