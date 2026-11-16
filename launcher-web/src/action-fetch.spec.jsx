// @vitest-environment jsdom
import React from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { App } from './main';

// Exercise the actual api.js request/JSON path, with only the network replaced.
const base = { worlds: [], local_worlds: [], offline_saves: [], presence: null, hosting: { available: false, enrolled: false, loaded: false, worlds: [], pending: null }, connected: false, trainer: null, games: [], setup: [], status: 'Ready' };
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); sessionStorage.clear(); });
for (const phase of ['fetch', 'response body']) {
  it(`releases UI waiting when the action ${phase} never resolves, without aborting or resending the POST`, async () => {
    vi.useFakeTimers();
    sessionStorage.setItem('emerald-launcher-capability', 'test-only-capability');
    const fetch = vi.fn((path) => path === '/api/state'
      ? Promise.resolve({ ok: true, json: async () => base })
      : phase === 'fetch' ? new Promise(() => {})
      : Promise.resolve({ ok: true, json: () => new Promise(() => {}) }));
    vi.stubGlobal('fetch', fetch);
    render(<App />);
    await act(async () => {});
    fireEvent.click(screen.getByRole('button', { name: /new solo save/i }));
    fireEvent.click(screen.getByRole('button', { name: /start adventure/i }));
    await act(async () => { await vi.advanceTimersByTimeAsync(30000); });
    const dialog = screen.getByRole('dialog');
    expect(within(dialog).getByText(/outcome unknown/i)).toBeTruthy();
    expect(within(dialog).getByRole('button', { name: 'Close' }).disabled).toBe(false);
    fireEvent.keyDown(document, { key: 'Escape' });
    fireEvent.click(within(screen.getByRole('navigation')).getByRole('button', { name: 'Controls & help' }));
    expect(screen.getByRole('heading', { name: 'Controls & help' })).toBeTruthy();
    expect(fetch.mock.calls.filter(([path]) => path === '/api/state').length).toBeGreaterThan(1);
    const posts = fetch.mock.calls.filter(([path]) => path === '/api/action');
    expect(posts).toHaveLength(1);
    expect(posts[0][1].signal).toBeUndefined();
    expect(JSON.parse(posts[0][1].body).action).toBe('solo_new');
  });
}
