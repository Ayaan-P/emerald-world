// @vitest-environment jsdom
import React from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { App } from './main';
import { loadState, perform } from './api';
vi.mock('./api', () => ({ loadState: vi.fn(), perform: vi.fn(), forgetCapability: vi.fn() }));
const state = { worlds: [], offline_saves: [], presence: null, hosting: { available: false, enrolled: false, loaded: false, worlds: [], pending: null }, connected: false, trainer: null, games: [], setup: [], status: 'Ready', engine: 'expansion-native', save_import_max_bytes: 147524 };
afterEach(() => { cleanup(); vi.clearAllMocks(); });
async function open(limit=147524) {
  loadState.mockResolvedValue({ ...state, save_import_max_bytes: limit }); perform.mockResolvedValue(state);
  const view=render(<App />);
  fireEvent.click(await screen.findByRole('button',{name:/new solo save/i}));
  return { input:view.container.querySelector('input[accept^=".sav"]'), modal:screen.getByRole('dialog') };
}
it('passes every byte of a maximum-sized native regional save', async () => {
  const {input,modal}=await open();const bytes=new Uint8Array(147524);bytes[0]=80;bytes[bytes.length-1]=99;
  fireEvent.change(input,{target:{files:[{name:'regional.sav',size:bytes.length,arrayBuffer:async()=>bytes.buffer}]}});
  await within(modal).findByText('regional.sav');fireEvent.click(within(modal).getByRole('button',{name:/start adventure/i}));
  await waitFor(()=>expect(perform).toHaveBeenCalledWith('solo_new',{trainer:'Player',seed:expect.any(String)}));
  const data=atob(perform.mock.calls.find(call=>call[0]==='solo_new')[1].seed);
  expect(data.length).toBe(bytes.length);expect(data.charCodeAt(0)).toBe(80);expect(data.charCodeAt(data.length-1)).toBe(99);
});
it('refuses oversized native saves before reading',async()=>{
  const {input}=await open();const read=vi.fn();
  fireEvent.change(input,{target:{files:[{name:'large.sav',size:147525,arrayBuffer:read}]}});
  await screen.findByText(/Choose a nonempty save file no larger than/);expect(read).not.toHaveBeenCalled();expect(perform).not.toHaveBeenCalled();
});
it('keeps the vanilla bound and checks the actual bytes after reading',async()=>{
  const {input}=await open(131072);const read=vi.fn(async()=>new Uint8Array(131073).buffer);
  fireEvent.change(input,{target:{files:[{name:'growing.sav',size:131072,arrayBuffer:read}]}});
  await screen.findByText(/Could not read that save file/);expect(perform).not.toHaveBeenCalled();
});
