// @vitest-environment jsdom
import React from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import PlayerActivities from './PlayerActivities';
import FirstAdventure from './FirstAdventure';
import { App } from './main';
import { loadState, perform } from './api';
vi.mock('./api', () => ({ loadState:vi.fn(), perform:vi.fn(), forgetCapability:vi.fn() }));
afterEach(cleanup);
const state = { connected:true, world_key:'local', trainer:'Scout', local_host:true, local_worlds:[{key:'local',name:'My world',trainer:'Scout'}], local_hosts:['local'], hosting:{available:true,enrolled:true,worlds:[{id:'remote',name:'Cloud world'}]} };
it('renders only authority survey progress and public recap without mutations', async () => {
 const onRequest=vi.fn().mockResolvedValue({trainer:'Scout',survey:{revision:'abc',active:true,in_scope:true,complete:false,next_objective:{id:'ridge',x:8,y:9,revision:'abc'},visited:['camp'],landmarks:[{id:'camp',x:1,y:1},{id:'wrong-first',x:2,y:2},{id:'ridge',x:8,y:9}]},guild:null,offers:[],recap:[{seq:5,title:'Area activated',details:['Lantern Trail']}],coverage_start_seq:0});
 render(<PlayerActivities state={state} ready busy={false} onRequest={onRequest} onAdventure={()=>{}} />);
 await screen.findByText('1 of 3 landmarks discovered');
 expect(screen.getByText(/ridge near/)).toBeTruthy();
 expect(screen.getByRole('heading',{name:'Public world recap'})).toBeTruthy();
 expect(screen.getByText(/explicit share confirmation/)).toBeTruthy();
 expect(onRequest).toHaveBeenCalledExactlyOnceWith('player_activity_read',{world:'local'});
});
it('does not fetch private activity while disconnected', () => {
 const onRequest=vi.fn(); render(<PlayerActivities state={{...state,connected:false}} ready onRequest={onRequest} onAdventure={()=>{}} />);
 expect(onRequest).not.toHaveBeenCalled(); expect(screen.getByText(/Connect as your trainer/)).toBeTruthy();
});
it('previews named adventure and requires separate install confirmation', async () => {
 const onRequest=vi.fn().mockResolvedValueOnce({adventures:[{id:'lantern-trail',name:'Lantern Trail'}]}).mockResolvedValueOnce({token:'review',label:'Lantern Trail',guide:['Meet the resident at the trail entrance.'],validation:['Reviewed built-in route.']}).mockResolvedValueOnce({saved:true,guide:['Enter through the WORLD menu.']});
 render(<FirstAdventure state={state} ready busy={false} onRequest={onRequest} onOpen={vi.fn()} onHostedWorlds={()=>{}} />);
 fireEvent.click(await screen.findByRole('button',{name:'Review Lantern Trail'}));
 await screen.findByText('Meet the resident at the trail entrance.');
 expect(onRequest).toHaveBeenLastCalledWith('adventure_preview',{world:'local',adventure:'lantern-trail'});
 expect(screen.getByRole('button',{name:'Install reviewed adventure'}).disabled).toBe(true);
 fireEvent.click(screen.getByRole('checkbox'));
 fireEvent.click(screen.getByRole('button',{name:'Install reviewed adventure'}));
 await screen.findByText('Enter through the WORLD menu.');
 expect(onRequest).toHaveBeenLastCalledWith('adventure_apply',{world:'local',token:'review',confirmed:true});
 expect(onRequest).toHaveBeenCalledTimes(3);
});
it('explains hosted owner availability without declaring remote generation unsupported', () => {
 render(<FirstAdventure state={state} ready onRequest={vi.fn()} onOpen={vi.fn()} onHostedWorlds={()=>{}} />);
 expect(screen.getByText(/Hosted owners/)).toBeTruthy();
 expect(screen.getByText(/Requires the Expansion client and a durable world with area archiving/)).toBeTruthy();
 expect(screen.getByText(/remote generation remains available in Explore/)).toBeTruthy();
});
it('invalidates private results when the connected trainer changes', async () => {
 let finish;
 const onRequest=vi.fn().mockReturnValueOnce(new Promise(resolve=>{finish=resolve;})).mockResolvedValueOnce({trainer:'NewScout',survey:null,guild:null,offers:[],recap:[],coverage_start_seq:0});
 const p={state,ready:true,busy:false,onRequest,onAdventure:()=>{}};
 const view=render(<PlayerActivities {...p} />);
 view.rerender(<PlayerActivities {...p} state={{...state,trainer:'NewScout'}} />);
 await screen.findByText(/No guild membership/);
 finish({trainer:'Scout',survey:null,guild:null,offers:[],recap:[{seq:1,title:'Private stale result',details:[]}],coverage_start_seq:0});
 expect(screen.queryByText('Private stale result')).toBeNull();
});
it('does not open or read a background local host without an explicit selection', () => {
 const onRequest=vi.fn(), onOpen=vi.fn();
 render(<FirstAdventure state={{...state,world_key:'another'}} ready onRequest={onRequest} onOpen={onOpen} onHostedWorlds={()=>{}} />);
 expect(onRequest).not.toHaveBeenCalled(); expect(onOpen).not.toHaveBeenCalled();
 fireEvent.click(screen.getByRole('button',{name:'Open adventure host'}));
 expect(onOpen).toHaveBeenCalledExactlyOnceWith(state.local_worlds[0]);
});
it('does not retry an ambiguous install and requires a fresh review after failure', async () => {
 const onRequest=vi.fn().mockResolvedValueOnce({adventures:[]}).mockResolvedValueOnce({token:'review',guide:['Real compiler review']}).mockRejectedValueOnce(new Error('Connection lost. Refresh before retrying.'));
 render(<FirstAdventure state={state} ready onRequest={onRequest} onOpen={vi.fn()} onHostedWorlds={()=>{}} />);
 fireEvent.click(await screen.findByRole('button',{name:'Review Lantern Trail'}));
 await screen.findByText('Real compiler review'); fireEvent.click(screen.getByRole('checkbox'));
 fireEvent.click(screen.getByRole('button',{name:'Install reviewed adventure'}));
 await screen.findByRole('alert');
 expect(screen.queryByRole('button',{name:'Install reviewed adventure'})).toBeNull();
 expect(onRequest).toHaveBeenCalledTimes(3);
});
it('opens objectives and the named adventure through actual navigation', async () => {
 loadState.mockResolvedValue({...state,games:[],worlds:[],offline_saves:[],setup:[],status:'Ready'});
 perform.mockResolvedValue({trainer:'Scout',survey:null,guild:null,offers:[],recap:[],coverage_start_seq:0});
 render(<App />);
 fireEvent.click(await screen.findByRole('button',{name:'Objectives & recap'}));
 await screen.findByRole('heading',{name:'Your objectives & recap'});
 expect(perform).toHaveBeenCalledWith('player_activity_read',{world:'local'});
 fireEvent.click(screen.getByRole('button',{name:'First adventure'}));
 await screen.findByRole('heading',{name:'First adventure'});
});
