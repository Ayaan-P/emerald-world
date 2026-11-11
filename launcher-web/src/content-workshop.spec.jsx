// @vitest-environment jsdom
import React from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import ContentWorkshop from './ContentWorkshop';
import { App } from './main';
import { loadState, perform } from './api';
vi.mock('./api', () => ({ loadState: vi.fn(), perform: vi.fn(), forgetCapability: vi.fn() }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });
const info = { world: 'local', identity: 'a'.repeat(64), version: 16, rows: ['###','#.#','###'], residents: ['old_friend'], outcomes: [{seq: 15, guild_name: 'My guild', goal_kind: 'expedition'}], players: 0 };
const props = { world: {key: 'local', name: 'My world'}, available: true, ready: true, busy: false, onBack: vi.fn(), onOpen: vi.fn() };
it('previews authored content then applies only a server-held review token', async () => {
  const request = vi.fn(async (action, payload) => action === 'content_preview' ? {...info,token:'review-token',report:{added_walkable_tiles: 35},proposed_rows:info.rows,plan:payload.plan} : action === 'content_apply' ? {...info,saved:true} : info);
  render(<ContentWorkshop {...props} onRequest={request} />);
  await screen.findByText(/old_friend/);
  fireEvent.click(screen.getByRole('button', {name:'Start editable plan'}));
  expect(request).toHaveBeenCalledTimes(1);
  fireEvent.change(screen.getByLabelText('Destination name'), {target:{value:'My courtyard'}});
  fireEvent.click(screen.getByRole('button',{name:'Preview content'}));
  await screen.findByRole('heading',{name:'Review content'});
  expect(request.mock.calls.filter(([a]) => a === 'content_apply')).toHaveLength(0);
  fireEvent.click(screen.getByLabelText(/I reviewed/));
  fireEvent.click(screen.getByRole('button',{name:'Apply reviewed content'}));
  await screen.findByText(/Content saved/);
  expect(request).toHaveBeenLastCalledWith('content_apply',{world:'local',token:'review-token',confirmed:true});
});
it('clears review on edits and never applies a stale or uncertain result again', async () => {
  const request = vi.fn(async (action,payload) => action === 'content_preview' ? {...info,token:'t',report:{},proposed_rows:info.rows,plan:payload.plan} : info);
  render(<ContentWorkshop {...props} onRequest={request} />);
  await screen.findByText(/old_friend/);
  fireEvent.click(screen.getByRole('button',{name:'Start editable plan'}));
  fireEvent.change(screen.getByLabelText('Destination name'),{target:{value:'Test'}});
  fireEvent.click(screen.getByRole('button',{name:'Preview content'}));
  await screen.findByRole('heading',{name:'Review content'});
  fireEvent.change(screen.getByLabelText('Content plan JSON'),{target:{value:'{}'}});
  expect(screen.queryByRole('button',{name:'Apply reviewed content'})).toBeNull();
});
it('offers a populated curated field-test preview without publishing anything or requesting a model', async () => {
  const request = vi.fn(async (action,payload) => action === 'content_preview' ? {...info,identity:null,token:'field-test',report:{},proposed_rows:info.rows,plan:{character:{id:'rc11_scholar'}}} : {...info,identity:null,rows:[],residents:[]});
  render(<ContentWorkshop {...props} onRequest={request} />);
  await screen.findByLabelText('Content type');
  fireEvent.change(screen.getByLabelText('Content type'),{target:{value:'field_test'}});
  fireEvent.click(screen.getByRole('button',{name:'Preview RC11 field test'}));
  await screen.findByRole('heading',{name:'Review content'});
  expect(request).toHaveBeenLastCalledWith('content_preview',{world:'local',kind:'field_test',label:'RC11 field test',plan:{},outcome_seq:null});
  expect(request.mock.calls.filter(([a]) => a === 'content_apply')).toHaveLength(0);
  expect(screen.getByText(/lookout.*22.*8/)).toBeTruthy();
});

it('exposes the workshop from the existing Local worlds launcher page', async () => {
  loadState.mockResolvedValue({local_worlds:[{key:'local',name:'My world',trainer:'Player'}],local_hosts:['local'],engine:'expansion-native',local_host:true,world_key:'local',worlds:[],offline_saves:[],games:[],hosting:{available:false,worlds:[]},setup:[],status:'Ready'});
  perform.mockResolvedValue(info);
  render(<App />);
  fireEvent.click(await screen.findByRole('button',{name:'Local worlds'}));
  fireEvent.click(await screen.findByRole('button',{name:'Author content'}));
  await screen.findByRole('heading',{name:'Content workshop'});
  await waitFor(() => expect(perform).toHaveBeenCalledWith('content_read',{world:'local'}));
});
it('installs the complete cooperative preset only after review and shows the right player entry', async () => {
  const request=vi.fn(async (action,payload) => action==='content_preview' ? {...info,kind:'field_story',token:'story-review',report:{stages:2},plan:{mystery:{id:'signal_v2'},story:{id:'signal_after_v2'}},proposed_rows:info.rows} : action==='content_apply' ? {...info,saved:true,field_story:{installed:true}} : info);
  render(<ContentWorkshop {...props} onRequest={request} />);
  await screen.findByLabelText('Content type');
  fireEvent.change(screen.getByLabelText('Content type'),{target:{value:'field_story'}});
  expect(screen.queryByLabelText('Content plan JSON')).toBeNull();
  fireEvent.click(screen.getByRole('button',{name:'Preview cooperative field story'}));
  await screen.findByRole('heading',{name:'Review content'});
  expect(request).toHaveBeenLastCalledWith('content_preview',{world:'local',kind:'field_story',label:'The Two-Tower Signal',plan:{},outcome_seq:null});
  expect(request.mock.calls.filter(([a])=>a==='content_apply')).toHaveLength(0);
  fireEvent.click(screen.getByLabelText(/I reviewed/));
  fireEvent.click(screen.getByRole('button',{name:'Apply reviewed content'}));
  await screen.findByText(/Both story parts are saved/);
  expect(screen.queryByText(/Content saved and read back/)).toBeNull();
  expect(request).toHaveBeenLastCalledWith('content_apply',{world:'local',token:'story-review',confirmed:true});
});
it('shows relay gameplay without publishing content or altering the world', async () => {
  const request=vi.fn(async()=>({...info,relay_courses:[{id:'petalburg_relay1',title:'Petalburg Baton Circuit',runners:2}]}));
  render(<ContentWorkshop {...props} onRequest={request}/>);
  await screen.findByLabelText('Content type');
  fireEvent.change(screen.getByLabelText('Content type'),{target:{value:'relay'}});
  expect(screen.getByRole('heading',{name:'Run a cooperative field relay'})).toBeTruthy();
  expect(screen.getByText(/petalburg_relay1 \(2 runners\)/)).toBeTruthy();
  expect(screen.getByText(/three-second countdown/)).toBeTruthy();
  expect(screen.queryByLabelText('Content plan JSON')).toBeNull();
  expect(screen.queryByRole('button',{name:/Preview|Apply/})).toBeNull();
  expect(request).toHaveBeenCalledTimes(1);
  expect(request).toHaveBeenCalledWith('content_read',{world:'local'});
});
it('offers capture-the-flag instructions without changing the local world', async () => {
  const request=vi.fn(async()=>info);
  render(<ContentWorkshop {...props} onRequest={request}/>);
  await screen.findByLabelText('Content type');
  fireEvent.change(screen.getByLabelText('Content type'),{target:{value:'flag'}});
  expect(screen.getByRole('heading',{name:'Capture the flag with a friend'})).toBeTruthy();
  expect(screen.getByText(/First to three captures wins/)).toBeTruthy();
  expect(screen.queryByRole('button',{name:/Preview|Apply/})).toBeNull();
  expect(request).toHaveBeenCalledTimes(1);
});
it('unifies installed games and explicit guild invitation consent without publishing', async () => {
  const request=vi.fn(async()=>({...info,activities:[{kind:'relay',id:'petalburg_relay1',title:'Petalburg Baton Circuit',players:2}]}));
  render(<ContentWorkshop {...props} onRequest={request}/>);
  await screen.findByRole('heading',{name:'Find something to play together'});
  expect(screen.getByText('Petalburg Baton Circuit')).toBeTruthy();
  expect(screen.getByText(/never your clues, choices or results/)).toBeTruthy();
  expect(screen.getByText(/No puzzle pack is installed here yet/)).toBeTruthy();
  expect(request).toHaveBeenCalledTimes(1);
});
it('distinguishes the actual mounted course from the trainer footrace and explains party requirements', async () => {
  render(<ContentWorkshop {...props} onRequest={vi.fn(async()=>info)}/>);
  await screen.findByLabelText('Content type');
  fireEvent.change(screen.getByLabelText('Content type'),{target:{value:'relay'}});
  expect(screen.getByText(/No Pokemon are granted by this mode/)).toBeTruthy();
  expect(screen.getByText(/Missing or overflowed movement reports cancel/)).toBeTruthy();
});
it('discovers living cast from Local worlds without starting a model', async () => {
  loadState.mockResolvedValue({local_worlds:[{key:'local',name:'My world',trainer:'Player'}],local_hosts:['local'],engine:'expansion-native',local_host:true,world_key:'local',worlds:[],offline_saves:[],games:[],hosting:{available:false,worlds:[]},setup:[],status:'Ready'});
  perform.mockResolvedValue({running:false,queued:0,failed_requests:0,providers:[],actors:[]});
  render(<App />);fireEvent.click(await screen.findByRole('button',{name:'Local worlds'}));fireEvent.click(await screen.findByRole('button',{name:'Living cast'}));
  await screen.findByRole('heading',{name:'Living cast agents'});
  await waitFor(()=>expect(perform).toHaveBeenCalledWith('cast_agent_read',{world:'local'}));
  expect(perform.mock.calls.some(([a])=>a==='cast_agent_start')).toBe(false);
});

it('reviews a real adventure graph and provides the correct entry without auto-enrolling', async () => {
  const plan={id:'journey',title:'My journey',entry:'meet',nodes:{meet:{visit:{label:'Meeting place',point:[0,9,8,8]},next:[]}}};
  const report={id:'journey',title:'My journey',entry:'meet',shared_only:false,stages:[{id:'meet',tasks:[{role:'all',kind:'visit',label:'Meeting place',point:[0,9,8,8]}],routes:[],loss_routes:[]}]};
  const request=vi.fn(async action => action==='content_preview' ? {...info,kind:'adventure',token:'adventure-review',report,plan,proposed_rows:info.rows} : action==='content_apply' ? {...info,saved:true,adventure:{...report,installed:true}} : {...info,adventures:[]});
  render(<ContentWorkshop {...props} onRequest={request} />);
  fireEvent.change(await screen.findByLabelText('Content type'),{target:{value:'adventure'}});
  fireEvent.change(screen.getByLabelText('Adventure JSON'),{target:{value:JSON.stringify(plan)}});
  fireEvent.click(screen.getByRole('button',{name:'Review adventure'}));
  await screen.findByRole('heading',{name:'Review content'});
  expect(screen.getByText(/Map 0\/9, tile 8,8/)).toBeTruthy();
  expect(request.mock.calls.filter(([a])=>a==='content_apply')).toHaveLength(0);
  fireEvent.click(screen.getByLabelText(/I reviewed/));fireEvent.click(screen.getByRole('button',{name:'Apply reviewed content'}));
  await screen.findByRole('heading',{name:'Adventure saved'});
  expect(screen.getByText(/campaign start journey/)).toBeTruthy();
  expect(request).toHaveBeenLastCalledWith('content_apply',{world:'local',token:'adventure-review',confirmed:true});
});
