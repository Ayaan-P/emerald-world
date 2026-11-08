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
it('resets every V3 permission and seed only after explicit review and apply', async () => {
 const p = props();
 const expected = {wild_shuffle:{enabled:false,seed:1}, ...Object.fromEntries(flags.map(key => [key,false]))};
 p.onSave.mockResolvedValue({world_options:{[key]:{...p.state.world_options[key],revision:5,rules:expected}}});
 render(<WorldOptions {...p}/>);
 fireEvent.click(screen.getByRole('button',{name:'Use default'}));
 expect(screen.getAllByRole('checkbox').every(input => !input.checked)).toBe(true);
 expect(screen.getByLabelText('Shuffle seed').value).toBe('1');
 expect(p.onSave).not.toHaveBeenCalled();
 fireEvent.click(screen.getByRole('button',{name:'Review changes'}));
 expect(screen.getAllByText('On → Off')).toHaveLength(9);
 expect(screen.getByText('7 → 1')).toBeTruthy();
 fireEvent.click(screen.getByRole('button',{name:'Keep editing'}));
 expect(p.onSave).not.toHaveBeenCalled();
 fireEvent.click(screen.getByRole('button',{name:'Review changes'}));
 fireEvent.click(screen.getByRole('button',{name:'Apply changes'}));
 await screen.findByText('World options saved.');
 expect(p.onSave).toHaveBeenCalledExactlyOnceWith({world:key,expected_revision:4,rules:expected,confirmed:true});
});
it('recognizes an expanded-only reset as dirty and keeps the player guard', () => {
 const p = props();
 const defaults = {wild_shuffle:{enabled:false,seed:1}, ...Object.fromEntries(flags.map(key => [key,false]))};
 p.state = snapshot({...defaults, expanded_species_pool:true});
 p.state.world_options[key].players = 1;
 const view = render(<WorldOptions {...p}/>);
 fireEvent.click(screen.getByRole('button',{name:'Use default'}));
 expect(screen.getByLabelText('Expanded species pool').checked).toBe(false);
 expect(screen.getByText('Unapplied changes')).toBeTruthy();
 expect(screen.getByRole('button',{name:'Review changes'}).disabled).toBe(true);
 p.state = snapshot({...defaults, expanded_species_pool:true});
 view.rerender(<WorldOptions {...p}/>);
 expect(screen.getByRole('button',{name:'Review changes'}).disabled).toBe(false);
 fireEvent.click(screen.getByRole('button',{name:'Review changes'}));
 expect(screen.getAllByText('On → Off')).toHaveLength(1);
 expect(p.onSave).not.toHaveBeenCalled();
});
it('leaves already-default V3 rules unchanged', () => {
 const p = props();
 p.state = snapshot({wild_shuffle:{enabled:false,seed:1}, ...Object.fromEntries(flags.map(key => [key,false]))});
 render(<WorldOptions {...p}/>);
 fireEvent.click(screen.getByRole('button',{name:'Use default'}));
 expect(screen.getByText('No changes')).toBeTruthy();
 expect(screen.getByRole('button',{name:'Review changes'}).disabled).toBe(true);
 expect(p.onSave).not.toHaveBeenCalled();
});
