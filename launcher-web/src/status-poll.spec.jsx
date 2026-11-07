// @vitest-environment jsdom
import React from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import { act, cleanup, render, screen } from '@testing-library/react';
import { App } from './main';
import { loadState, perform } from './api';
vi.mock('./api', () => ({ loadState: vi.fn(), perform: vi.fn(), forgetCapability: vi.fn() }));
const state = { worlds: [], offline_saves: [], presence: null, hosting: { available: false, enrolled: false, loaded: false, worlds: [], pending: null }, connected: false, trainer: null, games: [], setup: [], status: 'Ready' };
afterEach(() => { cleanup(); vi.useRealTimers(); vi.clearAllMocks(); });
it('does not overlap slow state reads and resumes polling after one completes', async () => {
  vi.useFakeTimers();
  let resolve;
  loadState.mockImplementationOnce(() => new Promise(done => { resolve = done; })).mockResolvedValue(state);
  perform.mockResolvedValue(state);
  render(<App />);
  expect(loadState).toHaveBeenCalledTimes(1);
  await act(async () => { await vi.advanceTimersByTimeAsync(15000); });
  expect(loadState).toHaveBeenCalledTimes(1);
  await act(async () => { resolve(state); await Promise.resolve(); });
  expect(screen.getByText('Launcher ready')).toBeTruthy();
  await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
  expect(loadState).toHaveBeenCalledTimes(2);
});
it('retries polling after a state read fails', async () => {
  vi.useFakeTimers();
  loadState.mockRejectedValueOnce(new Error('temporary failure')).mockResolvedValue(state);
  render(<App />);
  await act(async () => { await Promise.resolve(); });
  expect(screen.getByRole('alert').textContent).toContain('temporary failure');
  await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
  expect(loadState).toHaveBeenCalledTimes(2);
  expect(screen.getByText('Launcher ready')).toBeTruthy();
});

it('times out a hung status read, retries, and clears only its own error', async () => {
  vi.useFakeTimers();
  loadState.mockImplementationOnce(({ signal }) => new Promise((resolve, reject) => {
    signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
  })).mockResolvedValue(state);
  render(<App />);
  await act(async () => { await vi.advanceTimersByTimeAsync(8000); });
  expect(screen.getByRole('alert').textContent).toMatch(/took too long/i);
  await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
  expect(loadState).toHaveBeenCalledTimes(2);
  expect(screen.getByText('Launcher ready')).toBeTruthy();
  expect(screen.queryByRole('alert')).toBeNull();
});
it('keeps an action error when a later status read succeeds', async () => {
  vi.useFakeTimers();
  loadState.mockResolvedValue(state);
  perform.mockRejectedValueOnce(new Error('Could not launch adventure'));
  render(<App />);
  await act(async () => { await Promise.resolve(); });
  await act(async () => { screen.getByRole('button', { name: /new solo save/i }).click(); });
  await act(async () => { screen.getByRole('button', { name: /start adventure/i }).click(); await Promise.resolve(); });
  expect(screen.getByRole('alert').textContent).toContain('Could not launch adventure');
  await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
  expect(screen.getByRole('alert').textContent).toContain('Could not launch adventure');
});
