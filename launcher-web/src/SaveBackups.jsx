import React, { useEffect, useRef, useState } from 'react';
import { ArrowDownToLine, ArrowLeft, LockKeyhole, ShieldCheck } from 'lucide-react';
import { perform } from './api';

/** Local, explicit exports only. Save bytes are never put in React state. */
export default function SaveBackups({ state, busy, onBack }) {
  const [availability, setAvailability] = useState(null);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState('');
  const [download, setDownload] = useState(null);
  const alive = useRef(true);
  const inFlight = useRef(false);

  useEffect(() => {
    alive.current = true;
    perform('save_backup_info', {}).then(result => {
      if (alive.current) setAvailability(result.available);
    }).catch(() => { if (alive.current) setAvailability('error'); });
    return () => { alive.current = false; };
  }, []);

  useEffect(() => {
    if (!download) return;
    return () => URL.revokeObjectURL(download.url);
  }, [download]);

  async function backup(profile) {
    if (inFlight.current || busy) return;
    inFlight.current = true; setWorking(true); setError(''); setDownload(null);
    try {
      const result = await perform('save_backup', {
        world: profile.world, trainer: profile.trainer, offline: profile.offline,
      });
      if (!alive.current) return;
      const binary = atob(result.data);
      const bytes = Uint8Array.from(binary, char => char.charCodeAt(0));
      const url = URL.createObjectURL(new Blob([bytes], { type: 'application/octet-stream' }));
      setDownload({ url, filename: result.filename });
    } catch (failure) {
      if (alive.current) setError(failure.message || 'Could not create the backup.');
    } finally {
      inFlight.current = false;
      if (alive.current) setWorking(false);
    }
  }

  const profiles = [
    ...(state.local_worlds || []).filter(world => world.has_save).map(world => ({ world: world.key, trainer: world.trainer, name: world.name, offline: false, local: true })),
    ...state.worlds.map(world => ({ world: world.key, trainer: world.trainer, name: world.name, offline: false })),
    ...state.offline_saves.map(save => ({ ...save, offline: true })),
  ];

  return <div className="interior">
    <button className="back" onClick={onBack}><ArrowLeft size={16} /> Back to play</button>
    <span className="eyebrow gold">KEEP YOUR PROGRESS</span>
    <h1>Your saves,<br /><em>in your hands.</em></h1>
    <p className="lead">Create a separate local copy of a trainer's progress. Save and close that game first. The original stays where it is.</p>
    <div className="settings-card"><div className="settings-icon"><ShieldCheck size={22} /></div><div><h3>Your progress is separate</h3><p>Trainer saves live on this device. An owner-account backup does not include them. Save backups do not contain server worlds or host credentials.</p></div></div>
    {availability === null ? <p className="muted-copy">Checking save backup support…</p> : availability === 'error' ? <p className="inline-error" role="alert">The local launcher is unavailable. Restart it and try again.</p> : !availability ? <p className="muted-copy">Save backup support is not installed in this version yet.</p> : profiles.length === 0 ? <p className="muted-copy">No saved trainer profiles are available yet. Start an adventure first.</p> : <div className="backup-list">{profiles.map(profile => {
      const running = state.games.includes(profile.offline ? `offline/${profile.trainer}` : profile.trainer);
      return <article className="solo-item" key={`${profile.offline ? 'offline' : 'online'}/${profile.world}/${profile.trainer}`}><div className="session-icon"><LockKeyhole size={20} /></div><div className="session-copy"><strong>{profile.name}</strong><span>{profile.trainer} · {profile.local ? 'Local expedition save' : profile.offline ? 'Offline save' : 'Online-world save'}{running ? ' · Close the game first' : ''}</span></div><button className="button small primary" disabled={busy || working || running} onClick={() => backup(profile)}>Create backup</button></article>;
    })}</div>}
    {error && <p className="inline-error" role="alert">{error}</p>}
    {download && <div className="settings-card" role="status"><div className="settings-icon"><ArrowDownToLine size={22} /></div><div><h3>Your save backup is ready</h3><p>Your browser's downloads folder may not be private. Move the file to encrypted storage. The original save was not changed; save compatibility is not verified.</p><a className="button small primary" href={download.url} download={download.filename}><ArrowDownToLine size={16} /> Download save</a><button className="button small ghost" onClick={() => setDownload(null)}>Done</button></div></div>}
  </div>;
}
