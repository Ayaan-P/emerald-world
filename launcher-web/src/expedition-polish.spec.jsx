// @vitest-environment jsdom
import React from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import ExpeditionPanel from './ExpeditionPanel';
import PlayerHome from './PlayerHome';
import ReleaseModes from './ReleaseModes';

afterEach(cleanup);
it('shows unexpected exit recovery from the last save only and hides it for a live game', () => {
  const homeState = { ...state, games: [], connected: true, worlds: [], offline_saves: [], hosting: { worlds: [] }, game_exit: { trainer: 'Player', code: 1, unexpected: true } };
  const { rerender } = render(<PlayerHome state={homeState} ready busy={false} />);
  expect(screen.getByRole('alert').textContent).toContain('Only your last in-game save');
  expect(screen.getByRole('alert').textContent).toContain('Unsaved progress is not restored automatically');
  rerender(<PlayerHome state={{ ...homeState, games: ['Player'] }} ready busy={false} />);
  expect(screen.queryByText('Your game closed unexpectedly')).toBeNull();
});
const state = { world_key: 'local-one', local_host: true, trainer: 'Player', cave_authoring: true, generated_areas: [] };
const props = { ready: true, busy: false, onOpen: vi.fn(), onActivate: vi.fn(), onAuthor: vi.fn() };

it('identifies the active area and blocks replacement while trainers are inside', () => {
  const onActivate = vi.fn();
  render(<ExpeditionPanel {...props} onActivate={onActivate} state={{ ...state,
    active_generated_area: { label: 'Wide islands', kind: 'xl_wilds', side: 127, occupants: 2 },
    generated_areas: [{ identity: 'other', label: 'Quiet cave', kind: 'cave', active: false }],
  }} />);
  const area = screen.getByRole('region', { name: 'Current exploration area' });
  expect(area.textContent).toContain('Wide islands');
  expect(area.textContent).toContain('127 × 127');
  expect(area.textContent).toContain('2 trainers inside');
  expect(screen.getByRole('button', { name: 'Use this area' }).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText('Area theme'), { target: { value: 'Another cave' } });
  expect(screen.getByRole('button', { name: 'Review generation', hidden: true }).disabled).toBe(true);
  expect(onActivate).not.toHaveBeenCalled();
});

it('keeps area help accurate without release labels', () => {
  render(<ReleaseModes />);
  const modes = screen.getByRole('region', { name: 'Generated areas' });
  expect(modes.textContent).toContain('Caves and outdoor worlds');
  expect(modes.textContent).not.toContain('RC8');
  expect(modes.textContent).toContain('Offline story tools');
  expect(modes.textContent).toContain('not shared multiplayer quests');
  expect(modes.textContent).toContain('does not start a director');
});

it('offers shared XL generation only after explicit paid-generation confirmation', async () => {
  const onAuthor = vi.fn().mockResolvedValue(true);
  render(<ExpeditionPanel {...props} onAuthor={onAuthor} state={{ ...state, xl_wilds_authoring: true }} />);
  fireEvent.change(screen.getByLabelText('Area type'), { target: { value: 'xl_wilds' } });
  fireEvent.change(screen.getByLabelText('Area theme'), { target: { value: 'Wide islands' } });
  expect(screen.getByText(/no generated characters, story graphs or editable overlays/)).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Review generation', hidden: true }));
  expect(onAuthor).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Confirm generation' }));
  await waitFor(() => expect(onAuthor).toHaveBeenCalledWith({ world: 'local-one', theme: 'Wide islands', kind: 'xl_wilds', confirmed: true }));
});

it('separates published adventures from fixed scenery without inventing an adventure', () => {
  const { rerender } = render(<ExpeditionPanel {...props} state={state} />);
  expect(screen.getByText('No published adventures.')).toBeTruthy();
  rerender(<ExpeditionPanel {...props} state={{ ...state, generated_areas: [
    { identity: 'event', label: 'Forest mystery', kind: 'event_wilds', active: false },
    { identity: 'cast', label: 'Quiet grove', kind: 'cast_wilds', active: true },
  ] }} />);
  const published = screen.getByRole('region', { name: 'Published adventures' });
  expect(within(published).getByText('Forest mystery')).toBeTruthy();
  expect(within(published).queryByText('Quiet grove')).toBeNull();
  expect(screen.getAllByText('Forest mystery')).toHaveLength(1);
  expect(within(published).getByText(/state resets on a new visit/)).toBeTruthy();
});

it('keeps a failed activation confirmation, and clears it only after success', async () => {
  const onActivate = vi.fn().mockResolvedValueOnce(false).mockResolvedValueOnce(true);
  render(<ExpeditionPanel {...props} onActivate={onActivate} state={{ ...state, generated_areas: [
    { identity: 'event', label: 'Forest mystery', kind: 'event_wilds' },
  ] }} />);
  fireEvent.click(screen.getByRole('button', { name: 'Open adventure' }));
  fireEvent.click(screen.getByRole('button', { name: 'Confirm open adventure' }));
  await waitFor(() => expect(screen.getByRole('status').textContent).toContain('Nothing retries automatically'));
  expect(onActivate).toHaveBeenCalledTimes(1);
  expect(onActivate).toHaveBeenCalledWith({ world: 'local-one', identity: 'event', confirmed: true });
  fireEvent.click(screen.getByRole('button', { name: 'Confirm open adventure' }));
  await waitFor(() => expect(screen.queryByRole('button', { name: 'Confirm open adventure' })).toBeNull());
  expect(screen.getByRole('status').textContent).toContain('Forest mystery is active');
});

it('retains the paid-generation draft and prevents duplicate submissions while pending', async () => {
  let finish;
  const onAuthor = vi.fn(() => new Promise(resolve => { finish = resolve; }));
  render(<ExpeditionPanel {...props} onAuthor={onAuthor} state={state} />);
  fireEvent.change(screen.getByLabelText('Area theme'), { target: { value: 'A mossy cave' } });
  fireEvent.click(screen.getByRole('button', { name: 'Review generation', hidden: true }));
  const confirm = screen.getByRole('button', { name: 'Confirm generation' });
  fireEvent.click(confirm);
  fireEvent.click(confirm);
  expect(onAuthor).toHaveBeenCalledTimes(1);
  expect(screen.getByRole('button', { name: 'Cancel' }).disabled).toBe(true);
  finish(false);
  await waitFor(() => expect(screen.getByRole('button', { name: 'Confirm generation' }).disabled).toBe(false));
  expect(screen.getByLabelText('Area theme').value).toBe('A mossy cave');
});

it('continues an existing local world for editing without launching and creates a new save host-only', () => {
  const onOpen = vi.fn();
  render(<ExpeditionPanel {...props} onOpen={onOpen} state={{ ...state, local_host: false, local_worlds: [
    { key: 'local-one', name: 'My expedition', trainer: 'Player', has_save: true },
  ] }} />);
  fireEvent.click(screen.getByRole('button', { name: 'Open local world' }));
  expect(onOpen).toHaveBeenLastCalledWith('local_resume', { world: 'local-one', trainer: 'Player' }, 'local-one', { playAfter: false });
  fireEvent.change(screen.getByLabelText('World name'), { target: { value: 'Fresh world' } });
  fireEvent.click(screen.getByRole('button', { name: 'Create local world', hidden: true }));
  expect(onOpen).toHaveBeenLastCalledWith('local_create', { name: 'Fresh world', trainer: 'Player' });
});
