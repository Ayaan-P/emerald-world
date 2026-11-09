import React, { useEffect, useRef, useState } from 'react';

export default function LivingCast({world, available, ready, busy, onRequest}) {
  const [info,setInfo]=useState(null),[provider,setProvider]=useState('anthropic-messages'),[model,setModel]=useState('');
  const [actor,setActor]=useState('canon_rydel'),[purpose,setPurpose]=useState(''),[confirmed,setConfirmed]=useState(false);
  const [working,setWorking]=useState(false),[error,setError]=useState(''),[uncertain,setUncertain]=useState(false);
  const pending=useRef(false), goalRequest=useRef(null);
  const [goal,setGoal]=useState(''),[goalActor,setGoalActor]=useState('canon_rydel');
  const disabled=!available || !ready || busy || working;
  async function call(action,fields={}) {
    if(pending.current)return;
    pending.current=true;setWorking(true);setError('');
    try {
      const result=await onRequest(action,{world:world.key,...fields});
      if(!result || !Array.isArray(result.actors) || !Array.isArray(result.providers) || typeof result.running!=='boolean')throw new Error('No confirmed response. Refresh status before another action.');
      if(result.running){if(result.provider!==provider || result.model!==model)setConfirmed(false);setProvider(result.provider);setModel(result.model);}
      setInfo(result);setUncertain(false);return result;
    } catch(e){setError(e.message);setUncertain(true);}
    finally{pending.current=false;setWorking(false);}
  }
  useEffect(()=>{if(available && world)call('cast_agent_read');else setInfo(null);},[available,world?.key]);
  const selected=info?.actors.find(a=>a.id===actor);
  const credentials=info?.providers.find(p=>p.id===provider)?.credential_ready;
  const mayChange=!disabled && !uncertain;
  async function submitGoal(){
    if(!goalRequest.current || goalRequest.current.goal!==goal || goalRequest.current.actor!==goalActor)goalRequest.current={goal,actor:goalActor,request_id:crypto.randomUUID()};
    const result=await call('cast_agent_goal',{...goalRequest.current,confirmed:true});
    if(result){setGoal('');goalRequest.current=null;}
  }
  function edit(set,value){set(value);setConfirmed(false);}
  return <section aria-labelledby="living-cast-heading" className="worlds-section">
    <h2 id="living-cast-heading">Living cast agents</h2>
    <p>Optional local-host authoring for the original cast. Starting contacts your selected provider and can deploy validated world changes. Provider charges may apply. No fixed story arc is installed.</p>
    <p>Public world context and configured purposes go to the selected provider. Private character memories are separate and are not started here.</p>
    {!available ? <p>Open this local host to configure agents. Friend and hosted worlds are not controlled here.</p> : <>
      <button type="button" disabled={disabled} onClick={()=>call('cast_agent_read')}>Refresh agent status</button>
      <p role="status">{info?.running ? `Running: ${info.provider} / ${info.model}` : 'World author stopped'}{info && ` · ${info.queued} queued · ${info.failed_requests} failed or interrupted`}</p>
      {info?.failed && <p>Worker stopped with an error. Inspect setup before restarting; failed work is not automatically retried.</p>}
      <label>Author provider<select value={provider} disabled={disabled || info?.running} onChange={e=>edit(setProvider,e.target.value)}><option value="anthropic-messages">Anthropic Messages (Claude)</option><option value="openai-responses">OpenAI Responses</option></select></label>
      <label>Exact API model ID<input value={model} disabled={disabled || info?.running} onChange={e=>edit(setModel,e.target.value)} placeholder="Model available to your provider account" /></label>
      <p>{credentials ? 'Host credential is available. Provider access is not yet verified.' : `Host credential unavailable. Supply ${provider==='anthropic-messages'?'ANTHROPIC_API_KEY':'OPENAI_API_KEY'} through the launcher's host environment. Never paste a key here.`}</p>
      <label><input type="checkbox" checked={confirmed} disabled={disabled} onChange={e=>setConfirmed(e.target.checked)} />I authorize this local world author to send the described context and process the requests I queue or follow.</label>
      <button type="button" disabled={!mayChange || !confirmed || !credentials || !model.trim() || info?.running} onClick={()=>call('cast_agent_start',{provider,model:model.trim(),confirmed:true})}>Start world author</button>
      <button type="button" disabled={disabled || !info?.running} onClick={()=>call('cast_agent_stop')}>Stop world author</button>
      <button type="button" disabled={!mayChange || !confirmed} onClick={()=>call('cast_agent_enroll_cast',{confirmed:true})}>Initialize and follow original cast</button>
      <p>Enrolls Rydel, Wally, Mr. Briney and Steven together. Your explicit enrollment gives missing characters a first identity-based goal and greeting request; the selected agent chooses these without inventing experiences. Later growth uses real public history. Existing records and original scripts are preserved. No fixed arc or private player history.</p>
      <label>Original character<select value={actor} disabled={disabled} onChange={e=>edit(setActor,e.target.value)}>{(info?.actors || []).map(a=><option value={a.id} key={a.id}>{a.name}</option>)}</select></label>
      <p>{selected?.authored ? `Current goal: ${selected.goal}` : 'Not authored yet. Initialize the original cast above for an identity-based first greeting, or queue a custom request using real public history. The author may wait or fail; no outcome is invented.'}</p>
      <label>Character purpose<textarea value={purpose} maxLength={1024} disabled={disabled} onChange={e=>edit(setPurpose,e.target.value)} /></label>
      <button type="button" disabled={!mayChange || !confirmed || !purpose.trim() || selected?.followed} onClick={()=>call(selected?.authored?'cast_agent_follow':'cast_agent_initialize',{actor,purpose:purpose.trim(),confirmed:true})}>{selected?.authored ? 'Follow public events for this character' : 'Queue first character request'}</button>
      {selected?.followed && <button type="button" disabled={!mayChange} onClick={()=>call('cast_agent_unfollow',{actor})}>Stop following this character</button>}
      <h3>Independent new characters</h3>
      <p>Optionally let newly admitted NPCs created by followed actors receive their own model turns. They choose plans from their actual goals and surroundings, then respond to real results. This can incur additional provider charges: at most eight author turns per new NPC and eight followed actors at once. No provider starts automatically.</p>
      <button type="button" disabled={!mayChange || (!info?.population_agents?.enabled && !confirmed)} onClick={()=>call('cast_agent_population',{enabled:!info?.population_agents?.enabled,confirmed:true})}>{info?.population_agents?.enabled ? 'Stop automatic new-character agents' : 'Enable automatic new-character agents'}</button>
      <ul aria-label="Automatic character agents">{(info?.population_agents?.characters || []).map(a=><li key={a.id}>{a.id}: {a.status}</li>)}</ul>
      <p>Only future admitted creations qualify. Stopping cancels queued managed turns and following, but cannot undo committed actions or a running provider request. A later explicit world goal takes over that character under the normal goal controls.</p>
      <h3>Build the world with an agent</h3>
      <p>Describe an outcome in your own words. The selected existing actor can compose supported world capabilities and reconsider actual results. This queues a request and follows that actor's results; it does not start the provider or promise completion. Goals go to your configured provider and resulting world changes can be public.</p>
      <label>World goal actor<select value={goalActor} disabled={disabled} onChange={e=>setGoalActor(e.target.value)}>{(info?.goal_actors || []).map(a=><option value={a.id} key={a.id}>{a.name}</option>)}</select></label>
      <label>World-building goal<textarea value={goal} maxLength={1024} disabled={disabled} onChange={e=>setGoal(e.target.value)} placeholder="Describe the place, inhabitants or changes you want" /></label>
      <button type="button" disabled={!mayChange || !confirmed || !goal.trim() || !info?.goal_actors?.some(a=>a.id===goalActor)} onClick={submitGoal}>Queue world-building goal</button>
      {info?.goal_actors?.find(a=>a.id===goalActor)?.followed && <button type="button" disabled={!mayChange} onClick={()=>call('cast_agent_unfollow',{actor:goalActor})}>Stop world goal follow-up</button>}
      <ul aria-label="World goal requests">{(info?.goals || []).map(g=><li key={g.id}>{g.actor}: {g.status} author request. World actions have separate receipts.</li>)}</ul>
      <p>Stop following the selected character to stop future reaction turns. Already committed plans/actions remain world state; stopping the provider does not undo them.</p>
      <p>After the first record is authored, refresh and follow it for future events. Stopping preserves queued work. Closing or disconnecting this host stops its worker. No private reflection worker is enabled.</p>
      {error && <p role="alert">{error}</p>}
    </>}
  </section>;
}
