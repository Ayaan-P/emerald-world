import React, { useEffect, useRef, useState } from 'react';
import './world-journal.css';

export default function WorldJournal({ world, available, ready, busy, onRequest, onOpen, onBack }) {
  const [data, setData] = useState(null);
  const [place, setPlace] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const serial = useRef(0);
  const pending = useRef(false);
  const request = useRef(onRequest);
  request.current = onRequest;

  async function load(selected = place, older = false) {
    if (!world || !available || !ready || pending.current) return;
    const id = ++serial.current;
    pending.current = true; setLoading(true); setError('');
    if (!older) setData(null);
    const payload = { world: world.key, ...(selected ? { place_id: selected } : {}) };
    if (older && data) Object.assign(payload, { world_id: data.world_id, through: data.through, before: data.before });
    try {
      const value = await request.current('journal_read', payload);
      if (id !== serial.current) return;
      if (!value || !Array.isArray(value.entries) || !Array.isArray(value.places) || typeof value.world_id !== 'string'
          || !Number.isInteger(value.through) || typeof value.has_more !== 'boolean'
          || (older && (value.world_id !== data.world_id || value.through !== data.through))) throw new Error('The journal response changed. Refresh to read it again.');
      setData(older ? { ...value, entries: [...data.entries, ...value.entries] } : value);
    } catch (e) {
      if (id === serial.current) setError(e.message || 'The journal could not be read. Try refreshing.');
    } finally {
      if (id === serial.current) { pending.current = false; setLoading(false); }
    }
  }
  useEffect(() => {
    setData(null); setPlace(''); setLoading(false); setError(''); pending.current = false;
    if (available && ready) load('');
    return () => { serial.current++; pending.current = false; };
  }, [world?.key, available, ready]);

  const disabled = !ready || busy || loading;
  return <div className="interior world-journal">
    <header className="page-heading"><div><h1>World journal</h1><p>{world?.name || 'Choose a local world'}</p></div><button className="text-button" onClick={onBack}>Back to local worlds</button></header>
    <p>Recorded changes to shared places. Trainer saves and private story progress stay separate.</p>
    {!available && <section><p>Open this local host to read its journal. The game will stay closed.</p><button className="button primary" disabled={disabled || !world?.trainer} onClick={() => onOpen(world)}>Open host</button></section>}
    {available && <>
      <div className="journal-tools"><label>Place<select aria-label="Journal place" disabled={disabled} value={place} onChange={e => { const next = e.target.value; setPlace(next); load(next); }}><option value="">All recorded places</option>{data?.places.map(p => <option key={p.id} value={p.id}>{p.label}{p.active ? ' · active' : ''}</option>)}</select></label><button className="button ghost" disabled={disabled} onClick={() => load()}>Refresh journal</button></div>
      {loading && <p role="status">Reading journal…</p>}
      {error && <p role="alert">{error}</p>}
      {data && <>
        <p className="field-hint">History coverage begins after sequence {data.coverage_start_seq}. Earlier events are unknown. This view ends at sequence {data.through}; refresh to include newer changes.</p>
        {data.places_truncated && <p>Only the first 100 recorded places are listed.</p>}
        <section className="journal-now"><h2>Current shared state</h2>{data.current?.active_area && <p>Active generated area: {data.current.active_area.label}</p>}{data.current?.objects?.length ? <ul>{data.current.objects.map(o => <li key={o.id}><strong>{o.id}</strong> at ({o.x}, {o.y}): {o.text}</li>)}</ul> : <p>No current shared mechanic NPCs in this selection.</p>}<p className="field-hint">Historical dialogue below is recorded text, not proof that a player completed an event.</p></section>
        <ol className="journal-entries">{data.entries.map(entry => <li key={entry.seq}><article><div className="journal-entry-meta">Sequence {entry.seq}{typeof entry.recorded_at === 'number' && <> · <time dateTime={new Date(entry.recorded_at * 1000).toISOString()}>{new Date(entry.recorded_at * 1000).toLocaleString()}</time></>}</div><h2>{entry.title}</h2>{entry.places?.length > 0 && <p className="field-hint">{entry.places.map(id => data.places.find(p => p.id === id)?.label || id).join(' · ')}</p>}<ul>{entry.details.map((detail, i) => <li key={i}>{detail}</li>)}</ul><span className="field-hint">Committed by the world authority</span></article></li>)}</ol>
        {!data.entries.length && <p>No recorded changes for this selection.</p>}
        {data.has_more && <button className="button ghost" disabled={disabled} onClick={() => load(place, true)}>Read older changes</button>}
      </>}
    </>}
  </div>;
}
