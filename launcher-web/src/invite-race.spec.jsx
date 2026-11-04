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
const invite = trainer => JSON.stringify({ version: 1, trainer });
function deferredFile(name) {
  let resolve, reject;
  const text = new Promise((res, rej) => { resolve = res; reject = rej; });
  return { file: { name, size: 100, text: () => text }, resolve, reject };
}
async function openJoin() {
  fireEvent.click((await screen.findAllByRole('button', { name: /join a world/i }))[0]);
  return screen.getByRole('dialog');
}
function drop(modal, file) { fireEvent.drop(within(modal).getByRole('button', { name: /choose invitation file/i }), { dataTransfer: { files: [file] } }); }

it('keeps the most recently selected invitation when reads finish out of order', async () => {
  render(<App />); const modal = await openJoin();
  const first = deferredFile('old.json'), second = deferredFile('new.json');
  drop(modal, first.file); drop(modal, second.file);
  second.resolve(invite('New')); await screen.findByText('new.json');
  await act(async () => { first.resolve(invite('Old')); await Promise.resolve(); });
  await waitFor(() => expect(screen.queryByText('old.json')).toBeNull());
  expect(screen.getByText('new.json')).toBeTruthy();
});

it('ignores a pending file after the user switches to pasted text', async () => {
  render(<App />); const modal = await openJoin(); const old = deferredFile('old.json');
  drop(modal, old.file); fireEvent.click(within(modal).getByRole('button', { name: /paste invitation/i }));
  fireEvent.change(within(modal).getByLabelText('Invitation JSON'), { target: { value: invite('New') } });
  fireEvent.click(within(modal).getByRole('button', { name: /use invitation/i }));
  await act(async () => { old.resolve(invite('Old')); await Promise.resolve(); });
  await waitFor(() => expect(within(modal).getByRole('button', { name: /invitation ready/i })).toBeTruthy());
  expect(screen.queryByText('old.json')).toBeNull();
  fireEvent.click(within(modal).getByRole('button', { name: /join and play/i }));
  await waitFor(() => expect(perform).toHaveBeenCalledWith('join', { invitation: invite('New') }));
});

it('ignores a pending file after closing and reopening join', async () => {
  render(<App />); let modal = await openJoin(); const old = deferredFile('old.json');
  drop(modal, old.file); fireEvent.click(within(modal).getByRole('button', { name: /cancel/i }));
  modal = await openJoin(); await act(async () => { old.resolve(invite('Old')); await Promise.resolve(); });
  await waitFor(() => expect(within(modal).getByRole('button', { name: /join and play/i }).disabled).toBe(true));
  expect(screen.queryByText('old.json')).toBeNull();
});

it('does not show a stale read error after choosing another file', async () => {
  render(<App />); const modal = await openJoin();
  const old = deferredFile('old.json'), current = deferredFile('new.json');
  drop(modal, old.file); drop(modal, current.file);
  current.resolve(invite('New')); await screen.findByText('new.json');
  await act(async () => { old.reject(new Error('read failed')); await Promise.resolve(); });
  expect(within(modal).queryByRole('alert')).toBeNull();
  expect(within(modal).getByRole('button', { name: /join and play/i }).disabled).toBe(false);
});
