import React, { useEffect, useState } from 'react';

export default function ExpeditionPanel({ state, ready, busy, onOpen, onAuthor, onActivate }) {
  const [name, setName] = useState('');
  const [trainer, setTrainer] = useState('Player');
  const [theme, setTheme] = useState('');
  const [kind, setKind] = useState('cave');
  const [confirmation, setConfirmation] = useState(null);
  useEffect(() => { setConfirmation(null); }, [state.world_key]);
  const disabled = busy || !ready;
  const validTrainer = /^[A-Za-z0-9_-]{1,24}$/.test(trainer);
  const themeBytes = new TextEncoder().encode(theme).length;
  const localWorlds = state.local_worlds || [];
  const current = localWorlds.find(world => world.key === state.world_key);
  const areas = state.generated_areas || [];
  const pending = confirmation?.world === state.world_key ? confirmation : null;
  const canAuthor = kind === 'wilds' ? state.wilds_authoring : state.cave_authoring;

  return <section className="worlds-section" aria-labelledby="expedition-title">
    <div className="section-heading"><div><span className="eyebrow gold">LOCAL HOST</span><h2 id="expedition-title">Expedition workshop</h2></div></div>
    <p className="muted-copy">Host on this computer to generate and revisit areas. Remote hosted worlds cannot be authored here. Local hosting ends when the launcher quits; saved areas remain in this world's private library.</p>
    {state.local_host ? <>
      <h3>{current?.name || 'Local world session'}</h3>
      <p>Use Play now to enter with your selected trainer. One generated area is active at a time. Everyone must leave it before another can be activated. Generation does not stop the native game.</p>
      <label className="field-label" htmlFor="expedition-kind">Area type</label>
      <select id="expedition-kind" className="text-input" value={kind} disabled={disabled || Boolean(pending)} onChange={event => setKind(event.target.value)}>
        <option value="cave">Cave with custom wildlife</option>
        <option value="wilds" disabled={!state.wilds_authoring}>Outdoor wilds</option>
      </select>
      <p className="field-hint">{kind === 'wilds' ? 'Outdoor areas use existing Hoenn art, blocked water, tall grass and Route 101 encounters—not custom outdoor wildlife.' : 'Caves use existing art with a model-selected biome and custom wildlife roster.'}</p>
      {!canAuthor ? <p role="status">This host's catalog does not support this area type. Build the compatible game and reopen the local host.</p> : <>
        <label className="field-label" htmlFor="expedition-theme">Area theme</label>
        <textarea id="expedition-theme" className="text-input invite-paste" value={theme} disabled={disabled || Boolean(pending)} onChange={event => setTheme(event.target.value)} placeholder="Describe the landscape or cavern you want to explore." aria-describedby="expedition-theme-help" />
        <p id="expedition-theme-help" className="field-hint">{themeBytes} / 2,000 UTF-8 bytes. The configured model provider receives this theme and usage may incur charges. A new area becomes active; previously saved areas stay in the library.</p>
        <p className="field-hint">{state.cave_persistent ? 'The active area persists across host restarts. Trainer saves remain independent.' : 'This host is not configured to persist areas across restarts.'}</p>
        {!pending && <button className="button small primary" disabled={disabled || !theme.trim() || themeBytes > 2000} onClick={() => setConfirmation({ type: 'generate', world: state.world_key, kind, theme })}>Review area generation</button>}
      </>}
      {pending && <div className="settings-card"><div>
        <h3>{pending.type === 'activate' ? 'Make this the active area?' : `Generate a new ${pending.kind === 'wilds' ? 'outdoor area' : 'cave'}?`}</h3>
        {pending.type === 'activate' ? <><p>{pending.label}</p><p>No model call is made. The current area stays in the library, but everyone must leave it before switching.</p></> : <><p>The provider receives this theme and usage may incur charges:</p><p className="expedition-theme-preview">{pending.theme}</p></>}
        <div className="modal-actions"><button className="button ghost" disabled={disabled} onClick={() => setConfirmation(null)}>Cancel</button><button className="button primary" disabled={disabled} onClick={async () => {
          if (pending.type === 'activate') await onActivate({ world: pending.world, identity: pending.identity, confirmed: true });
          else await onAuthor({ world: pending.world, kind: pending.kind, theme: pending.theme, confirmed: true });
          setConfirmation(null);
        }}>{pending.type === 'activate' ? 'Activate saved area' : 'Confirm generation'}</button></div>
      </div></div>}
      {busy && <p role="status">The launcher is working. Native gameplay continues in its own window.</p>}
      {state.area_archive && <div className="generated-area-library">
        <h3>Saved areas</h3>
        <p className="field-hint">Reactivate an area without calling a model. This is a library, not simultaneous travel between regions.</p>
        {state.area_archive_error && <p role="alert">{state.area_archive_error}</p>}
        {!areas.length && !state.area_archive_error && <p className="muted-copy">Generate your first area to keep it here.</p>}
        {areas.map(area => <div className="settings-card" key={area.identity}><div>
          <h3>{area.label}</h3><p>{area.kind === 'wilds' ? 'Outdoor wilds' : 'Cave'} · {area.active ? 'Active' : 'Saved'}</p>
          <button className="button small ghost" disabled={disabled || area.active || Boolean(pending)} onClick={() => setConfirmation({ type: 'activate', world: state.world_key, identity: area.identity, label: area.label })}>{area.active ? 'Currently active' : 'Choose saved area'}</button>
        </div></div>)}
      </div>}
    </> : <>
      <label className="field-label" htmlFor="expedition-trainer">Local trainer profile</label>
      <input id="expedition-trainer" className="text-input" maxLength={24} value={trainer} disabled={disabled} onChange={event => setTrainer(event.target.value)} aria-describedby="expedition-trainer-help" />
      <p id="expedition-trainer-help" className="field-hint">Use 1–24 letters, numbers, underscores or hyphens. Resume with the same profile name to use your save.</p>
      <label className="field-label" htmlFor="expedition-name">New expedition name</label>
      <input id="expedition-name" className="text-input" maxLength={80} value={name} disabled={disabled} onChange={event => setName(event.target.value)} />
      <div className="modal-actions"><button className="button small primary" disabled={disabled || !validTrainer || !name.trim() || /[\x00-\x1f]/.test(name)} onClick={() => onOpen('local_create', { name, trainer })}>Create local expedition</button></div>
      <p className="field-hint">Creating or reopening a host does not call a model. Open it, then generate an area or press Play now.</p>
      {localWorlds.map(world => <div className="settings-card" key={world.key}><div><h3>{world.name}</h3><button className="button small ghost" disabled={disabled || !validTrainer} onClick={() => onOpen('local_resume', { world: world.key, trainer }, world.key)}>Open local host</button></div></div>)}
    </>}
  </section>;
}
