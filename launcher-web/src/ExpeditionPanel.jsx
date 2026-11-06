import React, { useEffect, useRef, useState } from 'react';

const areaTypes = {
  xl_wilds: { label: 'XL outdoor world (127 × 127)', capability: 'xl_wilds_authoring', description: 'A shared outdoor world with four times the terrain of standard wilds. Existing Hoenn art and encounters; no generated characters, story graphs or editable overlays in this XL multiplayer mode. Matching RC8 clients required.' },
  cave: { label: 'Cave with custom wildlife', capability: 'cave_authoring', description: 'Caves use existing art with a model-selected biome and custom wildlife roster.' },
  wilds: { label: 'Outdoor wilds', capability: 'wilds_authoring', description: 'Outdoor areas use existing Hoenn art, blocked water, tall grass and Route 101 encounters, not custom outdoor wildlife.' },
  guided_wilds: { label: 'Outdoor wilds with a guide', capability: 'guided_wilds_authoring', description: 'Outdoor wilds with one guide and short model-authored dialogue. Talk to the guide in the game. Dialogue is fixed text, not a live conversation.' },
  cast_wilds: { label: 'Outdoor wilds with characters', capability: 'cast_wilds_authoring', description: 'Outdoor wilds with one to three characters and short model-authored dialogue. Talk to them in the game. Dialogue is fixed text, not a live conversation.' },
};
const areaLabels = { ...Object.fromEntries(Object.entries(areaTypes).map(([key, type]) => [key, type.label])), event_wilds: 'Interactive adventure' };

export default function ExpeditionPanel({ state, ready, busy, onOpen, onAuthor, onActivate }) {
  const [name, setName] = useState('');
  const [trainer, setTrainer] = useState('Player');
  const [theme, setTheme] = useState('');
  const [kind, setKind] = useState('cave');
  const [confirmation, setConfirmation] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState('');
  const submittingRef = useRef(false);
  useEffect(() => { setConfirmation(null); setResult(''); }, [state.world_key, state.local_host]);
  const disabled = busy || submitting || !ready;
  const validTrainer = /^[A-Za-z0-9_-]{1,24}$/.test(trainer);
  const themeBytes = new TextEncoder().encode(theme).length;
  const localWorlds = state.local_worlds || [];
  const current = localWorlds.find(world => world.key === state.world_key);
  const areas = [...(state.generated_areas || [])].sort((a, b) => Number(b.active) - Number(a.active));
  const adventures = areas.filter(area => area.kind === 'event_wilds');
  const library = areas.filter(area => area.kind !== 'event_wilds');
  const pending = confirmation?.world === state.world_key ? confirmation : null;
  const canAuthor = state[areaTypes[kind].capability];

  function review(value) {
    if (disabled || pending || submittingRef.current) return;
    setResult('');
    setConfirmation(value);
  }

  async function confirm() {
    if (disabled || !pending || submittingRef.current) return;
    submittingRef.current = true;
    setSubmitting(true);
    setResult('');
    try {
      const succeeded = pending.type === 'activate'
        ? await onActivate({ world: pending.world, identity: pending.identity, confirmed: true })
        : await onAuthor({ world: pending.world, kind: pending.kind, theme: pending.theme, confirmed: true });
      if (succeeded === true) {
        setConfirmation(null);
        setResult(pending.type === 'activate' ? `${pending.label} is active. Enter from START → WORLD → Explore generated area.` : 'Area generated and installed. Enter from START → WORLD → Explore generated area.');
      } else setResult('The operation was not confirmed. Your confirmation and theme are kept. Check the launcher error and active area before deciding whether to try again. Nothing retries automatically.');
    } catch (error) {
      setResult(`The operation was not confirmed. ${error.message || 'Check the launcher error.'} Your confirmation and theme are kept. Nothing retries automatically.`);
    } finally {
      submittingRef.current = false;
      setSubmitting(false);
    }
  }

  return <section className="worlds-section expedition-panel" aria-labelledby="expedition-title">
    <div className="section-heading"><div><span className="eyebrow gold">ON THIS COMPUTER</span><h2 id="expedition-title">Local expeditions</h2></div></div>
    {state.local_host ? <>
      <div className="expedition-session"><h3>{current?.name || 'Local world session'}</h3>
        <p>Trainer {current?.trainer || state.trainer}. Use Play now above to enter the game.</p>
        <p>In the game, open <strong>START → WORLD → Explore generated area</strong>. You need at least one conscious Pokémon in your party.</p>
      </div>
      <section className="published-adventures" aria-labelledby="published-adventures-title">
        <h3 id="published-adventures-title">Published adventures</h3>
        <p className="field-hint">Conversations can change as you talk to characters. A connected director can update them during your visit. Opening an adventure does not start a director agent. Conversation state resets on a new visit. There is no persistent quest progress or reward system.</p>
        {!adventures.length && <p className="muted-copy">{state.area_archive_error ? 'Published adventures could not be checked. See the library error below.' : 'Your director has not published an adventure'}</p>}
        {adventures.map(area => <article className={`settings-card${area.active ? ' expedition-active-area' : ''}`} key={area.identity}><div>
          <h3>{area.label}</h3><p>Interactive adventure · {area.active ? 'Active now' : 'Published'}</p>
          {area.active ? <p className="field-hint">Choose Play now if needed, then START → WORLD → Explore generated area. Face a character and press A (default Z). Leave through WORLD → Leave generated area and save after returning.</p> : <button className="button small ghost" disabled={disabled || Boolean(pending)} onClick={() => review({ type: 'activate', world: state.world_key, identity: area.identity, label: area.label, adventure: true })}>Open adventure</button>}
        </div></article>)}
      </section>
      <div className="generated-area-library">
        <h3>Saved exploration areas</h3>
        <p className="field-hint">Terrain, caves and fixed-dialogue casts are separate from interactive adventures. One area or adventure is active at a time. Everyone must leave it before switching. Reopening a saved area does not call a model.</p>
        {state.area_archive_error && <p role="alert">{state.area_archive_error}</p>}
        {!library.length && !state.area_archive_error && <p className="muted-copy">No saved areas are listed. Generate an area below to begin exploring.</p>}
        {library.map(area => <div className={`settings-card${area.active ? ' expedition-active-area' : ''}`} key={area.identity}><div>
          <h3>{area.label}</h3><p>{areaLabels[area.kind] || 'Generated area'} · {area.active ? 'Active now' : 'Saved'}</p>
          {area.active ? <p className="field-hint">Enter from START → WORLD → Explore generated area. Face characters and press A (default Z). Leave through WORLD → Leave generated area, then save after returning.</p> : <button className="button small ghost" disabled={disabled || Boolean(pending)} onClick={() => review({ type: 'activate', world: state.world_key, identity: area.identity, label: area.label })}>Use this area</button>}
        </div></div>)}
      </div>
      <details className="expedition-details">
        <summary>Generate a new area</summary>
        <div className="expedition-details-content">
          <label className="field-label" htmlFor="expedition-kind">Area type</label>
          <select id="expedition-kind" className="text-input" value={kind} disabled={disabled || Boolean(pending)} onChange={event => setKind(event.target.value)}>
            {Object.entries(areaTypes).map(([value, type]) => <option key={value} value={value} disabled={!state[type.capability]}>{type.label}</option>)}
          </select>
          <p className="field-hint">{areaTypes[kind].description}</p>
          {(kind === 'guided_wilds' || kind === 'cast_wilds') && <p className="field-hint">These characters have fixed dialogue, not interactive adventure rules. Face a character and press A (default Z) for fixed dialogue. These areas use existing Hoenn art and Route 101 encounters, not custom outdoor wildlife. Compatible experimental clients are required to see the characters and dialogue.</p>}
          {!canAuthor ? <p role="status">This host's catalog does not support this area type. Build the compatible game and reopen the local host.</p> : <>
            <label className="field-label" htmlFor="expedition-theme">Area theme</label>
            <textarea id="expedition-theme" className="text-input invite-paste" value={theme} disabled={disabled || Boolean(pending)} onChange={event => setTheme(event.target.value)} placeholder="Describe the landscape or cavern you want to explore." aria-describedby="expedition-theme-help" />
            <p id="expedition-theme-help" className="field-hint">{themeBytes} / 2,000 UTF-8 bytes. The configured model provider receives this theme and usage may incur charges. A new area becomes active; previously saved areas stay in the library.</p>
            <p className="field-hint">{state.cave_persistent ? 'Areas persist across host restarts. Trainer saves remain independent.' : 'This host is not configured to persist areas across restarts.'} Generation does not stop your game.</p>
            {!pending && <button className="button small ghost" disabled={disabled || !theme.trim() || themeBytes > 2000} onClick={() => review({ type: 'generate', world: state.world_key, kind, theme })}>Review generation and cost</button>}
          </>}
        </div>
      </details>
      {pending && <div className="settings-card"><div>
        <h3>{pending.type === 'activate' ? (pending.adventure ? 'Open this adventure?' : 'Make this the active area?') : 'Generate this area?'}</h3>
        {pending.type === 'generate' && <p>{areaLabels[pending.kind] || 'Generated area'}</p>}
        {pending.type === 'activate' ? <><p>{pending.label}</p><p>No model call is made. The current area stays in the library, but everyone must leave it before switching.</p></> : <><p>The provider receives this theme and usage may incur charges:</p><p className="expedition-theme-preview">{pending.theme}</p></>}
        <div className="modal-actions"><button className="button ghost" disabled={disabled} onClick={() => setConfirmation(null)}>Cancel</button><button className="button primary" disabled={disabled} onClick={confirm}>{submitting ? 'Working…' : pending.type === 'activate' ? (pending.adventure ? 'Confirm open adventure' : 'Activate saved area') : 'Confirm generation'}</button></div>
      </div></div>}
      {result && <p className="expedition-result" role="status">{result}</p>}
      {(busy || submitting) && <p role="status">The launcher is working. Gameplay continues in its own window.</p>}
    </> : <>
      {localWorlds.length ? <div className="expedition-world-list">{localWorlds.map(world => <div className="settings-card" key={world.key}><div>
        <h3>{world.name}</h3><p>Trainer {world.trainer} · {world.has_save ? 'Saved game available' : 'No trainer save yet'}</p>
        <button className="button small ghost" disabled={disabled || !world.trainer} onClick={() => onOpen('local_resume', { world: world.key, trainer: world.trainer }, world.key, { playAfter: true })}>{world.has_save ? 'Continue expedition' : 'Open expedition'}</button>
      </div></div>)}</div> : <p className="muted-copy">No local expeditions yet. Create a new save below to get started.</p>}
      {localWorlds.length > 0 && <p className="field-hint">Continue opens the local session and game window. No model call is made when opening a world.</p>}
    </>}
    {!state.local_host && <details className="expedition-details expedition-new-save">
      <summary>Create a new expedition and save</summary>
      <div className="expedition-details-content">
        <p className="muted-copy">Start a separate local world with a new trainer save. This does not resume an existing adventure.</p>
        <label className="field-label" htmlFor="expedition-name">New expedition name</label>
        <input id="expedition-name" className="text-input" maxLength={80} value={name} disabled={disabled} onChange={event => setName(event.target.value)} />
        <label className="field-label" htmlFor="expedition-trainer">New trainer profile</label>
        <input id="expedition-trainer" className="text-input" maxLength={24} value={trainer} disabled={disabled} onChange={event => setTrainer(event.target.value)} aria-describedby="expedition-trainer-help" />
        <p id="expedition-trainer-help" className="field-hint">Use 1–24 letters, numbers, underscores or hyphens. Existing expeditions keep their own trainer profiles.</p>
        <div className="modal-actions"><button className="button small ghost" disabled={disabled || !validTrainer || !name.trim() || /[\x00-\x1f]/.test(name)} onClick={() => onOpen('local_create', { name, trainer })}>Create new expedition and save</button></div>
        <p className="field-hint">Creation opens only the local host, so you can generate an area before playing. It does not call a model or start the game. Choose Play now when ready.</p>
      </div>
    </details>}
    <p className="field-hint">Local hosting ends when the launcher quits. Saved areas stay in this world's private library when persistence is enabled. Remote hosted worlds cannot be authored here.</p>
  </section>;
}
