import React, { useState } from 'react';
import { perform } from './api';

const labels = { partyEXP: 'Party EXP', reusableTMs: 'Reusable TMs', modernSplit: 'Modern physical/special split', megaEvolution: 'Mega Evolution', expandedRoster: 'Expanded roster' };

export default function WorldRules({ state }) {
  const [world, setWorld] = useState('');
  const [policy, setPolicy] = useState(null);
  const [draft, setDraft] = useState(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const hosted = state.hosting?.worlds || [];
  const editable = Boolean(world || state.world_rules_owner);
  const action = world ? 'host_rules_' : 'world_rules_';
  const payload = world ? { world } : {};
  async function load() {
    setBusy(true); setMessage('');
    try {
      const value = await perform(action + 'get', payload);
      setPolicy(value.world_rules); setDraft(value.world_rules?.rules || null);
      if (!value.world_rules) setMessage('Connect to a world to view its rules.');
    } catch (error) { setMessage(error.message); setPolicy(null); setDraft(null); }
    finally { setBusy(false); }
  }
  async function save() {
    setBusy(true); setMessage('');
    try {
      await perform(action + 'set', { ...payload, rules: { ...draft } });
      const value = await perform(action + 'get', payload);
      setPolicy(value.world_rules); setDraft(value.world_rules.rules);
      setMessage('World rules saved. Reconnect clients before playing.');
    } catch (error) { setMessage(error.message); }
    finally { setBusy(false); }
  }
  function changeRule(key, checked) {
    if (key === 'modernSplit' && !checked && draft.megaEvolution) {
      setMessage('Turn off Mega Evolution first to disable the modern physical/special split.');
      return;
    }
    setMessage('');
    setDraft({ ...draft, [key]: checked, ...(key === 'megaEvolution' && checked ? { modernSplit: true } : {}) });
  }
  return <section className="settings-card" aria-label="World gameplay rules"><div>
    <h3>World gameplay rules</h3>
    <p>Everyone in a world uses the same gameplay rules. Trainer saves stay private. Close every game before the owner changes these settings. Display and controls stay local.</p>
    <label>World <select aria-label="World rules target" value={world} disabled={busy} onChange={event => { setWorld(event.target.value); setPolicy(null); setDraft(null); setMessage(''); }}>
      <option value="">Connected world</option>
      {hosted.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
    </select></label>{' '}
    <button className="button small ghost" disabled={busy || (!world && !state.connected)} onClick={load}>Load world rules</button>
    {draft && <fieldset disabled={busy || !editable}><legend>{editable ? 'Owner settings' : 'Read-only world settings'}</legend>
      {Object.entries(labels).map(([key, label]) => <label key={key} style={{ display: 'block' }}><input type="checkbox" checked={draft[key]} disabled={busy || !editable} onChange={event => changeRule(key, event.target.checked)} /> {label}</label>)}
    </fieldset>}
    {policy && <p>Rules version {policy.version}. Mega Evolution requires the modern physical/special split. Checking Mega Evolution also enables that setting.</p>}
    {policy && editable && <button className="button small primary" disabled={busy} onClick={save}>Save world rules</button>}
    {message && <p role="status">{message}</p>}
  </div></section>;
}
