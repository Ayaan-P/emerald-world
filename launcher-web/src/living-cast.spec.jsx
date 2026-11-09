// @vitest-environment jsdom
import React from 'react';
import {afterEach,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen} from '@testing-library/react';
import LivingCast from './LivingCast';
afterEach(cleanup);
const info={running:false,queued:0,failed_requests:0,providers:[{id:'anthropic-messages',credential_ready:true}],actors:[{id:'canon_rydel',name:'Rydel',authored:true,followed:false,goal:'Consider actual events'}]};
const props={world:{key:'local'},available:true,ready:true,busy:false};
it('reads only, then starts the explicit provider/model after confirmation',async()=>{
 const request=vi.fn(async()=>info);render(<LivingCast {...props} onRequest={request}/>);
 await screen.findByText('Current goal: Consider actual events');expect(request).toHaveBeenCalledTimes(1);
 const start=screen.getByRole('button',{name:'Start world author'});expect(start.disabled).toBe(true);
 fireEvent.change(screen.getByLabelText('Exact API model ID'),{target:{value:'selected-claude'}});fireEvent.click(screen.getByRole('checkbox'));fireEvent.click(start);
 expect(request).toHaveBeenLastCalledWith('cast_agent_start',{world:'local',provider:'anthropic-messages',model:'selected-claude',confirmed:true});
 expect(screen.queryByLabelText(/API key/i)).toBeNull();
});
it('does not retry uncertain start',async()=>{
 const request=vi.fn(async(a)=>a==='cast_agent_start'?undefined:info);render(<LivingCast {...props} onRequest={request}/>);
 await screen.findByText('Current goal: Consider actual events');fireEvent.change(screen.getByLabelText('Exact API model ID'),{target:{value:'selected-model'}});fireEvent.click(screen.getByRole('checkbox'));fireEvent.click(screen.getByRole('button',{name:'Start world author'}));
 await screen.findByRole('alert');expect(screen.getByRole('button',{name:'Start world author'}).disabled).toBe(true);expect(request.mock.calls.filter(([a])=>a==='cast_agent_start')).toHaveLength(1);
});
it('shows no owner controls for unopened worlds',()=>{
 const request=vi.fn();render(<LivingCast {...props} available={false} onRequest={request}/>);expect(screen.queryByRole('button',{name:'Start world author'})).toBeNull();expect(request).not.toHaveBeenCalled();
});
it('enrolls the original cast together without starting a provider implicitly',async()=>{
 const request=vi.fn(async()=>info);render(<LivingCast {...props} onRequest={request}/>);
 await screen.findByText('Current goal: Consider actual events');
 const enroll=screen.getByRole('button',{name:'Initialize and follow original cast'});
 expect(enroll.disabled).toBe(true);fireEvent.click(screen.getByRole('checkbox'));fireEvent.click(enroll);
 expect(request).toHaveBeenLastCalledWith('cast_agent_enroll_cast',{world:'local',confirmed:true});
 expect(request.mock.calls.some(([a])=>a==='cast_agent_start')).toBe(false);
});
