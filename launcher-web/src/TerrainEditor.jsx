import React, { useEffect, useRef, useState } from 'react';
import { floorPath } from './AreaLibrary';
import './terrain-editor.css';

const kinds = ['grass', 'tall_grass', 'water'];
const names = { grass: 'Grass', tall_grass: 'Tall grass', water: 'Water', original: 'Original' };
const key = tile => `${tile.x},${tile.y}`;
const canonical = tiles => [...tiles].sort((a, b) => a.x - b.x || a.y - b.y);
const same = (a, b) => JSON.stringify(canonical(a)) === JSON.stringify(canonical(b));
const empty = () => {};
export function validTerrain(value, world, identity) {
  return value && value.world === world && value.identity === identity
    && Number.isInteger(value.revision) && value.revision >= 0 && value.revision <= 2147483647
    && Number.isInteger(value.players) && value.players >= 0
    && Array.isArray(value.rows) && value.rows.length === 63 && value.rows.every(row => typeof row === 'string' && /^[.#]{63}$/.test(row))
    && Array.isArray(value.characters) && value.characters.length >= 1 && value.characters.length <= 3
    && value.characters.every(tile => tile && Number.isInteger(tile.x) && Number.isInteger(tile.y) && tile.x > 0 && tile.x < 62 && tile.y > 0 && tile.y < 62)
    && Array.isArray(value.tiles) && value.tiles.length <= 512
    && value.tiles.every(tile => tile && Number.isInteger(tile.x) && Number.isInteger(tile.y) && tile.x > 0 && tile.x < 62 && tile.y > 0 && tile.y < 62 && kinds.includes(tile.terrain))
    && new Set(value.tiles.map(key)).size === value.tiles.length;
}
export function terrainDifference(before, after) {
  const old = new Map(before.map(tile => [key(tile), tile.terrain]));
  const next = new Map(after.map(tile => [key(tile), tile.terrain]));
  return new Set([...old.keys(), ...next.keys()].filter(cell => old.get(cell) !== next.get(cell))).size;
}

export default function TerrainEditor({ world, area, available, ready, busy, onRequest, onBack, onDirtyChange = empty }) {
  const [base, setBase] = useState(null);
  const [tiles, setTiles] = useState([]);
  const [brush, setBrush] = useState('grass');
  const [cursor, setCursor] = useState([3, 3]);
  const [zoom, setZoom] = useState(1);
  const [undo, setUndo] = useState([]);
  const [review, setReview] = useState(null);
  const [uncertain, setUncertain] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [operation, setOperation] = useState('');
  const request = useRef(0);
  const pending = useRef(false);
  const title = useRef(null);
  const viewport = useRef(null);
  const dirty = Boolean(base && !same(base.tiles, tiles));
  const blocked = busy || loading || !ready || !available || uncertain;
  const frozen = blocked || Boolean(review);
  useEffect(() => { load(); return () => { request.current++; }; }, [world, area.identity]);
  useEffect(() => { onDirtyChange(dirty || uncertain); }, [dirty, uncertain, onDirtyChange]);
  useEffect(() => () => onDirtyChange(false), [onDirtyChange]);
  useEffect(() => {
    if (!dirty && !uncertain) return;
    const guard = event => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', guard);
    return () => window.removeEventListener('beforeunload', guard);
  }, [dirty, uncertain]);
  useEffect(() => { if (review) title.current?.focus(); }, [review]);

  async function call(action, payload) {
    if (pending.current) return null;
    pending.current = true; setLoading(true); setError(''); setNotice('');
    setOperation(action === 'terrain_apply' ? 'Saving terrain…' : action === 'terrain_review' ? 'Checking draft…' : 'Reading terrain…');
    const serial = ++request.current;
    try {
      const value = await onRequest(action, { world, identity: area.identity, ...payload });
      if (serial !== request.current) return null;
      if (!validTerrain(value, world, area.identity)) throw new Error('Terrain response unavailable.');
      return value;
    } catch (reason) {
      if (serial === request.current) setError(reason?.message || 'Terrain could not be read or the save confirmed.');
      return null;
    } finally { if (serial === request.current) { pending.current = false; setLoading(false); } }
  }
  async function load() {
    const value = await call('terrain_read');
    if (value) { setBase(value); setTiles(value.tiles); setUndo([]); setReview(null); setUncertain(false); }
  }
  function draft(next) {
    if (frozen) return;
    if (next.length > 512) { setError('The overlay can hold 512 cells. Restore a cell before adding another.'); return; }
    setUndo(old => [...old.slice(-19), tiles]); setTiles(canonical(next)); setError(''); setNotice('');
  }
  function paint(x, y) {
    if (frozen || !base) return;
    setCursor([x, y]);
    if (x <= 0 || y <= 0 || x >= 62 || y >= 62 || ['1,1', '61,60', '61,61'].includes(`${x},${y}`)
        || base.characters.some(npc => npc.x === x && npc.y === y)) {
      setError('This cell is protected.'); return;
    }
    const next = tiles.filter(tile => tile.x !== x || tile.y !== y);
    if (brush !== 'original') next.push({ x, y, terrain: brush });
    if (!same(tiles, next)) draft(next);
  }
  function keyboard(event) {
    const moves = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
    if (moves[event.key]) {
      event.preventDefault(); const [dx, dy] = moves[event.key];
      setCursor(([x, y]) => [Math.max(0, Math.min(62, x + dx)), Math.max(0, Math.min(62, y + dy))]);
    } else if (event.key === ' ' || event.key === 'Enter') { event.preventDefault(); paint(...cursor); }
  }
  async function prepare() {
    if (blocked || !dirty || pending.current) return;
    setReview(null);
    const payload = { expected_revision: base.revision, tiles: canonical(tiles) };
    const value = await call('terrain_review', payload);
    if (!value) return;
    if (value.revision !== base.revision || !validTerrain({ ...value, tiles: value.proposed_tiles }, world, area.identity) || !same(value.proposed_tiles, payload.tiles) || !same(value.tiles, base.tiles)) {
      setError('Terrain changed. Reload before reviewing a new draft.'); return;
    }
    setBase(value); setReview(payload);
  }
  async function apply() {
    if (blocked || !review || base.players > 0 || pending.current) return;
    const value = await call('terrain_apply', { ...review, confirmed: true });
    if (value?.saved === true && value.revision === review.expected_revision + 1 && same(value.tiles, review.tiles)) {
      setBase(value); setTiles(value.tiles); setUndo([]); setReview(null);
      setNotice(`Terrain saved at revision ${value.revision}. Rejoin the world to load it. In-game application has not been checked.`);
    } else { setReview(null); setUncertain(true); }
  }
  return <div className="interior terrain-page">
    <button className="back" disabled={busy || loading} onClick={onBack}>Back to areas</button>
    <header className="page-heading"><div><h1>Edit terrain</h1><p>{area.label}</p></div>{base && <span>Revision {base.revision}</span>}</header>
    <p className="field-hint">Shared 63 × 63 area. Save and close connected games before applying. Changes stay in this world.</p>
    {!available && <p role="alert">This is no longer the selected active local area. Return to the library.</p>}
    {error && <p role="alert" className="terrain-warning">{error}</p>}
    {notice && <p role="status" className="terrain-warning">{notice}</p>}
    {uncertain && <p role="alert">The save was not confirmed. Reload to check the stored terrain before editing again. Nothing retries automatically.</p>}
    <div className="terrain-actions"><button className="text-button" disabled={busy || loading || !ready || !available} onClick={load}>{dirty || uncertain ? 'Discard draft & reload' : 'Refresh terrain'}</button>{loading && <span role="status">{operation}</span>}</div>
    {base && <>
      <div className="terrain-tools" role="group" aria-label="Terrain brushes">{[...kinds, 'original'].map(kind => <button key={kind} className="button ghost" aria-pressed={brush === kind} disabled={frozen} onClick={() => setBrush(kind)}><i className={`terrain-swatch terrain-${kind}`} />{names[kind]}</button>)}</div>
      <div className="area-map-toolbar"><span>{tiles.length} / 512 overrides · {terrainDifference(base.tiles, tiles)} changed cells</span><div role="group" aria-label="Terrain zoom">{[1, 2, 4].map(value => <button key={value} className="text-button" aria-pressed={zoom === value} onClick={() => { setZoom(value); if (value === 1 && viewport.current) { viewport.current.scrollLeft = 0; viewport.current.scrollTop = 0; } }}>{value === 1 ? 'Fit' : `${value}×`}</button>)}</div></div>
      <div className="area-map-viewport terrain-viewport" ref={viewport} role="grid" aria-rowcount={63} aria-colcount={63} aria-label="Terrain map" aria-describedby="terrain-input-help" aria-activedescendant="terrain-cursor" tabIndex={0} onKeyDown={keyboard}>
        <div className="area-map-canvas"><svg aria-hidden="true" viewBox="0 0 63 63" style={{ width: `${zoom * 100}%` }} onClick={event => { const box = event.currentTarget.getBoundingClientRect(); if (box.width > 0 && box.height > 0) paint(Math.min(62, Math.max(0, Math.floor((event.clientX - box.left) * 63 / box.width))), Math.min(62, Math.max(0, Math.floor((event.clientY - box.top) * 63 / box.height)))); }}>
          <rect width="63" height="63" className="map-blocked" /><path d={floorPath(base.rows)} className="map-floor" shapeRendering="crispEdges" />
          {tiles.map(tile => <rect key={key(tile)} x={tile.x} y={tile.y} width="1" height="1" className={`terrain-${tile.terrain}`} />)}
          <circle cx="1.5" cy="1.5" r="0.8" className="map-entrance" /><rect x="61" y="61" width="1" height="1" className="map-exit" />
          {base.characters.map(npc => <path key={key(npc)} d={`M${npc.x + .5} ${npc.y}l.5 .5-.5 .5-.5-.5z`} className="map-character" />)}
          <rect x={cursor[0]} y={cursor[1]} width="1" height="1" className="terrain-cursor" />
        </svg></div><span role="row" aria-rowindex={cursor[1] + 1} className="visually-hidden"><span role="gridcell" aria-colindex={cursor[0] + 1} id="terrain-cursor">Cell {cursor.join(', ')}. {names[tiles.find(tile => key(tile) === cursor.join(','))?.terrain] || (base.rows[cursor[1]][cursor[0]] === '.' ? 'Original floor' : 'Original blocked tile')}.</span></span>
      </div>
      <p id="terrain-input-help" className="field-hint">Click to paint. Keyboard: arrows select a cell, Space paints. Water blocks movement. Original removes an override.</p>
      <div className="terrain-actions"><button className="button ghost" disabled={frozen || !undo.length} onClick={() => { setTiles(undo.at(-1)); setUndo(old => old.slice(0, -1)); setError(''); }}>Undo</button><button className="text-button" disabled={frozen || !tiles.length} onClick={() => draft([])}>Restore base layout</button><span>{base.players} connected {base.players === 1 ? 'player' : 'players'}</span></div>
      <details className="terrain-json"><summary>Draft overlay JSON</summary><p className="field-hint">Existing owner CLI format for geometry replacement. This draft is not applied.</p><textarea className="text-input" aria-label="Draft overlay JSON" readOnly value={JSON.stringify(canonical(tiles), null, 2)} /></details>
      {review ? <section className="terrain-review"><h2 ref={title} tabIndex={-1}>Apply terrain changes?</h2><p>{terrainDifference(base.tiles, review.tiles)} changed cells · {review.tiles.length} stored overrides. Replaces revision {review.expected_revision}.</p><p className="field-hint">Connectivity and protected cells checked. Matching geometry-capable clients are required. Nobody is disconnected automatically.</p>{base.players > 0 && <p role="status">Close connected games, then refresh this review.</p>}<div className="terrain-actions"><button className="button ghost" disabled={busy || loading} onClick={() => setReview(null)}>Keep editing</button><button className="text-button" disabled={blocked} onClick={prepare}>Refresh review</button><button className="button primary" disabled={blocked || base.players > 0} onClick={apply}>Apply terrain</button></div></section>
        : <button className="button primary" disabled={blocked || !dirty || base.revision === 2147483647} onClick={prepare}>Review terrain</button>}
    </>}
  </div>;
}
