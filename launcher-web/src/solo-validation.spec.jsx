// @vitest-environment jsdom
import React from 'react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
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
