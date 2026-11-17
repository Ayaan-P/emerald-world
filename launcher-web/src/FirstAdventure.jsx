import React, { useEffect, useRef, useState } from 'react';

// Only human-readable guide strings supplied by the adventure compiler are shown.
function Guide({ value }) {
  if (typeof value === 'string') return <p>{value}</p>;
  if (Array.isArray(value)) return <ul>{value.filter(line => typeof line === 'string').map((line,i) => <li key={i}>{line}</li>)}</ul>;
  if (value && typeof value === 'object') return <>{Object.entries(value).map(([key, item]) => <section key={key}><h3>{key.replaceAll('_',' ')}</h3><Guide value={item} /></section>)}</>;
  return null;
}

export default function FirstAdventure({ state, ready, busy, onRequest, onOpen, onHostedWorlds }) {
  const worlds = [...(state.local_worlds || []), ...(state.hosting?.worlds || []).map(w => ({...w,key:`hosted-${w.id}`,hosted:true}))];
  const [key,setKey] = useState(state.local_worlds?.[0]?.key || worlds[0]?.key || '');
  const world = worlds.find(w => w.key === key);
  const available = Boolean(world?.hosted || (state.local_host && state.world_key === key));
  const [data,setData] = useState(null), [review,setReview] = useState(null), [confirmed,setConfirmed] = useState(false);
  const [loading,setLoading] = useState(false), [error,setError] = useState('');
  const request = useRef(onRequest); request.current = onRequest;
  const serial = useRef(0), pending = useRef(false);
  async function run(action) {
    if (!ready || busy || !available || pending.current) return;
    const id = ++serial.current; pending.current = true; setLoading(true); setError('');
    const payload = action === 'adventure_preview' ? { world:key, adventure:'lantern-trail' } : action === 'adventure_apply' ? {world:key,token:review.token,confirmed:true} : {world:key};
    try {
      const result = await request.current(action,payload);
      if (id !== serial.current) return;
      if (!result || result === false) throw new Error('Adventure request could not complete. Refresh before trying again.');
      if (action === 'adventure_preview') {
        if (typeof result.token !== 'string' || !result.token) throw new Error('The review expired. Review the adventure again.');
        setReview(result); setConfirmed(false);
      } else { setData(result); setReview(null); setConfirmed(false); }
    } catch (e) { if (id === serial.current) { setError(e.message || 'Adventure request failed.'); setReview(null); setConfirmed(false); } }
    finally { if (id === serial.current) { pending.current = false; setLoading(false); } }
  }
  useEffect(() => {
    setData(null); setReview(null); setConfirmed(false); setError(''); setLoading(false); pending.current=false;
    if (available && ready) run('adventure_read');
    return () => { serial.current++; pending.current=false; };
  },[key, available, ready]);
  const disabled = !ready || busy || loading;
  return <div className="interior narrow"><header className="page-heading"><div><h1>First adventure</h1><p>Lantern Trail</p></div></header>
    <p>A named resident-led adventure supplied by the world content compiler. Review its entry instructions before installing. No model call is needed.</p>
    <section className="settings-card"><div><h2>Before you begin</h2><p>Requires the Expansion client and a durable world with area archiving. Start with a local world you own. Open its host without launching a game, then review the adventure. Installation changes shared world content and requires a separate confirmation. Save and close any game before applying.</p><p>After installation, use its entry guide in the native WORLD menu. Your trainer needs a starter and field control. The adventure does not warp you, grant badges, or mark objectives complete. Battles are optional.</p><p>Hosted owners can use the same review when their service provides adventure management. Existing remote generation remains available in Explore. Joining a hosted world as a player does not grant owner access.</p></div></section>
    <label className="field-label">Adventure world<select className="text-input" value={key} disabled={disabled} onChange={e=>setKey(e.target.value)}><option value="">Choose an owned world</option>{worlds.map(w=><option key={w.key} value={w.key}>{w.name}{w.hosted?' · Hosted owner':' · Local owner'}</option>)}</select></label>
    {!world && <p>Create a local world from Play, or load your owned worlds from Hosted worlds.</p>}
    {world && !available && <><p>Open this local host first. The game stays closed.</p><button className="button primary" disabled={disabled || !world.trainer} onClick={()=>onOpen(world)}>Open adventure host</button></>}
    <button className="text-button" disabled={disabled} onClick={onHostedWorlds}>Hosted worlds</button>
    {loading && <p role="status">Reading adventure…</p>}{error && <p role="alert">{error}</p>}
    {available && <button className="button ghost" disabled={disabled} onClick={()=>run('adventure_read')}>Refresh adventure</button>}
    {data && !review && <section className="settings-card"><div><h2>Lantern Trail</h2><Guide value={data.guide || data.adventures?.find(a => a.id === 'lantern-trail')?.guide} /><Guide value={data.prerequisites} />{data.saved && <p role="status">Adventure installation recorded by the authority. Follow the entry guide to begin playing.</p>}<button className="button primary" disabled={disabled} onClick={()=>run('adventure_preview')}>Review Lantern Trail</button></div></section>}
    {review && <section className="settings-card"><div><h2>Review {review.label || 'Lantern Trail'}</h2><Guide value={review.guide} /><Guide value={review.validation} /><Guide value={review.prerequisites} /><p>This installs shared geography and residents. Existing geography remains archived. Nothing is published from your private survey and no game is launched.</p><label><input type="checkbox" checked={confirmed} disabled={disabled} onChange={e=>setConfirmed(e.target.checked)} /> I have saved and closed the game and want to install this reviewed shared content.</label><button className="button primary" disabled={disabled || !confirmed} onClick={()=>run('adventure_apply')}>Install reviewed adventure</button></div></section>}
    <p className="field-hint">Your survey stays private until explicit share confirmation beside a discovered landmark in the game. Sharing writes a persistent public record that agents and other players may read. Installing or refreshing never consents to sharing for you.</p>
  </div>;
}
