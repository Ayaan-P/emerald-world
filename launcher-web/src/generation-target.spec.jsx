// @vitest-environment jsdom
import React from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import ExpeditionPanel from './ExpeditionPanel';

afterEach(() => { cleanup(); vi.clearAllMocks(); });
const props = { ready: true, busy: false, onOpen: vi.fn(), onAuthor: vi.fn(), onActivate: vi.fn() };
const owned = { id: 'one', name: 'Cloud grove', trainer: 'Owner' };

it('selects an owned hosted target without opening or playing a world', () => {
  const onSelectHostedArea = vi.fn();
  render(<ExpeditionPanel {...props} onSelectHostedArea={onSelectHostedArea} state={{ local_host: false, hosting: { enrolled: true, loaded: true, worlds: [owned] } }} />);
  fireEvent.click(screen.getByRole('button', { name: 'Select Cloud grove for generation' }));
  expect(onSelectHostedArea).toHaveBeenCalledWith(owned);
  expect(props.onOpen).not.toHaveBeenCalled();
  expect(props.onAuthor).not.toHaveBeenCalled();
});

it('authors and activates the hosted area target, never the running solo identity', async () => {
  const state = { world_key: 'solo', area_world_key: 'hosted-one', area_authoring: true, hosted_area_world: owned, cave_authoring: true, cave_persistent: true, games: ['offline/Player'], generated_areas: [{ identity: 'saved', label: 'Old cave', kind: 'cave' }] };
  const { rerender } = render(<ExpeditionPanel {...props} state={state} />);
  expect(screen.getByRole('heading', { name: 'Cloud grove' })).toBeTruthy();
  fireEvent.change(screen.getByLabelText('Area theme'), { target: { value: 'Cloud cave' } });
  fireEvent.click(screen.getByRole('button', { name: 'Review generation' }));
  expect(props.onAuthor).not.toHaveBeenCalled();
  expect(screen.getByText(/usage may incur charges/)).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Confirm generation' }));
  expect(props.onAuthor).toHaveBeenCalledWith({ world: 'hosted-one', kind: 'cave', theme: 'Cloud cave', confirmed: true });
  await waitFor(() => expect(screen.getByRole('button', { name: 'Confirm generation' }).disabled).toBe(false));
  rerender(<ExpeditionPanel {...props} state={{ ...state, area_world_key: 'hosted-two' }} />);
  expect(screen.queryByRole('button', { name: 'Confirm generation' })).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: 'Use this area' }));
  fireEvent.click(screen.getByRole('button', { name: 'Activate saved area' }));
  expect(props.onActivate).toHaveBeenCalledWith({ world: 'hosted-two', identity: 'saved', confirmed: true });
});

it('shows owner-selection errors without enabling unsupported generation or leaking stale confirmations', () => {
  const { rerender } = render(<ExpeditionPanel {...props} state={{ area_authoring: true, area_world_key: 'hosted-one', hosted_area_world: owned, cave_authoring: true }} />);
  fireEvent.change(screen.getByLabelText('Area theme'), { target: { value: 'A cave' } });
  fireEvent.click(screen.getByRole('button', { name: 'Review generation' }));
  rerender(<ExpeditionPanel {...props} state={{ area_authoring: false, area_world_key: 'hosted-one', hosted_area_error: 'Owner access unavailable' }} />);
  expect(screen.getByRole('alert').textContent).toBe('Owner access unavailable');
  expect(screen.queryByRole('button', { name: 'Confirm generation' })).toBeNull();
  expect(screen.getByRole('button', { name: 'Review generation' }).disabled).toBe(true);
  expect(props.onAuthor).not.toHaveBeenCalled();
});

it('keeps generation discoverable in solo with a disabled reason and local setup path', () => {
  render(<ExpeditionPanel {...props} state={{ local_host: false, world_key: 'solo', games: ['offline/Player'] }} />);
  expect(screen.getByRole('heading', { name: 'Generate an area' })).toBeTruthy();
  expect(screen.getByLabelText('Area type').disabled).toBe(true);
  expect(screen.getByLabelText('Area theme').disabled).toBe(true);
  expect(screen.getByRole('button', { name: 'Review generation' }).disabled).toBe(true);
  expect(screen.getByText(/Generation is not available in solo or offline story mode/)).toBeTruthy();
  expect(screen.getByText('Create a local world', { selector: 'summary' })).toBeTruthy();
  expect(props.onAuthor).not.toHaveBeenCalled();
});
