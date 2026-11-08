import React, { useEffect, useRef, useState } from 'react';
import './area-library.css';

const labels = { cave: 'Cave', wilds: 'Outdoor wilds', guided_wilds: 'Outdoor wilds · Guide', cast_wilds: 'Outdoor wilds · Characters', event_wilds: 'Interactive adventure', xl_wilds: 'XL outdoor world' };
const filters = ['All areas', 'Caves', 'Outdoors', 'Adventures'];
const previewError = 'Map preview unavailable. Try again or check the local host. Nothing was changed.';

// Keep a damaged or mismatched bridge response out of SVG and roster rendering.
export function validPreview(value, world, identity) {
  if (!value || value.world !== world || value.identity !== identity || value.layout !== 'saved_base'
      || ![31, 63, 127].includes(value.side) || !Array.isArray(value.rows) || value.rows.length !== value.side
      || !value.rows.every(row => typeof row === 'string' && row.length === value.side && /^[.#]+$/.test(row))) return false;
  const point = xy => Array.isArray(xy) && xy.length === 2 && xy.every(n => Number.isInteger(n) && n >= 0 && n < value.side);
  return point(value.entrance) && point(value.exit) && Array.isArray(value.characters) && value.characters.length <= 3
    && value.characters.every(npc => npc && Number.isInteger(npc.number) && npc.number >= 1 && npc.number <= 3 && point([npc.x, npc.y]))
    && Array.isArray(value.wildlife) && value.wildlife.length <= 12
    && value.wildlife.every(mon => mon && typeof mon.name === 'string' && mon.name.length > 0 && mon.name.length <= 80
      && Number.isInteger(mon.species) && mon.species > 0 && mon.species <= 65535 && Array.isArray(mon.levels) && mon.levels.length > 0 && mon.levels.length <= 12
      && mon.levels.every(level => Number.isInteger(level) && level >= 1 && level <= 100));
}

// One path of horizontal runs keeps even a 127-square layout small in the DOM.
export function floorPath(rows) {
  return rows.flatMap((row, y) => [...row.matchAll(/\.+/g)].map(run => `M${run.index} ${y}h${run[0].length}v1h-${run[0].length}z`)).join('');
}

function MapPreview({ area, data }) {
  const [zoom, setZoom] = useState(1);
  const viewport = useRef(null);
  function zoomTo(next) {
    setZoom(next);
    if (next === 1 && viewport.current) { viewport.current.scrollLeft = 0; viewport.current.scrollTop = 0; }
  }
  return <>
    <div className="area-map-toolbar"><span>{data.side} × {data.side} tiles</span><div role="group" aria-label="Map zoom">
      {[1, 2, 4].map(value => <button key={value} className="text-button" aria-pressed={zoom === value} onClick={() => zoomTo(value)}>{value === 1 ? 'Fit' : `${value}×`}</button>)}
    </div></div>
    <div className={`area-map-viewport${area.kind === 'cave' ? ' cave-map' : ''}`} ref={viewport} tabIndex={0} role="region" aria-label="Scrollable saved map">
      <div className="area-map-canvas"><svg role="img" aria-label={`Saved layout of ${area.label}`} viewBox={`0 0 ${data.side} ${data.side}`} style={{ width: `${zoom * 100}%` }}>
        <title>{area.label}. Entrance at {data.entrance.join(', ')}, exit at {data.exit.join(', ')}.</title>
        <rect width={data.side} height={data.side} className="map-blocked" />
        <path d={floorPath(data.rows)} className="map-floor" shapeRendering="crispEdges" />
        <circle cx={data.entrance[0] + 0.5} cy={data.entrance[1] + 0.5} r="1.1" className="map-entrance" />
        <rect x={data.exit[0] - 0.5} y={data.exit[1] - 0.5} width="2" height="2" className="map-exit" />
        {data.characters.map(npc => <path key={npc.number} d={`M${npc.x + 0.5} ${npc.y - 0.8}l1.3 1.3-1.3 1.3-1.3-1.3z`} className="map-character"><title>Character {npc.number} at {npc.x}, {npc.y}</title></path>)}
      </svg></div>
    </div>
    <ul className={`area-map-key${area.kind === 'cave' ? ' cave-map-key' : ''}`} aria-label="Map legend"><li><i className="key-entrance" />Entrance</li><li><i className="key-exit" />Exit</li><li><i className="key-floor" />Floor</li><li><i className="key-blocked" />Blocked</li>{data.characters.length > 0 && <li><i className="key-character" />Characters · {data.characters.length}</li>}</ul>
    <p className="field-hint">Saved base layout. Live terrain and player positions are not shown.</p>
    {data.characters.length > 0 && <p className="field-hint">In game: face a character and press A (default Z).</p>}
    {data.wildlife.length > 0 ? <details className="area-wildlife"><summary>Wildlife · {data.wildlife.length} species</summary>
      <ul>{data.wildlife.map(mon => <li key={mon.species}><span>{mon.name}</span><span>Lv. {mon.levels.join(', ')}</span></li>)}</ul>
      <p className="field-hint">Stored roster · {data.wildlife_cohort === 'expansion-native' ? 'Expansion' : 'Vanilla'} species. Requires a matching game build.</p>
    </details> : <p className="field-hint">No custom wildlife roster. Encounters follow the game’s area defaults.</p>}
  </>;
}

export default function AreaLibrary({ world, areas, error, disabled, occupied, pending, onInspect, onReview, onEditTerrain }) {
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('All areas');
  const [limit, setLimit] = useState(24);
  const [preview, setPreview] = useState(null);
  const request = useRef(0);
  const previewPanel = useRef(null);
  const opener = useRef(null);
  const restoreFocus = useRef(false);
  const libraryPanel = useRef(null);
  useEffect(() => () => { request.current += 1; }, []);
  const selected = areas.find(area => area.identity === preview?.identity);
  useEffect(() => {
    if (preview && !selected) { request.current += 1; setPreview(null); }
  }, [selected, preview]);
  useEffect(() => {
    if (preview?.identity) previewPanel.current?.focus();
    else if (restoreFocus.current) {
      restoreFocus.current = false;
      if (opener.current?.isConnected && !opener.current.disabled) opener.current.focus();
      else libraryPanel.current?.focus();
    }
  }, [preview?.identity]);

  async function inspect(area) {
    if (disabled || pending || !onInspect || preview?.loading) return;
    const serial = ++request.current;
    opener.current = document.activeElement;
    setPreview({ identity: area.identity, loading: true });
    try {
      const data = await onInspect({ world, identity: area.identity });
      if (request.current === serial) {
        const valid = validPreview(data, world, area.identity);
        setPreview({ identity: area.identity, data: valid ? data : null, error: valid ? '' : previewError });
      }
    } catch {
      if (request.current === serial) setPreview({ identity: area.identity, error: previewError });
    }
  }
  function close() {
    request.current += 1;
    restoreFocus.current = true;
    setPreview(null);
  }
  function review(area) {
    onReview({ type: 'activate', world, identity: area.identity, label: area.label, adventure: area.kind === 'event_wilds' });
  }
  const matches = areas.filter(area => area.label.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase())
    && (filter === 'All areas' || (filter === 'Caves' && area.kind === 'cave')
      || (filter === 'Outdoors' && ['wilds', 'guided_wilds', 'cast_wilds', 'xl_wilds'].includes(area.kind))
      || (filter === 'Adventures' && area.kind === 'event_wilds')));
  const visible = matches.slice(0, limit);
  const searching = query.trim() || filter !== 'All areas';
  return <section className="area-library" ref={libraryPanel} tabIndex={-1} aria-label="Area library">
    <div className="area-library-heading"><h3>Area library</h3><span>{areas.length} saved</span></div>
    <p className="field-hint">One active area per world. Previews and saved areas make no model call.</p>
    {error && <p role="alert">{error}</p>}
    {areas.length > 0 && <div className="area-library-controls">
      <label className="area-search"><span className="field-label">Find an area</span><input type="search" className="text-input" value={query} maxLength={80} onChange={event => { setQuery(event.target.value); setLimit(24); }} placeholder="Search by name" /></label>
      <div role="group" aria-label="Area types" className="area-filters">{filters.map(value => <button key={value} className="text-button" aria-pressed={filter === value} onClick={() => { setFilter(value); setLimit(24); }}>{value}</button>)}</div>
    </div>}
    {preview && selected && <section className="area-preview" ref={previewPanel} tabIndex={-1} aria-label="Map preview" onKeyDown={event => { if (event.key === 'Escape') { event.stopPropagation(); close(); } }}>
      <header><div><span className="mode-label">Map preview</span><h3>{selected.label}</h3></div><button className="text-button" onClick={close}>Close preview</button></header>
      {preview.loading && <p role="status">Loading saved layout…</p>}
      {preview.error && <><p role="alert">{preview.error}</p><button className="button small ghost" disabled={disabled || Boolean(pending)} onClick={() => inspect(selected)}>Retry preview</button></>}
      {preview.data && <MapPreview key={preview.identity} area={selected} data={preview.data} />}
      <footer><span>{selected.active ? 'Active now' : labels[selected.kind] || 'Generated area'}</span>{!selected.active && <button className="button small primary" disabled={disabled || occupied || Boolean(pending)} onClick={() => review(selected)}>Review activation</button>}</footer>
    </section>}
    {searching && !matches.length && <p className="muted-copy" role="status">No matching areas. <button className="text-button" onClick={() => { setQuery(''); setFilter('All areas'); setLimit(24); }}>Clear filters</button></p>}
    {[false, true].map(adventure => {
      const group = visible.filter(area => (area.kind === 'event_wilds') === adventure);
      if (!group.length && (searching || matches.some(area => (area.kind === 'event_wilds') === adventure))) return null;
      return <section className={`area-library-group${adventure ? ' published-adventures' : ' generated-area-library'}`} key={String(adventure)} aria-label={adventure ? 'Published adventures' : 'Saved exploration areas'}>
        <h4>{adventure ? 'Published adventures' : 'Saved exploration areas'}</h4>
        {adventure && <p className="field-hint">Published by a connected director. Conversation state resets on a new visit; opening one does not start a director.</p>}
        {!group.length && <p className="muted-copy">{error ? 'The archive could not be checked.' : adventure ? 'No published adventures.' : 'No saved areas.'}</p>}
        <div className="area-library-grid">{group.map(area => <article key={area.identity} className={`area-library-card${area.active ? ' is-active' : ''}`}>
          <span className="area-card-type">{labels[area.kind] || 'Generated area'}</span><h3>{area.label}</h3>
          {area.active && <span className="area-active-badge">Active now</span>}
          <div className="area-card-actions">{area.active && area.kind === 'event_wilds' && onEditTerrain && <button className="button small ghost" disabled={disabled || Boolean(pending)} onClick={() => onEditTerrain(area)}>Edit terrain</button>}<button className="button small ghost" disabled={disabled || Boolean(pending) || preview?.loading || !onInspect} aria-label={`Preview map: ${area.label}`} onClick={() => inspect(area)}>Preview map</button>
            {!area.active && <button className="text-button" disabled={disabled || occupied || Boolean(pending)} onClick={() => review(area)}>{adventure ? 'Open adventure' : 'Use this area'}</button>}</div>
        </article>)}</div>
      </section>;
    })}
    {matches.length > limit && <button className="button small ghost" onClick={() => setLimit(value => value + 24)}>Show more areas ({matches.length - limit})</button>}
  </section>;
}
