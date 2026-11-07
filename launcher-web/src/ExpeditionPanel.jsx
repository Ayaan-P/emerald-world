import React, { useEffect, useRef, useState } from 'react';
import AreaLibrary from './AreaLibrary';

const areaTypes = {
  xl_wilds: { label: 'XL outdoor world (127 × 127)', capability: 'xl_wilds_authoring', description: 'A shared outdoor world with four times the terrain of standard wilds. Existing Hoenn art and encounters; no generated characters, story graphs or editable overlays in this XL multiplayer mode. Matching clients required.' },
  cave: { label: 'Cave', capability: 'cave_authoring', description: 'Existing art, a generated layout and a custom wildlife roster.' },
  wilds: { label: 'Outdoor wilds', capability: 'wilds_authoring', description: 'Outdoor areas use existing Hoenn art, blocked water, tall grass and Route 101 encounters, not custom outdoor wildlife.' },
  guided_wilds: { label: 'Outdoor wilds with a guide', capability: 'guided_wilds_authoring', description: 'Outdoor wilds with one guide and short model-authored dialogue. Talk to the guide in the game. Dialogue is fixed text, not a live conversation.' },
  cast_wilds: { label: 'Outdoor wilds with characters', capability: 'cast_wilds_authoring', description: 'Outdoor wilds with one to three characters and short model-authored dialogue. Talk to them in the game. Dialogue is fixed text, not a live conversation.' },
};
const areaLabels = { ...Object.fromEntries(Object.entries(areaTypes).map(([key, type]) => [key, type.label])), event_wilds: 'Interactive adventure' };

export default function ExpeditionPanel({ state, ready, busy, onOpen, onAuthor, onActivate, onSelectHostedArea, onRefreshHosted, onHostedWorlds, onInspect, onEditTerrain }) {
  const [name, setName] = useState('');
  const [trainer, setTrainer] = useState('Player');
  const [theme, setTheme] = useState('');
  const [kind, setKind] = useState('cave');
  const [confirmation, setConfirmation] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState('');
  const submittingRef = useRef(false);
  const confirmationPanel = useRef(null);
  const confirmationOpener = useRef(null);
  const hadConfirmation = useRef(false);
  const areaWorldKey = state.area_world_key || state.world_key;
  useEffect(() => { setConfirmation(null); setResult(''); }, [areaWorldKey, state.local_host, state.area_authoring]);
  const authoring = Boolean(state.local_host || state.area_authoring);
  const disabled = busy || submitting || !ready;
  const validTrainer = /^[A-Za-z0-9_-]{1,24}$/.test(trainer);
  const themeBytes = new TextEncoder().encode(theme).length;
  const localWorlds = state.local_worlds || [];
  const current = state.hosted_area_world || localWorlds.find(world => world.key === areaWorldKey);
  const areas = [...(state.generated_areas || [])].sort((a, b) => Number(b.active) - Number(a.active));
  const activeArea = state.active_generated_area;
  const occupied = (activeArea?.occupants || 0) > 0;
  const gameRunning = state.games?.includes(state.trainer);
  const pending = authoring && confirmation?.world === areaWorldKey ? confirmation : null;
  const canAuthor = state[areaTypes[kind].capability];
  useEffect(() => {
    if (pending) {
      confirmationPanel.current?.focus();
      confirmationPanel.current?.scrollIntoView?.({ block: 'nearest' });
    } else if (hadConfirmation.current && confirmationOpener.current?.isConnected) {
      confirmationOpener.current.focus();
    }
    hadConfirmation.current = Boolean(pending);
  }, [pending]);

  function review(value) {
    if (disabled || pending || submittingRef.current) return;
    setResult('');
    confirmationOpener.current = document.activeElement;
    setConfirmation(value);
  }

  async function confirm() {
    if (disabled || !authoring || occupied || !pending || submittingRef.current) return;
    submittingRef.current = true;
    setSubmitting(true);
    setResult('');
    try {
      const succeeded = pending.type === 'activate'
        ? await onActivate({ world: pending.world, identity: pending.identity, confirmed: true })
        : await onAuthor({ world: pending.world, kind: pending.kind, theme: pending.theme, confirmed: true });
      if (succeeded === true) {
        setConfirmation(null);
        setResult(pending.type === 'activate' ? `${pending.label} is active. Enter from START → WORLD → Explore generated area.` : 'Area generated. Enter from START → WORLD → Explore generated area.');
      } else setResult('The operation was not confirmed. Your confirmation and theme are kept. Check the launcher error and active area before deciding whether to try again. Nothing retries automatically.');
    } catch (error) {
      setResult(`The operation was not confirmed. ${error.message || 'Check the launcher error.'} Your confirmation and theme are kept. Nothing retries automatically.`);
    } finally {
      submittingRef.current = false;
      setSubmitting(false);
    }
  }

  return <section className="worlds-section expedition-panel" aria-labelledby="expedition-title">
    <div className="section-heading"><div><h2 id="expedition-title">Generated areas</h2></div></div>
    {authoring && <>
      <div className="expedition-session"><h3>{current?.name || 'Local world'}</h3>
        <p>Trainer {current?.trainer || state.trainer}. {state.hosted_area_world ? 'Owned hosted world. Generation changes this persistent world, not your solo save.' : gameRunning ? 'Game running.' : 'Game stopped.'}</p>
        {!activeArea && <p>Choose a saved area or generate a new one.</p>}
      </div>
      {activeArea && <section className="settings-card expedition-current-area" aria-label="Current exploration area"><div>
        <span className="mode-label">Active area</span><h3>{activeArea.label}</h3>
        <p>{activeArea.kind === 'xl_wilds' ? 'XL outdoor world' : areaLabels[activeArea.kind] || 'Generated area'} · {activeArea.side} × {activeArea.side}</p>
        <p className="enter-area">In game: <strong>START → WORLD → Explore generated area</strong></p>
        <details className="area-help"><summary>Entry and return</summary><p>Go outdoors on foot with a conscious non-Egg Pokémon. Return through WORLD → Leave generated area, then save.</p></details>
        {occupied ? <p role="status">{activeArea.occupants} {activeArea.occupants === 1 ? 'trainer' : 'trainers'} inside. Everyone must leave before replacing this area.</p>
          : <p className="field-hint">No trainers inside.</p>}
      </div></section>}
    </>}
      <section className="expedition-generator" aria-labelledby="generate-title">
        <h3 id="generate-title">Generate an area</h3>
        <div className="expedition-details-content">
          <label className="field-label" htmlFor="expedition-kind">Area type</label>
          <select id="expedition-kind" className="text-input" value={kind} disabled={disabled || !authoring || Boolean(pending)} onChange={event => setKind(event.target.value)}>
            {Object.entries(areaTypes).map(([value, type]) => <option key={value} value={value} disabled={!state[type.capability]}>{type.label}</option>)}
          </select>
          <p className="field-hint">{areaTypes[kind].description}</p>
          {(kind === 'guided_wilds' || kind === 'cast_wilds') && <p className="field-hint">Face a character and press A (default Z). Dialogue is fixed text, not live chat.</p>}
          {!authoring ? <p role="status">Generation is not available in solo or offline story mode. Open or create a local world below, or select an owned hosted world.</p> : !canAuthor && <p role="status">This world does not support this area type. Check the game setup or choose another world.</p>}
            <label className="field-label" htmlFor="expedition-theme">Area theme</label>
            <textarea id="expedition-theme" className="text-input invite-paste" value={theme} disabled={disabled || !authoring || !canAuthor || Boolean(pending)} onChange={event => setTheme(event.target.value)} placeholder="Describe the landscape or cavern you want to explore." aria-describedby="expedition-theme-help" />
            <p id="expedition-theme-help" className="field-hint">{themeBytes} / 2,000 bytes. Requires a supported, signed-in model CLI. Your provider receives the theme and may charge for generation.</p>
            <p className="field-hint">{!authoring ? 'Select a world before generating. Offline story saves are not changed.' : state.cave_persistent ? 'Generated areas are saved in this world.' : 'This host does not save areas across restarts.'}</p>
            {!pending && <button className="button small ghost" disabled={disabled || !authoring || !canAuthor || occupied || !theme.trim() || themeBytes > 2000} onClick={() => review({ type: 'generate', world: areaWorldKey, kind, theme })}>Review generation</button>}
        </div>
      </section>
    {authoring && <>
      {pending && <section className="settings-card generation-confirmation" ref={confirmationPanel} tabIndex={-1} aria-label="Review area change"><div>
        <h3>{pending.type === 'activate' ? (pending.adventure ? 'Open this adventure?' : 'Make this the active area?') : 'Generate this area?'}</h3>
        {pending.type === 'generate' && <p>{areaLabels[pending.kind] || 'Generated area'}</p>}
        {pending.type === 'activate' ? <><p>{pending.label}</p><p>No model call is made. Everyone must leave the current area before switching.</p></> : <><p>The provider receives this theme and usage may incur charges:</p><p className="expedition-theme-preview">{pending.theme}</p></>}
        <div className="modal-actions"><button className="button ghost" disabled={disabled} onClick={() => setConfirmation(null)}>Cancel</button><button className="button primary" disabled={disabled || occupied} onClick={confirm}>{submitting ? 'Working…' : pending.type === 'activate' ? (pending.adventure ? 'Confirm open adventure' : 'Activate saved area') : 'Confirm generation'}</button></div>
      </div></section>}
      <AreaLibrary key={areaWorldKey} world={areaWorldKey} areas={areas} error={state.area_archive_error} disabled={disabled} occupied={occupied} pending={pending} onInspect={onInspect} onReview={review} onEditTerrain={onEditTerrain} />
      {!onInspect && <p className="field-hint">Map previews and terrain editing are available only for the selected local owner host. Hosted generation and activation still use the hosting service.</p>}
      {result && <p className="expedition-result" role="status">{result}</p>}
      {(busy || submitting) && <p role="status">Working. Your game can keep running.</p>}
    </>}
    {!state.local_host && <>
      {localWorlds.length ? <div className="expedition-world-list">{localWorlds.map(world => <div className="settings-card" key={world.key}><div>
        <h3>{world.name}</h3><p>Trainer {world.trainer} · {world.has_save ? 'Saved game available' : 'No trainer save yet'}</p>
        <button className="button small ghost" disabled={disabled || !world.trainer} onClick={() => onOpen('local_resume', { world: world.key, trainer: world.trainer }, world.key, { playAfter: false })}>Open local world</button>
      </div></div>)}</div> : <p className="muted-copy">Open a local world below, or choose an owned hosted world for generation.</p>}
      {localWorlds.length > 0 && <p className="field-hint">Opening a local world makes no model call.</p>}
    </>}
    <section aria-label="Owned hosted worlds for generation">
      <h3>Generate in an owned hosted world</h3>
      <p className="field-hint">Selecting a world does not connect or start a game, stop your current game, or call a model. Only worlds owned by your account can be edited.</p>
      {state.hosted_area_error && <p role="alert">{state.hosted_area_error}</p>}
      {state.hosting?.enrolled ? <>
        <button className="text-button" disabled={disabled || !onRefreshHosted} onClick={onRefreshHosted}>{state.hosting.loaded ? 'Refresh owned worlds' : 'Load owned worlds'}</button>
        {(state.hosting.worlds || []).map(world => <div className="settings-card" key={world.id}><div>
          <h4>{world.name}</h4><p>Hosted · Trainer {world.trainer}</p>
          <button className="button small ghost" aria-label={`Select ${world.name} for generation`} disabled={disabled || !onSelectHostedArea || state.hosted_area_world?.id === world.id} onClick={() => onSelectHostedArea(world)}>{state.hosted_area_world?.id === world.id ? 'Selected for generation' : 'Select for generation'}</button>
        </div></div>)}
        {state.hosting.loaded && !state.hosting.worlds?.length && <p className="muted-copy">No owned hosted worlds. Create one in Hosted worlds.</p>}
      </> : <p className="muted-copy">Add or restore owner access in Hosted worlds to select a persistent world.</p>}
      {onHostedWorlds && <button className="text-button" disabled={disabled} onClick={onHostedWorlds}>Open Hosted worlds</button>}
    </section>
    {!state.local_host && <details className="expedition-details expedition-new-save">
      <summary>Create a local world</summary>
      <div className="expedition-details-content">
        <p className="muted-copy">Create a world on this computer with a separate trainer save.</p>
        <label className="field-label" htmlFor="expedition-name">World name</label>
        <input id="expedition-name" className="text-input" maxLength={80} value={name} disabled={disabled} onChange={event => setName(event.target.value)} />
        <label className="field-label" htmlFor="expedition-trainer">Trainer profile</label>
        <input id="expedition-trainer" className="text-input" maxLength={24} value={trainer} disabled={disabled} onChange={event => setTrainer(event.target.value)} aria-describedby="expedition-trainer-help" />
        <p id="expedition-trainer-help" className="field-hint">1–24 letters, numbers, underscores or hyphens.</p>
        <div className="modal-actions"><button className="button small ghost" disabled={disabled || !validTrainer || !name.trim() || /[\x00-\x1f]/.test(name)} onClick={() => onOpen('local_create', { name, trainer })}>Create local world</button></div>
        <p className="field-hint">Creates the local host without starting the game or calling a model.</p>
      </div>
    </details>}
    <p className="field-hint">Local hosting stops when you quit the launcher.</p>
  </section>;
}
