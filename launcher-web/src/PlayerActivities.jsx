import React, { useEffect, useRef, useState } from 'react';

export default function PlayerActivities({ state, ready, busy, onRequest, onAdventure }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const serial = useRef(0);
  const request = useRef(onRequest); request.current = onRequest;
  const world = state.connected ? state.world_key : null;
  async function load() {
    if (!world || !ready || busy) return;
    const id = ++serial.current; setLoading(true); setData(null); setError('');
    try {
      const value = await request.current('player_activity_read', { world });
      if (id !== serial.current) return;
      if (!value || value.trainer !== state.trainer || !Array.isArray(value.recap) || !Array.isArray(value.offers)) throw new Error('Your activity response changed. Reconnect as your trainer and refresh.');
      setData(value);
    } catch (e) { if (id === serial.current) setError(e.message || 'Your activities could not be read. Refresh to try again.'); }
    finally { if (id === serial.current) setLoading(false); }
  }
  useEffect(() => { setData(null); setError(''); setLoading(false); load(); return () => { serial.current++; }; }, [world, state.trainer, ready]);
  const survey = data?.survey;
  const next = survey?.active && survey?.in_scope && survey?.next_objective?.revision === survey?.revision ? survey.next_objective : null;
  return <div className="interior narrow">
    <header className="page-heading"><div><h1>Your objectives & recap</h1><p>Only the trainer connected in this launcher can read their private activity.</p></div></header>
    <button className="button ghost" disabled={!world || !ready || busy || loading} onClick={load}>Refresh activities</button>
    {!world && <p>Connect as your trainer to see your own activities. Choose a world from Play first.</p>}
    {loading && <p role="status">Reading your activities…</p>}{error && <p role="alert">{error}</p>}
    <section className="settings-card"><div><h2>Private landmark survey</h2>
      {!survey && <p>No private survey is shown. Enter a registered route in the native game and opt in with its exploration controls. Merely opening this page never starts a survey.</p>}
      {survey && <><p>{survey.visited.length} of {survey.landmarks.length} landmarks discovered</p><p>{survey.active ? 'Active survey' : 'Paused survey'}{!survey.in_scope && '. Return to the same map revision to continue.'}</p>{next ? <p>Next clearing: {next.id} near ({next.x}, {next.y}). Reach its center in the game.</p> : survey.complete ? <p>The authority has recorded every clearing in this survey.</p> : <p>Refresh in your active survey destination for the authority’s next clearing.</p>}</>}
      <p className="field-hint">Discoveries remain private. Public history requires explicit share confirmation in the game beside a discovered landmark. That persistent record includes its name, coordinates and map revision, not your name or private trail. Agents and other players can read shared records.</p>
    </div></section>
    {data && <>
      <section className="settings-card"><div><h2>Your guild goals</h2>{data.guild ? <><h3>{data.guild.name}</h3>{data.guild.goals.length ? <ul>{data.guild.goals.map(goal => <li key={goal.kind}>{goal.kind}: visit {goal.destination}. {goal.credited === null ? '' : `${goal.credited} of `}{goal.target} trainers. {goal.complete ? 'Recorded complete.' : 'Active.'}</li>)}</ul> : <p>No current guild goal.</p>}<p>Use Guilds in the WORLD menu to coordinate. Presence is client-reported, not independently simulated travel.</p></> : <p>No guild membership recorded for your trainer. Open Guilds in the WORLD menu to join or create one.</p>}</div></section>
      <section className="settings-card"><div><h2>Resident offers</h2>{data.offers.length ? <ul>{data.offers.map(offer => <li key={offer.resident}><strong>{offer.name}</strong>: {offer.target} guild trainers visit {offer.destination}. Speak to this resident in the game. The guild leader must explicitly accept, with guild chronicle consent enabled.</li>)}</ul> : <p>No active resident expedition offers recorded.</p>}<p>Available offers are not accepted objectives or proof of completion. Optional battles stay in the game and do not count as a landmark discovery.</p></div></section>
      <section className="settings-card"><div><h2>Public world recap</h2><p>Shared authority records, not your private quest log. History coverage begins after sequence {data.coverage_start_seq}.</p>{data.recap.length ? <ol>{data.recap.map(entry => <li key={entry.seq}><strong>{entry.title}</strong><ul>{entry.details.map((detail,i) => <li key={i}>{detail}</li>)}</ul></li>)}</ol> : <p>No public world changes recorded.</p>}</div></section>
    </>}
    <section className="settings-card"><div><h2>Looking for a first adventure?</h2><p>Review Lantern Trail with an owner before entering. No automatic generation, publication or travel happens here.</p><button className="button primary" onClick={onAdventure}>First adventure</button></div></section>
  </div>;
}
