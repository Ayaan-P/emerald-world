// @vitest-environment jsdom
import React from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import WorldOptions from './WorldOptions';
const key = 'e-localworld12';
const flags = ['reusable_tms', 'evolution_items_from_bag', 'party_exp_share', 'mega_primal', 'z_moves', 'dynamax', 'terastallization', 'expanded_species_pool', 'pokemon_follower'];
const rules = () => ({ wild_shuffle: { enabled: false, seed: 7 }, ...Object.fromEntries(flags.map(key => [key, true])) });
const snapshot = value => ({local_worlds: [{key, name: 'RC10 lab', trainer: 'Player'}], world_options: {[key]: {status:'ready',version:3,revision:4,players:0,rules:value}}});
function props() { return {state: snapshot(rules()), worldKey:key, ready:true, busy:false, onSave:vi.fn(), onRefresh:vi.fn(), onDirtyChange:vi.fn(), onBack:vi.fn(), onChoose:vi.fn()}; }
afterEach(cleanup);
it('exposes only implemented V3 permissions with honest solo-battle limitations', async () => {
 const p = props(); const original = rules(); original.mega_primal = false; p.state = snapshot(original);
 const expected = {...original, mega_primal:true};
 p.onSave.mockResolvedValue({world_options:{[key]:{...p.state.world_options[key],revision:5,rules:expected}}});
 render(<WorldOptions {...p}/>);
 expect(screen.getAllByRole('checkbox')).toHaveLength(10);
 expect(screen.getByText(/solo battles only/i)).toBeTruthy();
 expect(screen.getByText(/does not grant Gigantamax/i)).toBeTruthy();
 fireEvent.click(screen.getByLabelText('Mega Evolution / Primal Reversion (solo battles)'));
 fireEvent.click(screen.getByRole('button',{name:'Review changes'}));
 expect(screen.getByText('Off → On')).toBeTruthy();
 fireEvent.click(screen.getByRole('button',{name:'Apply changes'}));
 await screen.findByText('World options saved.');
 expect(p.onSave).toHaveBeenCalledExactlyOnceWith({world:key,expected_revision:4,rules:expected,confirmed:true});
});
it('treats a V3 flag mismatch as uncertain and does not retry after polling', async () => {
 const p = props(); const view = render(<WorldOptions {...p}/>);
 fireEvent.click(screen.getByLabelText('Wild shuffle'));
 fireEvent.click(screen.getByRole('button',{name:'Review changes'}));
 const changed = {...rules(), mega_primal:false, wild_shuffle:{enabled:true,seed:7}};
 p.onSave.mockResolvedValue({world_options:{[key]:{...p.state.world_options[key],revision:5,rules:changed}}});
 fireEvent.click(screen.getByRole('button',{name:'Apply changes'}));
 await screen.findByText(/last save was not confirmed/);
 view.rerender(<WorldOptions {...p} state={snapshot(rules())}/>);
 expect(screen.getByRole('button',{name:'Review changes'}).disabled).toBe(true);
 expect(screen.getByLabelText('Mega Evolution / Primal Reversion (solo battles)').disabled).toBe(true);
 expect(p.onSave).toHaveBeenCalledTimes(1);
});
it('rejects unknown, missing and nonboolean V3 fields instead of inventing defaults', () => {
 const p = props();
 for (const bad of [{...rules(), unknown:false}, {...rules(), mega_primal:1}, Object.fromEntries(Object.entries(rules()).filter(([key])=>key!=='dynamax'))]) {
  const view = render(<WorldOptions {...p} state={snapshot(bad)}/>);
  expect(screen.queryByLabelText('Wild shuffle')).toBeNull();
  expect(screen.getByRole('button',{name:'Use default'}).disabled).toBe(true);
  view.unmount();
 }
 expect(p.onSave).not.toHaveBeenCalled();
});
it('preserves all nine V3 flags through shuffle review and save', async () => {
 const p = props(); const expected = {...rules(), wild_shuffle:{enabled:true,seed:7}};
 p.onSave.mockResolvedValue({world_options:{[key]:{...p.state.world_options[key],revision:5,rules:expected}}});
 render(<WorldOptions {...p}/>);
 fireEvent.click(screen.getByLabelText('Wild shuffle'));
 fireEvent.click(screen.getByRole('button',{name:'Review changes'}));
 fireEvent.click(screen.getByRole('button',{name:'Apply changes'}));
 await screen.findByText('World options saved.');
 expect(p.onSave).toHaveBeenCalledExactlyOnceWith({world:key,expected_revision:4,rules:expected,confirmed:true});
});
