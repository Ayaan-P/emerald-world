import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ArrowDownToLine, ArrowLeft, ArrowRight, Check, Compass, DoorOpen, Gamepad2, Globe2, Leaf, LoaderCircle, LockKeyhole, Menu, Plus, Settings2, ShieldCheck, Sparkles, Star, UsersRound, X } from 'lucide-react';
import { forgetCapability, loadState, perform } from './api';
import './style.css';
import SaveBackups from './SaveBackups';
import PlayerHome from './PlayerHome';
import GameMirror from './GameMirror';

const empty = { local_worlds: [], local_host: false, cave_authoring: false, cave_persistent: false, worlds: [], offline_saves: [], presence: null, hosting: { available: false, backup_available: false, enrolled: false, loaded: false, worlds: [], pending: null }, setup: [], connected: false, world_key: null, offline_world_key: null, trainer: null, games: [], status: 'Choose a world to begin.' };

export function App() {
  const [state, setState] = useState(empty);
  const [ready, setReady] = useState(false);
  const [page, setPage] = useState('play');
  const [dialog, setDialog] = useState(null);
  const [busy, setBusy] = useState(false);
  const [workLabel, setWorkLabel] = useState('Working');
  const busyRef = useRef(false);
  const [error, setError] = useState('');
  const [connectionError, setConnectionError] = useState('');
  const [menu, setMenu] = useState(false);
  const [invitation, setInvitation] = useState(null);
  const [fileName, setFileName] = useState('');
  const [dragging, setDragging] = useState(false);
  const [inviteMode, setInviteMode] = useState('file');
  const [pasteText, setPasteText] = useState('');
  const [inviteKind, setInviteKind] = useState('native');
  const [inviteFingerprint, setInviteFingerprint] = useState('');
  const [hostFingerprint, setHostFingerprint] = useState('');
  const [joinTrainer, setJoinTrainer] = useState('Player');
  const [hostAccess, setHostAccess] = useState(null);
  const [hostMode, setHostMode] = useState('access');
  const [hostFileName, setHostFileName] = useState('');
  const [hostName, setHostName] = useState('');
  const [hostTrainer, setHostTrainer] = useState('Player');
  const hostInput = useRef(null);
  const hostFileRequest = useRef(0);
  const [worldName, setWorldName] = useState('');
  const [soloTrainer, setSoloTrainer] = useState('Player');
  const [soloSeed, setSoloSeed] = useState(null);
  const [soloSeedName, setSoloSeedName] = useState('');
  const [seedLoading, setSeedLoading] = useState(false);
  const seedInput = useRef(null);
  const seedRequest = useRef(0);
  const [worldSearch, setWorldSearch] = useState('');
  const fileRef = useRef(null);
  const invitationRequest = useRef(0);

  useEffect(() => {
    let active = true;
    let refreshing = false;
    let controller = null;
    let timeout = null;
    const refresh = async () => {
      if (refreshing) return;
      refreshing = true;
      controller = new AbortController();
      let timedOut = false;
      timeout = setTimeout(() => { timedOut = true; controller.abort(); }, 8000);
      try {
        const next = await loadState({ signal: controller.signal });
        if (active) { setState(next); setReady(true); setConnectionError(''); }
      } catch (e) {
        if (active) { setReady(false); setConnectionError(timedOut ? 'The local launcher took too long to respond. Retrying…' : e.message); }
      } finally { clearTimeout(timeout); timeout = null; controller = null; refreshing = false; }
    };
    if (!busy) refresh();
    const timer = setInterval(() => { if (!busy) refresh(); }, 5000);
    return () => { active = false; clearInterval(timer); clearTimeout(timeout); controller?.abort(); };
  }, [busy]);

  // Keep the original opener for the whole dialog chain, not each busy render.
  const dialogOpen = Boolean(dialog);
  useEffect(() => {
    if (!dialogOpen) return;
    const previous = document.activeElement;
    const modal = document.querySelector('[role="dialog"]');
    const onKey = event => {
      if (event.key === 'Escape' && !busyRef.current) { setDialog(null); setError(''); }
      if (event.key !== 'Tab' || !modal) return;
      const controls = [...modal.querySelectorAll('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [href], [tabindex]:not([tabindex="-1"])')].filter(el => el.offsetParent !== null && el.tabIndex >= 0);
      if (!controls.length) { event.preventDefault(); return; }
      const first = controls[0], last = controls[controls.length - 1];
      if (event.shiftKey && (document.activeElement === first || !modal.contains(document.activeElement) || document.activeElement === modal)) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && (document.activeElement === last || !modal.contains(document.activeElement))) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('keydown', onKey); if (previous?.isConnected) previous.focus?.(); };
  }, [dialogOpen]);

  useEffect(() => {
    // Replacing confirmation content invalidates its focused control. Busy changes
    // do not change dialog identity and must leave the player's focus alone.
    if (dialog) document.querySelector('[role="dialog"]')?.focus();
  }, [dialog]);

  useEffect(() => {
    if (!dialog) { invitationRequest.current++; setInvitation(null); setFileName(''); setPasteText(''); setInviteMode('file'); setInviteKind('native'); setInviteFingerprint(''); hostFileRequest.current++; setHostFingerprint(''); setHostAccess(null); setHostFileName(''); setHostMode('access'); seedRequest.current++; setSoloSeed(null); setSoloSeedName(''); setSeedLoading(false); }
  }, [dialog]);

  useEffect(() => {
    if (dialog?.type !== 'share') return;
    const url = dialog.url;
    return () => URL.revokeObjectURL(url);
  }, [dialog]);

  function openCreate() {
    setError('');
    const pending = state.hosting.pending;
    setHostName(pending?.name || ''); setHostTrainer(pending?.trainer || 'Player');
    setDialog('create');
  }

  async function chooseHostAccess(file) {
    const request = ++hostFileRequest.current;
    setHostAccess(null); setHostFileName(''); setHostFingerprint(''); setError('');
    if (!file) return;
    if (!file.size || file.size > 4096) { setError('Choose a host access file no larger than 4 KiB.'); return; }
    try {
      const raw = await file.text();
      if (request !== hostFileRequest.current) return;
      const value = JSON.parse(raw);
      if (!value || value.kind !== (hostMode === 'restore' ? 'host-profile' : 'host-access')) throw new Error();
      setHostAccess(raw); setHostFileName(file.name); setHostFingerprint(typeof value.pin === 'string' && /^[0-9a-fA-F]{64}$/.test(value.pin) ? value.pin.toLowerCase() : '');
    } catch { if (request === hostFileRequest.current) setError(hostMode === 'restore' ? 'That is not a valid owner profile backup.' : 'That is not a valid host access file.'); }
  }

  async function run(action, payload = {}, options = {}) {
    if (busyRef.current) return;
    busyRef.current = true; setBusy(true); setError('');
    setWorkLabel(action === 'author_cave' ? 'Generating and installing cave' : options.disconnectFirst ? 'Closing current session' : options.playAfter ? 'Connecting' : 'Working');
    try {
      if (options.disconnectFirst) {
        const detached = await perform('disconnect', {});
        setState(detached);
        setWorkLabel('Connecting');
      }
      let next = await perform(action, payload);
      if (action === 'quit') {
        forgetCapability(); setState(empty); setReady(false); setDialog(null);
        setError('Launcher closed. You can close this window.'); return;
      }
      let confirmationError = '';
      if (action === 'host_create') {
        try { Object.assign(next, await perform('host_ack', {})); }
        catch { confirmationError = 'Your world connected, but confirmation is pending. Refresh hosted worlds before creating another.'; }
      }
      if (next.download) {
        const url = URL.createObjectURL(new Blob([next.download], { type: 'application/json' }));
        delete next.download;
        const kind = next.download_kind; delete next.download_kind;
        setState(next); setReady(true); setDialog({ type: 'share', url, kind }); return;
      }
      setState(next); setReady(true);
      if (action === 'host_enroll') { setHostAccess(null); setHostFileName(''); setDialog('create'); }
      else setDialog(null);
      if (['join', 'rejoin', 'reconnect', 'offline', 'solo_new', 'solo_resume', 'host_create', 'host_resume', 'host_join', 'host_restore'].includes(action)) setPage('play');
      if (action === 'join') { setInvitation(null); setFileName(''); }
      if (options.playAfter) {
        setWorkLabel('Opening game');
        try {
          next = await perform('launch', {});
          setState(next);
        } catch (launchError) {
          setError(`Your world connected, but the game did not start. ${launchError.message}`);
          return;
        }
      }
      if (confirmationError) setError(confirmationError);
    } catch (e) { setError(e.message); }
    finally { busyRef.current = false; setBusy(false); setWorkLabel('Working'); }
  }

  function requestPlay(action, payload = {}, key = null, options = {}) {
    if (busyRef.current) return;
    const playAfter = options.playAfter !== false;
    if (state.connected && key && state.world_key === key) {
      if (!state.games.includes(state.trainer)) run('launch');
      else setPage('play');
      return;
    }
    if (state.connected || state.games.length) {
      setDialog({ type: 'switch', action, payload, playAfter });
      return;
    }
    run(action, payload, { playAfter });
  }

  function acceptInvitation(raw, label) {
    setInvitation(null); setFileName(''); setInviteFingerprint(''); setError('');
    if (new TextEncoder().encode(raw).length > 4096) { setError('That invitation is too large. Ask your host for a new one.'); return; }
    try {
      const parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error();
      if (parsed.kind === 'host-access') { setError('This is a host access file. Use Create a world to set up your account.'); return; }
      if (parsed.kind && parsed.kind !== 'world-join') throw new Error();
      setInviteKind(parsed.kind === 'world-join' ? 'hosted' : 'native');
      setInviteFingerprint(typeof parsed.pin === 'string' && /^[0-9a-fA-F]{64}$/.test(parsed.pin) ? parsed.pin.toLowerCase() : '');
      setInvitation(raw); setFileName(label);
    } catch { setError('That is not a valid invitation. Ask your host for a new one.'); }
  }

  async function chooseInvitation(file) {
    const request = ++invitationRequest.current;
    setInvitation(null); setFileName(''); setError('');
    if (!file) return;
    if (file.size > 4096) { setError('That invitation is too large. Ask your host for a new one.'); return; }
    try {
      const raw = await file.text();
      if (request === invitationRequest.current) acceptInvitation(raw, file.name);
    } catch { if (request === invitationRequest.current) setError('That file could not be read. Choose it again.'); }
  }

  async function chooseSoloSave(file) {
    const request = ++seedRequest.current;
    setSoloSeed(null); setSoloSeedName(''); setSeedLoading(false); setError('');
    if (!file) return;
    if (!file.size || file.size > 131072) { setError('Choose a nonempty save file no larger than 128 KiB.'); return; }
    setSeedLoading(true);
    try {
      const bytes = new Uint8Array(await file.arrayBuffer());
      if (request !== seedRequest.current) return;
      if (!bytes.length || bytes.length > 131072) throw new Error();
      let binary = '';
      for (let i = 0; i < bytes.length; i += 8192) binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
      setSoloSeed(btoa(binary)); setSoloSeedName(file.name);
    } catch { if (request === seedRequest.current) setError('Could not read that save file. Choose it again.'); }
    finally { if (request === seedRequest.current) setSeedLoading(false); }
  }

  const nav = [
    { id: 'play', label: 'Play', icon: Compass },
    { id: 'worlds', label: 'Your worlds', icon: Globe2 },
    { id: 'backups', label: 'Save backups', icon: ShieldCheck },
    { id: 'settings', label: 'Settings', icon: Settings2 },
  ];
  const orderedWorlds = [...state.worlds].sort((a, b) => Number(b.favorite) - Number(a.favorite) || a.name.localeCompare(b.name));
  const visibleWorlds = orderedWorlds.filter(world => `${world.name} ${world.trainer}`.toLowerCase().includes(worldSearch.trim().toLowerCase()));
  const busyText = busy ? <><LoaderCircle size={15} className="spin" /> {workLabel}…</> : null;
  const go = id => { setPage(id); setMenu(false); setError(''); };

  return <div className="app-shell">
    <aside className={`sidebar ${menu ? 'open' : ''}`} aria-label="Main navigation">
      <div className="brand"><div className="brand-mark"><Leaf size={23} strokeWidth={1.6} /></div><div><span className="eyebrow">A SHARED ADVENTURE</span><strong>EMERALD<span>WORLD</span></strong></div></div>
      <div className="side-label">YOUR JOURNEY</div>
      <nav>{nav.map(({ id, label, icon: Icon }) => <button key={id} className={`nav-item ${page === id ? 'active' : ''}`} onClick={() => go(id)} aria-current={page === id ? 'page' : undefined}><Icon size={19} strokeWidth={1.7} /><span>{label}</span>{page === id && <span className="active-dot" />}</button>)}</nav>
      <div className="sidebar-bottom"><div className="side-illustration"><Sparkles size={16} /><span>One world.<br /><b>Many stories.</b></span></div><div className="connection"><span className={`dot ${state.connected ? 'online' : ''}`} /><span>{state.connected ? 'World session open' : 'Not connected'}</span></div></div>
    </aside>
    {menu && <button className="mobile-scrim" aria-label="Close menu" onClick={() => setMenu(false)} />}
    <main className="main">
      <header className="topbar"><button className="menu-button icon-button" aria-label="Open navigation" onClick={() => setMenu(true)}><Menu size={21} /></button><div className="top-path"><span>EMERALD WORLD</span><span className="slash">/</span><b>{page === 'play' ? 'PLAY' : page === 'worlds' ? 'YOUR WORLDS' : page === 'backups' ? 'SAVE BACKUPS' : page === 'screen' ? 'GAME SCREEN' : 'SETTINGS'}</b></div><div className="top-right">{busyText}<span className={`dot ${state.connected ? 'online' : ''}`} /><span>{state.connected ? 'Session open' : 'No session'}</span></div></header>
      {page === 'play' && <PlayerHome state={state} ready={ready} busy={busy}
        onLocalOpen={(action, payload, key) => requestPlay(action, payload, key, { playAfter: false })}
        onAuthorCave={payload => run('author_cave', payload)}
        onJoin={() => { setError(''); setDialog('join'); }} onCreate={openCreate}
        onSolo={() => { setError(''); setDialog('solo'); }} onWorlds={() => go('worlds')}
        onLaunch={() => run('launch')} onScreen={() => go('screen')} onClose={game => setDialog({ type: 'leave', game })}
        onDisconnect={() => state.games.length ? setDialog('disconnect') : run('disconnect')}
        onReconnect={() => setDialog('reconnect')} onHostRefresh={() => run('host_refresh')}
        onHostInvite={world => run('host_invite', { world: world.id })}
        onInviteOwner={() => setDialog('invite-owner')}
        onBackupOwner={() => setDialog('backup-owner')}
        onPlaySaved={world => requestPlay('rejoin', { world: world.key }, world.key)}
        onPlayHosted={world => requestPlay('host_resume', { world: world.id }, `hosted-${world.id}`)}
        onPlayOffline={save => requestPlay('solo_resume', { world: save.world, trainer: save.trainer }, null, { playAfter: false })} />}
      {page === 'worlds'  && <div className="interior"><button className="back" onClick={() => go('play')}><ArrowLeft size={16} /> Back to play</button><span className="eyebrow gold">YOUR ADVENTURES</span><h1>Worlds worth<br /><em>returning to.</em></h1><p className="lead">Your saved connections live here. Your private trainer progress stays on your device.</p><div className="world-toolbar"><h2>Saved worlds <span className="count">{state.worlds.length}</span></h2><button className="button small primary" onClick={() => { setError(''); setDialog('join'); }} disabled={!ready || busy}><Plus size={16} /> Join a world</button></div>{state.worlds.length > 0 && <label className="world-search"><span className="visually-hidden">Search saved worlds</span><input className="text-input" type="search" value={worldSearch} placeholder="Search worlds or trainers" onChange={event => setWorldSearch(event.target.value)} /></label>}{state.worlds.length ? (visibleWorlds.length ? <div className="world-grid">{visibleWorlds.map((world, i) => <WorldCard key={world.key} world={world} index={i} busy={busy} ready={ready} onContinue={() => requestPlay('rejoin', { world: world.key }, world.key)} onForget={() => setDialog({ type: 'forget', world })} onOffline={() => { setError(''); setDialog({ type: 'offline', world }); }} onRename={() => { setError(''); setWorldName(world.name); setDialog({ type: 'rename', world }); }} onFavorite={() => run('favorite', { world: world.key, favorite: !world.favorite })} />)}</div> : <p className="muted-copy">No worlds match that search.</p>) : <EmptyWorlds onJoin={() => setDialog('join')} ready={ready} />}</div>}
      {page === 'screen' && <GameMirror gameRunning={state.games.length > 0} onBack={() => go('play')} />}
      {page === 'backups' && <SaveBackups state={state} busy={busy} onBack={() => go('play')} />}
      {page === 'settings' && <div className="interior narrow"><button className="back" onClick={() => go('play')}><ArrowLeft size={16} /> Back to play</button><span className="eyebrow gold">THE DETAILS</span><h1>Settings</h1><p className="lead">A little more control, when you need it.</p><div className="settings-card"><div className="settings-icon"><ShieldCheck size={22} /></div><div><h3>Your adventure stays yours</h3><p>Trainer saves stay on this device. Invitations are private credentials, so only import one from a trusted host.</p></div></div><div className="settings-card"><div className="settings-icon"><Settings2 size={22} /></div><div><h3>Game setup</h3><p>Basic checks for the native Linux game. Follow INSTALL_PC.md for installation and troubleshooting.</p><ul className="setup-list">{state.setup.map(item => <li key={item.name}><span className={`dot ${item.ready ? 'online' : 'error-dot'}`} /><span><strong>{item.name}</strong> {item.ready ? 'available' : 'needed'}{!item.ready && <small>{item.help}</small>}</span></li>)}</ul><p>Passing these checks does not guarantee the game will launch.</p></div></div><button className="text-button danger" onClick={() => setDialog('quit')}><DoorOpen size={16} /> Quit launcher</button></div>}
      <footer className="footer"><div><span className={`dot ${ready ? (state.connected ? 'online' : 'idle') : 'error-dot'}`} /> {ready ? state.status : 'Local launcher unavailable'}</div><span>EMERALD WORLD <b>•</b> YOUR ADVENTURE, TOGETHER</span></footer>
    </main>
    {(error || connectionError) && !dialog && <div className="toast" role="alert"><span>{error || connectionError}</span><button aria-label="Dismiss" onClick={() => { setError(''); setConnectionError(''); }}><X size={16} /></button></div>}
    {dialog && <div className="modal-backdrop" onMouseDown={e => { if (e.target === e.currentTarget && !busy) { setDialog(null); setError(''); } }}><section className="modal" role="dialog" tabIndex={-1} aria-modal="true" aria-labelledby="modal-title"><button className="modal-close icon-button" aria-label="Close" onClick={() => { setDialog(null); setError(''); }} disabled={busy}><X size={20} /></button>
      {dialog === 'join' && <><div className="modal-icon"><UsersRound size={22} /></div><span className="eyebrow gold">BETTER TOGETHER</span><h2 id="modal-title">Join a world</h2><p>Choose the private invitation your host shared with you. We’ll use it to connect your trainer securely.</p><div className="invite-tabs" aria-label="Invitation method"><button type="button" aria-pressed={inviteMode === 'file'} onClick={() => { invitationRequest.current++; setInviteMode('file'); setInvitation(null); setFileName(''); setError(''); }}>From a file</button><button type="button" aria-pressed={inviteMode === 'paste'} onClick={() => { invitationRequest.current++; setInviteMode('paste'); setInvitation(null); setFileName(''); setError(''); }}>Paste invitation</button></div>{inviteMode === 'file' ? <><input ref={fileRef} className="visually-hidden" tabIndex={-1} type="file" accept=".json,application/json" onChange={event => { const file = event.target.files?.[0]; event.target.value = ''; chooseInvitation(file); }} /><button className={`upload ${fileName ? 'chosen' : ''} ${dragging ? 'dragging' : ''}`} onClick={() => fileRef.current?.click()} onDragOver={event => { event.preventDefault(); if (!busy) setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={event => { event.preventDefault(); setDragging(false); if (!busy) chooseInvitation(event.dataTransfer.files?.[0]); }} disabled={busy}><span className="upload-icon">{fileName ? <Check size={21} /> : <ArrowDownToLine size={21} />}</span><span><strong>{fileName || 'Choose invitation file'}</strong><small>{fileName ? 'Ready to connect' : 'Drop the file here or browse'}</small></span><ArrowRight size={17} /></button></> : <><label className="field-label" htmlFor="invite-paste">Invitation JSON</label><textarea id="invite-paste" className="text-input invite-paste" maxLength={4096} autoComplete="off" value={pasteText} onChange={event => { invitationRequest.current++; setPasteText(event.target.value); setInvitation(null); setFileName(''); }} placeholder="Paste the invitation shared by your host" spellCheck={false} /><button className="button small ghost paste-confirm" disabled={busy || !pasteText} onClick={() => acceptInvitation(pasteText, 'Pasted invitation')}>{invitation ? 'Invitation ready' : 'Use invitation'}</button></>}{invitation && inviteKind === 'hosted' && <div className="join-trainer"><label className="field-label" htmlFor="join-trainer">Choose your trainer profile</label><input className="text-input" id="join-trainer" value={joinTrainer} maxLength={24} onChange={event => setJoinTrainer(event.target.value)} /><p className="field-hint">Letters, numbers, underscores and hyphens. This invitation binds to one trainer.</p></div>}<div className="security-note"><LockKeyhole size={15} /> Invitations are private. Confirm the server fingerprint with your host through a separate trusted channel.</div>{invitation && inviteFingerprint && <div className="fingerprint"><strong>Server fingerprint</strong><span>{inviteFingerprint}</span></div>}{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" onClick={() => { setDialog(null); setError(''); }} disabled={busy}>Cancel</button><button className="button primary" onClick={() => requestPlay(inviteKind === 'hosted' ? 'host_join' : 'join', inviteKind === 'hosted' ? { invitation, trainer: joinTrainer } : { invitation })} disabled={!invitation || busy || (inviteKind === 'hosted' && !/^[A-Za-z0-9_-]{1,24}$/.test(joinTrainer))}>{busy ? <LoaderCircle size={17} className="spin" /> : <><span>Join and play</span><ArrowRight size={17} /></>}</button></div></>}
      {dialog === 'solo' && <><div className="modal-icon"><Gamepad2 size={22} /></div><span className="eyebrow gold">YOUR OWN ADVENTURE</span><h2 id="modal-title">Play solo</h2><p>Start a new offline adventure without an invitation. Your save stays on this device and is separate from online worlds.</p><label className="field-label" htmlFor="solo-trainer">Trainer profile</label><input className="text-input" id="solo-trainer" maxLength={24} aria-invalid={soloTrainer.length > 0 && !/^[A-Za-z0-9_-]{1,24}$/.test(soloTrainer)} aria-describedby="solo-trainer-help" value={soloTrainer} onChange={event => setSoloTrainer(event.target.value)} /><p className="field-hint" id="solo-trainer-help">Use 1–24 letters, numbers, underscores or hyphens. This labels your local profile.</p><div className="seed-control"><input ref={seedInput} className="visually-hidden" tabIndex={-1} type="file" accept=".sav,application/octet-stream" onChange={event => { const file = event.target.files?.[0]; event.target.value = ''; chooseSoloSave(file); }} /><button className="button small ghost" disabled={busy || seedLoading} onClick={() => seedInput.current?.click()}>{soloSeedName ? 'Change save file' : 'Import an existing save'}</button>{(seedLoading || soloSeedName) && <button className="text-button" onClick={() => { seedRequest.current++; setSoloSeed(null); setSoloSeedName(''); setSeedLoading(false); setError(''); }}>{seedLoading ? 'Cancel import' : 'Remove'}</button>}<span>{seedLoading ? 'Reading save…' : soloSeedName || 'Optional. Your original file is never changed.'}</span></div>{soloSeedName && <p className="field-hint">A separate copy will be used. The game may reject incompatible or damaged saves.</p>}{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" onClick={() => setDialog(null)}>Cancel</button><button className="button primary" disabled={busy || seedLoading || !/^[A-Za-z0-9_-]{1,24}$/.test(soloTrainer)} onClick={() => requestPlay('solo_new', { trainer: soloTrainer, ...(soloSeed ? { seed: soloSeed } : {}) }, null, { playAfter: false })}>Start adventure <ArrowRight size={16} /></button></div></>}
      {dialog === 'create' && <><div className="modal-icon"><Leaf size={22} /></div><span className="eyebrow gold">A NEW ADVENTURE</span><h2 id="modal-title">Create a world</h2>{!state.hosting.available ? <><p>The hosted-world backend is not installed in this version yet. Once it is available, this is where you can create a persistent world on the server.</p><div className="modal-actions"><button className="button primary" onClick={() => setDialog(null)}>Got it</button></div></> : !state.hosting.enrolled ? <><p>{hostMode === 'restore' ? 'Restore an existing owner profile. This never replaces a different account on this device.' : 'Import a private host access file to set up your account. You only need to do this once on this device.'}</p>{state.hosting.backup_available && <div className="invite-tabs"><button type="button" aria-pressed={hostMode === 'access'} onClick={() => { hostFileRequest.current++; setHostMode('access'); setHostAccess(null); setHostFileName(''); setHostFingerprint(''); setError(''); }}>New account</button><button type="button" aria-pressed={hostMode === 'restore'} onClick={() => { hostFileRequest.current++; setHostMode('restore'); setHostAccess(null); setHostFileName(''); setHostFingerprint(''); setError(''); }}>Use backup</button></div>}<input ref={hostInput} className="visually-hidden" tabIndex={-1} type="file" accept=".json,application/json" onChange={event => { const file = event.target.files?.[0]; event.target.value = ''; chooseHostAccess(file); }} /><button className="upload" disabled={busy} onClick={() => hostInput.current?.click()}><span className="upload-icon"><LockKeyhole size={20} /></span><span><strong>{hostFileName || (hostMode === 'restore' ? 'Choose owner profile backup' : 'Choose host access file')}</strong><small>{hostMode === 'restore' ? 'Use your private owner profile backup' : 'Only import access from a trusted host'}</small></span><ArrowRight size={17} /></button><div className="security-note"><LockKeyhole size={15} /> Host access is private. Confirm the server fingerprint with your host through a separate trusted channel.</div>{hostFingerprint && <div className="fingerprint"><strong>Server fingerprint</strong><span>{hostFingerprint}</span></div>}{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" onClick={() => setDialog(null)}>Cancel</button><button className="button primary" disabled={!hostAccess || busy} onClick={() => run(hostMode === 'restore' ? 'host_restore' : 'host_enroll', hostMode === 'restore' ? { profile: hostAccess } : { access: hostAccess })}>{hostMode === 'restore' ? 'Restore account' : 'Set up account'}</button></div></> : <><p>Your world lives on the hosted service, independent of your game. Choose a name and your trainer profile.</p>{state.hosting.pending && <p className="inline-error">{state.hosting.pending.invalid ? 'A previous creation request needs attention before another can be started.' : 'A previous creation may have reached the server. Retry the same request to avoid duplicates.'}</p>}<label className="field-label" htmlFor="host-world-name">World name</label><input className="text-input" id="host-world-name" maxLength={80} value={hostName} readOnly={Boolean(state.hosting.pending)} onChange={event => setHostName(event.target.value)} /><label className="field-label spaced-label" htmlFor="host-trainer">Trainer profile</label><input className="text-input" id="host-trainer" maxLength={24} value={hostTrainer} readOnly={Boolean(state.hosting.pending)} onChange={event => setHostTrainer(event.target.value)} /><p className="field-hint">Profile: letters, numbers, underscores or hyphens. Your save stays on this device.</p>{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" onClick={() => setDialog(null)}>Cancel</button><button className="button ghost" disabled={busy || !hostName.trim() || !/^[A-Za-z0-9_-]{1,24}$/.test(hostTrainer) || state.hosting.pending?.invalid} onClick={() => requestPlay('host_create', { name: hostName, trainer: hostTrainer }, null, { playAfter: false })}>Create only</button><button className="button primary" disabled={busy || !hostName.trim() || !/^[A-Za-z0-9_-]{1,24}$/.test(hostTrainer) || state.hosting.pending?.invalid} onClick={() => requestPlay('host_create', { name: hostName, trainer: hostTrainer })}>{state.hosting.pending ? 'Retry and play' : 'Create and play'}</button></div></>}</>}
      {dialog === 'backup-owner' && <><div className="modal-icon"><LockKeyhole size={22} /></div><span className="eyebrow gold">PROTECT YOUR WORLDS</span><h2 id="modal-title">Back up your owner account?</h2><p>This file contains the private credential that controls your hosted worlds. Anyone with it can manage those worlds. Save it in an encrypted, private place and never share it as a friend invitation.</p><p className="field-hint">Your browser may save it in a regular downloads folder. Player saves and server-world data are not included.</p>{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" onClick={() => setDialog(null)}>Cancel</button><button className="button primary" disabled={busy} onClick={() => run('host_export')}>Create backup</button></div></>}
      {dialog === 'invite-owner' && <><div className="modal-icon"><LockKeyhole size={22} /></div><span className="eyebrow gold">SHARE HOST ACCESS</span><h2 id="modal-title">Invite another owner?</h2><p>This creates a private access file that lets someone set up their own hosted-world account. Only share it with someone you trust. The host may restrict which accounts can issue these invitations.</p>{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" onClick={() => setDialog(null)}>Cancel</button><button className="button primary" disabled={busy} onClick={() => run('host_invite_account')}>Create access file</button></div></>}
      {dialog?.type === 'share' && <><div className="modal-icon"><LockKeyhole size={22} /></div><span className="eyebrow gold">{dialog.kind === 'backup' ? 'OWNER ACCOUNT BACKUP' : dialog.kind === 'owner' ? 'SHARE HOST ACCESS' : 'INVITE A FRIEND'}</span><h2 id="modal-title">{dialog.kind === 'backup' ? 'Your backup is ready' : 'Your invitation is ready'}</h2><p>{dialog.kind === 'backup' ? 'Keep this private account credential somewhere encrypted. Anyone with it can manage your hosted worlds.' : dialog.kind === 'owner' ? 'This private file lets someone set up a hosted-world account. Share it only through a trusted channel.' : 'Download this private invitation and send it to one friend through a trusted channel. It binds to the trainer who redeems it.'}</p><a className="button primary" href={dialog.url} download={dialog.kind === 'backup' ? 'emerald-owner-backup.json' : dialog.kind === 'owner' ? 'emerald-host-access.json' : 'emerald-world-invitation.json'}><ArrowDownToLine size={17} /> {dialog.kind === 'backup' ? 'Download backup' : 'Download invitation'}</a><div className="modal-actions"><button className="button ghost" onClick={() => setDialog(null)}>Done</button></div></>}

      {dialog?.type === 'offline' && <><div className="modal-icon"><Gamepad2 size={22} /></div><span className="eyebrow gold">A SEPARATE ADVENTURE</span><h2 id="modal-title">Play offline</h2><p>Play as <strong>{dialog.world.trainer}</strong> in {dialog.world.name}. Offline progress is kept in a separate save and never merges back into your online world.</p><p>Start a fresh offline save or resume an existing one. You can also make a one-time copy of your online save if no offline save exists yet.</p>{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" disabled={busy} onClick={() => requestPlay('offline', { world: dialog.world.key, copy: true }, null, { playAfter: false })}>Copy online save</button><button className="button primary" disabled={busy} onClick={() => requestPlay('offline', { world: dialog.world.key, copy: false }, null, { playAfter: false })}>Start or resume</button></div></>}
      {dialog?.type === 'leave' && <><div className="modal-icon"><DoorOpen size={22} /></div><span className="eyebrow gold">CLOSE GAME</span><h2 id="modal-title">Finished playing?</h2><p>Save in the game first. Closing it can discard progress since your last save.</p>{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" onClick={() => setDialog(null)}>Keep playing</button><button className="button danger-button" disabled={busy} onClick={() => run('leave', { game: dialog.game })}>Close game</button></div></>}
      {dialog?.type === 'rename' && <><div className="modal-icon"><Leaf size={22} /></div><span className="eyebrow gold">MAKE IT YOURS</span><h2 id="modal-title">Name this world</h2><p>This name is only for your launcher. It won’t change the server or anyone else’s view.</p><label className="field-label" htmlFor="world-name">World name</label><input className="text-input" id="world-name" maxLength={80} value={worldName} onChange={event => setWorldName(event.target.value)} />{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" onClick={() => setDialog(null)}>Cancel</button><button className="button primary" disabled={busy || !worldName.trim()} onClick={() => run('rename', { world: dialog.world.key, label: worldName })}>Save name</button></div></>}
      {dialog?.type === 'forget' && <><div className="modal-icon"><LockKeyhole size={22} /></div><span className="eyebrow gold">SAVED CONNECTION</span><h2 id="modal-title">Forget this world?</h2><p>This removes the saved connection for <strong>{dialog.world.name}</strong>. Your trainer and offline saves stay on this device. You will need a new invitation to access this world here again.</p>{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" onClick={() => setDialog(null)}>Cancel</button><button className="button danger-button" disabled={busy} onClick={() => run('forget', { world: dialog.world.key })}>Forget connection</button></div></>}
      {dialog === 'reconnect' && <><div className="modal-icon"><Globe2 size={22} /></div><span className="eyebrow gold">RETURN TO YOUR WORLD</span><h2 id="modal-title">Reconnect?</h2><p>This closes games started by the launcher, then reconnects using your saved invitation. Save in the game first. Interrupted battles or trades are not restored automatically.</p>{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" onClick={() => setDialog(null)}>Cancel</button><button className="button primary" disabled={busy} onClick={() => run('reconnect', {}, { playAfter: true })}>Reconnect and play</button></div></>}
      {dialog?.type === 'switch' && <><div className="modal-icon"><DoorOpen size={22} /></div><span className="eyebrow gold">SWITCH ADVENTURES</span><h2 id="modal-title">Switch worlds?</h2><p>This disconnects your current world and closes games started by this launcher. Save in the game first. An interrupted battle or trade does not resume automatically.</p>{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" onClick={() => setDialog(null)}>Cancel</button><button className="button primary" disabled={busy} onClick={() => run(dialog.action, dialog.payload, { disconnectFirst: true, playAfter: dialog.playAfter })}>Switch and continue</button></div></>}
      {dialog === 'disconnect' && <><div className="modal-icon"><DoorOpen size={22} /></div><span className="eyebrow gold">DISCONNECT</span><h2 id="modal-title">Disconnect and close games?</h2><p>Disconnecting closes games started by this launcher. Save in the game first. Your remote world keeps running.</p>{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" onClick={() => setDialog(null)}>Keep playing</button><button className="button danger-button" disabled={busy} onClick={() => run('disconnect')}>Disconnect</button></div></>}
      {dialog === 'quit' && <><div className="modal-icon"><DoorOpen size={22} /></div><span className="eyebrow gold">LEAVING HOENN</span><h2 id="modal-title">Quit the launcher?</h2><p>This closes games and local services started by this launcher. Save in the game first. A remote dedicated world keeps running.</p><div className="modal-actions"><button className="button ghost" onClick={() => setDialog(null)}>Cancel</button><button className="button danger-button" onClick={() => run('quit')}>Quit launcher</button></div></>}
    </section></div>}
  </div>;
}

function WorldCard({ world, index, busy, ready, onContinue, onForget, onOffline, onRename, onFavorite }) {
  return <article className="world-card"><div className={`world-art art-${index % 3}`}><span className="world-tag"><Leaf size={13} /> SAVED WORLD</span>{onFavorite && <button className={`favorite-button ${world.favorite ? 'is-favorite' : ''}`} aria-label={world.favorite ? `Remove ${world.name} from favorites` : `Add ${world.name} to favorites`} aria-pressed={Boolean(world.favorite)} disabled={busy || !ready} onClick={onFavorite}><Star size={16} fill={world.favorite ? 'currentColor' : 'none'} /></button>}</div><div className="world-body"><div className="world-icon"><Leaf size={18} /></div><div className="world-info"><h3>{world.name}</h3><p>Trainer <strong>{world.trainer}</strong></p></div><button className="button small primary" aria-label={`Play ${world.name}`} disabled={busy || !ready} onClick={onContinue}>Play <ArrowRight size={15} /></button></div>{onRename && <button className="card-forget" disabled={busy || !ready} onClick={onRename}>Rename</button>}{onOffline && <button className="card-forget" disabled={busy || !ready} onClick={onOffline}>Play offline</button>}{onForget && <button className="card-forget" onClick={onForget}>Forget connection</button>}</article>;
}

function EmptyWorlds({ onJoin, ready }) {
  return <div className="empty-worlds"><div className="empty-icon"><Compass size={23} /></div><div><h3>A new story starts here</h3><p>Join a world with an invitation, and it will be waiting here when you return.</p></div><button className="button small ghost" disabled={!ready} onClick={onJoin}>Join a world <ArrowRight size={15} /></button></div>;
}

const root = document.getElementById('root');
if (root) createRoot(root).render(<App />);
