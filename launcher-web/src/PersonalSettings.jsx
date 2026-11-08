import React, { useEffect, useRef, useState } from 'react';
import './personal-settings.css';

const buttons = [['up', 'Up'], ['down', 'Down'], ['left', 'Left'], ['right', 'Right'],
  ['a', 'A / Confirm'], ['b', 'B / Back'], ['start', 'Start / Menu'], ['select', 'Select'], ['l', 'L'], ['r', 'R']];
const keyLabel = key => ({ return: 'Enter', backspace: 'Backspace', ' ': 'Space' }[key] || key.replace(/\b\w/g, char => char.toUpperCase()));

export default function PersonalSettings({ ready, busy, onRequest, onDirtyChange }) {
  const [info, setInfo] = useState(null);
  const [profile, setProfile] = useState('');
  const [base, setBase] = useState(null);
  const [draft, setDraft] = useState({});
  const [working, setWorking] = useState(true);
  const [failed, setFailed] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [saved, setSaved] = useState(false);
  const [pendingProfile, setPendingProfile] = useState(null);
  const alive = useRef(false);
  const inFlight = useRef(false);
  const request = useRef(onRequest);
  request.current = onRequest;
  const changes = Object.fromEntries(Object.entries(draft).filter(([key, value]) => value !== base?.values[key]));
  const dirty = Boolean(base && Object.keys(changes).length);

  async function load(id) {
    setWorking(true); setFailed(false); setSaved(false);
    try {
      const value = await request.current('personal_settings_read', { profile: id });
      if (!alive.current) return;
      if (value?.revision && value.values) { setBase(value); setDraft(value.values); setUncertain(false); }
      else { setBase(null); setDraft({}); setFailed(true); }
    } catch { if (alive.current) { setFailed(true); setBase(null); setDraft({}); } }
    finally { if (alive.current) setWorking(false); }
  }

  async function initialize() {
    setWorking(true); setFailed(false);
    try {
      const result = await request.current('personal_settings_info', {});
      if (!alive.current) return;
      if (!result || typeof result.available !== 'boolean' || !Array.isArray(result.profiles)
          || (result.available && (!result.defaults || !Array.isArray(result.keys)))) { setFailed(true); return; }
      setInfo(result);
      if (result.available && result.profiles.length) {
        setProfile(result.profiles[0].id);
        await load(result.profiles[0].id);
      }
    } catch { if (alive.current) setFailed(true); }
    finally { if (alive.current) setWorking(false); }
  }

  useEffect(() => { alive.current = true; initialize(); return () => { alive.current = false; }; }, []);
  useEffect(() => { onDirtyChange(dirty || uncertain); }, [dirty, uncertain, onDirtyChange]);
  useEffect(() => () => onDirtyChange(false), [onDirtyChange]);
  useEffect(() => {
    if (!dirty && !uncertain) return;
    const guard = event => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', guard);
    return () => window.removeEventListener('beforeunload', guard);
  }, [dirty, uncertain]);

  function choose(id) {
    if (dirty || uncertain) { setPendingProfile(id); return; }
    setProfile(id); setBase(null); load(id);
  }
  function edit(key, value) { setDraft(previous => ({ ...previous, [key]: value })); setSaved(false); }
  async function save() {
    if (inFlight.current || !dirty || !ready || busy || working || uncertain) return;
    inFlight.current = true; setWorking(true); setSaved(false);
    try {
      const value = await request.current('personal_settings_save', { profile, changes, expected_revision: base.revision });
      if (!alive.current) return;
      if (value?.revision && value.values) { setBase(value); setDraft(value.values); setSaved(true); }
      else setUncertain(true);
    } catch { if (alive.current) setUncertain(true); }
    finally { inFlight.current = false; if (alive.current) setWorking(false); }
  }

  const disabled = !ready || busy || working || uncertain || failed;
  const selected = info?.profiles.find(item => item.id === profile);
  const duplicates = buttons.filter(([key]) => draft[key] && buttons.some(([other]) => other !== key && draft[key] === draft[other]));
  return <section className="personal-settings" aria-labelledby="personal-settings-title">
    <div className="section-heading"><div><h2 id="personal-settings-title">Display & controls</h2><p>Saved for one trainer profile. Applies next launch.</p></div></div>
    {info?.available === false ? <p>Editing is available for Expansion profiles. Use the native settings file for other builds.</p>
      : info && info.profiles.length === 0 ? <p>Start an adventure to create a trainer profile.</p>
      : <>
        {info && <><label className="field-label" htmlFor="settings-profile">Trainer profile</label><select id="settings-profile" className="text-input profile-select" value={profile} disabled={busy || working || !ready} onChange={event => choose(event.target.value)}>{info.profiles.map(item => <option key={item.id} value={item.id}>{item.name} · {item.trainer} · {item.offline ? 'Solo' : 'World'}</option>)}</select></>}
        {pendingProfile && <div className="settings-warning" role="alert"><p>Discard this draft and switch profiles?</p><div className="personal-actions"><button className="button ghost" disabled={busy || working} onClick={() => setPendingProfile(null)}>Keep editing</button><button className="button primary" disabled={busy || working} onClick={() => { const id = pendingProfile; setPendingProfile(null); setProfile(id); setBase(null); load(id); }}>Discard draft</button></div></div>}
        {working && <p role="status">{inFlight.current ? 'Saving settings…' : 'Loading settings…'}</p>}
        {failed && <div className="settings-warning" role="alert"><p>Settings could not be loaded.</p><button className="button ghost" disabled={busy || working || !ready} onClick={() => info ? load(profile) : initialize()}>Retry loading</button></div>}
        {uncertain && <div className="settings-warning" role="alert"><p>Reload settings before trying again. The last save was not confirmed.</p><button className="button ghost" disabled={busy || working || !ready} onClick={() => load(profile)}>Discard draft & reload</button></div>}
        {base && <>
          <div className="personal-display"><label className="field-label">Window scale<select className="text-input" value={draft.scale ?? ''} disabled={disabled} onChange={event => edit('scale', Number(event.target.value))}>{draft.scale === null && <option value="">Custom file value</option>}{Array.from({ length: 16 }, (_, index) => index + 1).map(value => <option key={value} value={value}>{value}× · {value * 240} × {value * 160}</option>)}</select></label><label className="field-label">Fullscreen<select className="text-input" value={draft.fullscreen ?? ''} disabled={disabled} onChange={event => edit('fullscreen', event.target.value)}>{draft.fullscreen === null && <option value="">Custom file value</option>}<option value="auto">Auto (Steam Deck)</option><option value="yes">On</option><option value="no">Off</option></select></label></div>
          <div className="section-heading keyboard-heading"><h3>Keyboard</h3><span>Physical keys</span></div>
          <div className="personal-keyboard">{buttons.map(([key, label]) => <label className="field-label" key={key}>{label}<select className="text-input" disabled={disabled} value={draft[key] ?? ''} onChange={event => edit(key, event.target.value)}>{draft[key] === null && <option value="">Custom file value</option>}{info.keys.map(value => <option key={value} value={value}>{keyLabel(value)}</option>)}</select></label>)}</div>
          {duplicates.length > 0 && <p className="settings-warning" role="status">Some buttons share a key: {duplicates.map(([, label]) => label).join(', ')}.</p>}
          {base.custom.length > 0 && <p className="field-hint">Custom file values stay unchanged unless you replace them here.</p>}
          <p className="field-hint">F1 shows your active controls in game. Use Ctrl+T for chat if T is remapped. Controller game buttons are remapped through Steam Input.</p>
          <p className="field-hint">Save and close this trainer’s game before applying. Other profiles and shared world rules stay unchanged.</p>
          {saved && <p className="personal-saved" role="status">Settings saved for {selected?.trainer}. They apply next launch.</p>}
          <div className="personal-actions"><button className="text-button" disabled={disabled} onClick={() => { setDraft({ ...info.defaults }); setSaved(false); }}>Use defaults</button>{!uncertain && <button className="button ghost" disabled={busy || working || !ready} onClick={() => load(profile)}>{dirty ? 'Discard draft & reload' : 'Reload'}</button>}<button className="button primary" disabled={disabled || !dirty || Boolean(pendingProfile)} onClick={save}>Save settings</button></div>
        </>}
      </>}
  </section>;
}
