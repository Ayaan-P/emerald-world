import React, { useState } from 'react';

export default function ExpeditionPanel({ state, ready, busy, onOpen, onAuthor }) {
  const [name, setName] = useState('');
  const [trainer, setTrainer] = useState('Player');
  const [theme, setTheme] = useState('');
  const [confirmation, setConfirmation] = useState(null);
  const disabled = busy || !ready;
  const validTrainer = /^[A-Za-z0-9_-]{1,24}$/.test(trainer);
  const themeBytes = new TextEncoder().encode(theme).length;
  const localWorlds = state.local_worlds || [];
  const current = localWorlds.find(world => world.key === state.world_key);

  return <section className="worlds-section" aria-labelledby="expedition-title">
    <div className="section-heading"><div><span className="eyebrow gold">LOCAL HOST</span><h2 id="expedition-title">Expedition workshop</h2></div></div>
    <p className="muted-copy">Host an expedition on this computer to author a generated cave. This is separate from remote hosted worlds, whose caves cannot be generated here. No host access file is needed. Local hosting ends when the launcher quits.</p>
    {state.local_host ? <>
      <h3>{current?.name || 'Local world session'}</h3>
      <p>Use Play now to enter with your selected trainer. Cave generation does not stop the native game. Everyone must leave the generated cave before it can be replaced.</p>
      {!state.cave_authoring ? <p role="status">This host's map catalog does not support the generated cave. Build the compatible game and restart the local host before authoring.</p> : <>
        <label className="field-label" htmlFor="expedition-theme">Cave theme</label>
        <textarea id="expedition-theme" className="text-input invite-paste" value={theme} disabled={disabled || Boolean(confirmation)} onChange={event => setTheme(event.target.value)} placeholder="Describe the cave layout, atmosphere and wildlife you want." aria-describedby="expedition-theme-help" />
        <p id="expedition-theme-help" className="field-hint">{themeBytes} / 2,000 UTF-8 bytes. Your theme is sent to the configured model provider through the existing Codex adapter. Usage may incur charges. Generation replaces the current cave for compatible players.</p>
        <p className="field-hint">{state.cave_persistent ? 'The installed cave persists when this world restarts.' : 'The installed cave lasts only for this host session. Trainer saves remain on this device.'}</p>
        {confirmation && confirmation.world === state.world_key ? <div className="settings-card"><div>
          <h3>Generate and replace this cave?</h3>
          <p>The provider will receive this theme and may charge for the request:</p><p className="expedition-theme-preview">{confirmation.theme}</p>
          <p>Stay connected while generation and installation finish. Do not retry unless an error is reported.</p>
          <div className="modal-actions"><button className="button ghost" disabled={disabled} onClick={() => setConfirmation(null)}>Cancel</button><button className="button primary" disabled={disabled} onClick={async () => { await onAuthor({ ...confirmation, confirmed: true }); setConfirmation(null); }}>Confirm paid generation</button></div>
        </div></div> : <button className="button small primary" disabled={disabled || !theme.trim() || themeBytes > 2000} onClick={() => setConfirmation({ world: state.world_key, theme })}>Review cave generation</button>}
        {busy && <p role="status">The launcher is working. Native gameplay continues in its own window.</p>}
      </>}
    </> : <>
      <label className="field-label" htmlFor="expedition-trainer">Local trainer profile</label>
      <input id="expedition-trainer" className="text-input" maxLength={24} value={trainer} disabled={disabled} onChange={event => setTrainer(event.target.value)} aria-describedby="expedition-trainer-help" />
      <p id="expedition-trainer-help" className="field-hint">Use 1–24 letters, numbers, underscores or hyphens. To resume your save, use the same profile name as before.</p>
      <label className="field-label" htmlFor="expedition-name">New expedition name</label>
      <input id="expedition-name" className="text-input" maxLength={80} value={name} disabled={disabled} onChange={event => setName(event.target.value)} />
      <div className="modal-actions"><button className="button small primary" disabled={disabled || !validTrainer || !name.trim() || /[\x00-\x1f]/.test(name)} onClick={() => onOpen('local_create', { name, trainer })}>Create local expedition</button></div>
      <p className="field-hint">Creating or opening a local host does not call a model. Open the host first, then review generation or press Play now.</p>
      {localWorlds.map(world => <div className="settings-card" key={world.key}><div><h3>{world.name}</h3><button className="button small ghost" disabled={disabled || !validTrainer} onClick={() => onOpen('local_resume', { world: world.key, trainer }, world.key)}>Open local host</button></div></div>)}
    </>}
  </section>;
}
