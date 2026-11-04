import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ArrowDownToLine, ArrowLeft, ArrowRight, Check, Compass, DoorOpen, Gamepad2, Globe2, Leaf, LoaderCircle, LockKeyhole, Menu, Plus, Settings2, ShieldCheck, Sparkles, Star, UsersRound, X } from 'lucide-react';
import { forgetCapability, loadState, perform } from './api';
import './style.css';

const empty = { worlds: [], offline_saves: [], presence: null, hosting: { available: false, backup_available: false, enrolled: false, loaded: false, worlds: [], pending: null }, setup: [], connected: false, trainer: null, games: [], status: 'Choose a world to begin.' };

export function App() {
  const [state, setState] = useState(empty);
  const [ready, setReady] = useState(false);
  const [page, setPage] = useState('play');
  const [dialog, setDialog] = useState(null);
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const [error, setError] = useState('');
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

  useEffect(() => {
    let active = true;
    const refresh = async () => {
      try { const next = await loadState(); if (active) { setState(next); setReady(true); } }
      catch (e) { if (active) { setReady(false); setError(e.message); } }
    };
    if (!busy) refresh();
    const timer = setInterval(() => { if (!busy) refresh(); }, 5000);
    return () => { active = false; clearInterval(timer); };
  }, [busy]);

  useEffect(() => {
    if (!dialog) return;
    const previous = document.activeElement;
    const modal = document.querySelector('[role="dialog"]');
    modal?.focus();
    const onKey = event => {
      if (event.key === 'Escape' && !busy) { setDialog(null); setError(''); }
      if (event.key !== 'Tab' || !modal) return;
      const controls = [...modal.querySelectorAll('button:not(:disabled), input:not(:disabled), [href], [tabindex]:not([tabindex="-1"])')].filter(el => el.offsetParent !== null && el.tabIndex >= 0);
      if (!controls.length) { event.preventDefault(); return; }
      const first = controls[0], last = controls[controls.length - 1];
      if (event.shiftKey && (document.activeElement === first || document.activeElement === modal)) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('keydown', onKey); previous?.focus?.(); };
  }, [dialog, busy]);

  useEffect(() => {
    if (!dialog) { setInvitation(null); setFileName(''); setPasteText(''); setInviteMode('file'); setInviteKind('native'); setInviteFingerprint(''); hostFileRequest.current++; setHostFingerprint(''); setHostAccess(null); setHostFileName(''); setHostMode('access'); seedRequest.current++; setSoloSeed(null); setSoloSeedName(''); setSeedLoading(false); }
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

  async function run(action, payload = {}) {
    if (busyRef.current) return;
    busyRef.current = true; setBusy(true); setError('');
    try {
      const next = await perform(action, payload);
      if (action === 'quit') {
        forgetCapability(); setState(empty); setReady(false); setDialog(null);
        setError('Launcher closed. You can close this window.'); return;
      }
      if (action === 'host_create') {
        try { Object.assign(next, await perform('host_ack', {})); }
        catch { setError('Your world connected, but confirmation is pending. Refresh your hosted worlds before creating another.'); }
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
    } catch (e) { setError(e.message); }
    finally { busyRef.current = false; setBusy(false); }
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
    setInvitation(null); setFileName(''); setError('');
    if (!file) return;
    if (file.size > 4096) { setError('That invitation is too large. Ask your host for a new one.'); return; }
    try { acceptInvitation(await file.text(), file.name); }
    catch { setError('That file could not be read. Choose it again.'); }
  }

  async function chooseSoloSave(file) {
    const request = ++seedRequest.current;
    setSoloSeed(null); setSoloSeedName(''); setError('');
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
    { id: 'settings', label: 'Settings', icon: Settings2 },
  ];
  const orderedWorlds = [...state.worlds].sort((a, b) => Number(b.favorite) - Number(a.favorite) || a.name.localeCompare(b.name));
  const visibleWorlds = orderedWorlds.filter(world => `${world.name} ${world.trainer}`.toLowerCase().includes(worldSearch.trim().toLowerCase()));
  const busyText = busy ? <><LoaderCircle size={15} className="spin" /> Working</> : null;
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
      <header className="topbar"><button className="menu-button icon-button" aria-label="Open navigation" onClick={() => setMenu(true)}><Menu size={21} /></button><div className="top-path"><span>EMERALD WORLD</span><span className="slash">/</span><b>{page === 'play' ? 'PLAY' : page === 'worlds' ? 'YOUR WORLDS' : 'SETTINGS'}</b></div><div className="top-right">{busyText}<span className={`dot ${state.connected ? 'online' : ''}`} /><span>{state.connected ? 'Session open' : 'No session'}</span></div></header>
      {page === 'play' && <div className="content">
        <section className="hero"><div className="hero-shade" /><div className="hero-copy"><div className="hero-kicker"><span className="diamond" /> A WORLD WORTH SHARING</div><h1>Your adventure,<br /><em>together.</em></h1><p>Explore Hoenn with friends. Your trainer, your team, your story.</p><div className="hero-actions"><button className="button primary" onClick={() => { setDialog('join'); setError(''); }} disabled={!ready || busy}><UsersRound size={18} /> Join a world <ArrowRight size={17} /></button><button className="button outline" onClick={openCreate}><Plus size={18} /> Create a world</button><button className="button outline" onClick={() => { setError(''); setDialog('solo'); }} disabled={!ready || busy}><Gamepad2 size={18} /> Play solo</button></div></div><div className="hero-coordinate">HOENN REGION <span>•</span> YOUR NEXT CHAPTER</div></section>
        <section className="worlds-section"><div className="section-heading"><div><span className="eyebrow gold">PICK UP WHERE YOU LEFT OFF</span><h2>Your worlds <span className="count">{state.worlds.length}</span></h2></div><button className="text-button" onClick={() => go('worlds')}>View all <ArrowRight size={15} /></button></div>
          {state.worlds.length ? <div className="world-grid">{orderedWorlds.slice(0, 3).map((world, i) => <WorldCard key={world.key} world={world} index={i} busy={busy} ready={ready} onContinue={() => run('rejoin', { world: world.key })} />)}</div> : <EmptyWorlds onJoin={() => { setError(''); setDialog('join'); }} ready={ready} />}
        </section>
        <section className="session-strip"><div className="session-icon"><Gamepad2 size={21} /></div><div className="session-copy"><strong>{state.connected ? `Ready as ${state.trainer || 'your trainer'}` : 'Your trainer, your story'}</strong><span>{state.connected ? 'Session open. Launch your game to enter.' : 'Your team, bag and save stay yours wherever you play.'}</span></div><div className="session-actions">{state.connected && <><button className="button small primary" disabled={busy} onClick={() => run('launch')}><Gamepad2 size={16} /> Launch game</button>{state.games.length > 0 && <button className="button small ghost" disabled={busy} onClick={() => setDialog({ type: 'leave', game: state.trainer })}>Leave game</button>}<button className="button small ghost" disabled={busy} onClick={() => setDialog('reconnect')}>Reconnect</button><button className="button small ghost" disabled={busy} onClick={() => state.games.length ? setDialog('disconnect') : run('disconnect')}>Disconnect</button></>}</div></section>
        {state.hosting.available && state.hosting.enrolled && <section className="worlds-section"><div className="section-heading"><div><span className="eyebrow gold">YOUR HOSTED WORLDS</span><h2>Always there for you</h2></div><div className="host-actions">{state.hosting.backup_available && <button className="text-button" disabled={busy} onClick={() => setDialog('backup-owner')}>Back up account</button>}<button className="text-button" disabled={busy} onClick={() => setDialog('invite-owner')}>Invite an owner</button><button className="text-button" disabled={busy} onClick={() => run('host_refresh')}>Refresh <ArrowRight size={15} /></button></div></div>{state.hosting.worlds.length ? <div className="solo-list">{state.hosting.worlds.map(world => <article className="solo-item" key={world.id}><div className="session-icon"><Globe2 size={20} /></div><div className="session-copy"><strong>{world.name}</strong><span>Owner profile {world.trainer}</span></div><button className="button small ghost" disabled={busy} onClick={() => run('host_invite', { world: world.id })}>Invite friend</button><button className="button small primary" disabled={busy} onClick={() => run('host_resume', { world: world.id })}>Connect</button></article>)}</div> : <p className="muted-copy">{state.hosting.loaded ? 'No hosted worlds yet. Create one to begin.' : 'Refresh to load your hosted worlds.'}</p>}</section>}
        {state.presence && <section className="worlds-section"><div className="section-heading"><div><span className="eyebrow gold">LIVE FROM YOUR GAME</span><h2>Nearby trainers</h2></div><span className="presence-state"><span className={`dot ${state.presence.state === 'connected' ? 'online' : 'error-dot'}`} /> {state.presence.state === 'connected' ? 'Game connected' : state.presence.state === 'disconnected' ? 'Game disconnected' : 'Waiting for game'}</span></div>{state.presence.state === 'connected' ? (state.presence.nearby === null ? <p className="muted-copy">Nearby trainer information is unavailable.</p> : state.presence.nearby.length ? <div className="nearby-list">{state.presence.nearby.map(peer => <div className="nearby-person" key={peer.trainer}><div className="nearby-avatar">{peer.trainer.slice(0, 1).toUpperCase()}</div><div><strong>{peer.trainer}</strong><span>{peer.ready ? 'Available' : 'Busy'}{!peer.rendered ? ' · Not visible on screen' : ''}</span></div></div>)}</div> : <p className="muted-copy">No nearby trainers reported by your game right now.</p>) : <p className="muted-copy">Nearby trainers appear when your running game reports a fresh connection.</p>}</section>}
        {state.offline_saves.length > 0 && <section className="worlds-section"><div className="section-heading"><div><span className="eyebrow gold">YOUR OWN PACE</span><h2>Solo adventures <span className="count">{state.offline_saves.length}</span></h2></div></div><div className="solo-list">{state.offline_saves.map(save => <article className="solo-item" key={`${save.world}/${save.trainer}`}><div className="session-icon"><Gamepad2 size={20} /></div><div className="session-copy"><strong>{save.name}</strong><span>Trainer {save.trainer} · Separate offline save</span></div><button className="button small ghost" disabled={busy} onClick={() => run('solo_resume', { world: save.world, trainer: save.trainer })}>Continue <ArrowRight size={15} /></button></article>)}</div></section>}
        {state.games.filter(game => game.startsWith('offline/')).map(game => <section className="session-strip" key={game}><div className="session-icon"><Gamepad2 size={21} /></div><div className="session-copy"><strong>Playing offline as {game.slice(8)}</strong><span>Offline progress stays separate from your online save.</span></div><button className="button small ghost" onClick={() => setDialog({ type: 'leave', game })}>Close game</button></section>)}
      </div>}
      {page === 'worlds'  && <div className="interior"><button className="back" onClick={() => go('play')}><ArrowLeft size={16} /> Back to play</button><span className="eyebrow gold">YOUR ADVENTURES</span><h1>Worlds worth<br /><em>returning to.</em></h1><p className="lead">Your saved connections live here. Your private trainer progress stays on your device.</p><div className="world-toolbar"><h2>Saved worlds <span className="count">{state.worlds.length}</span></h2><button className="button small primary" onClick={() => { setError(''); setDialog('join'); }} disabled={!ready || busy}><Plus size={16} /> Join a world</button></div>{state.worlds.length > 0 && <label className="world-search"><span className="visually-hidden">Search saved worlds</span><input className="text-input" type="search" value={worldSearch} placeholder="Search worlds or trainers" onChange={event => setWorldSearch(event.target.value)} /></label>}{state.worlds.length ? (visibleWorlds.length ? <div className="world-grid">{visibleWorlds.map((world, i) => <WorldCard key={world.key} world={world} index={i} busy={busy} ready={ready} onContinue={() => run('rejoin', { world: world.key })} onForget={() => setDialog({ type: 'forget', world })} onOffline={() => { setError(''); setDialog({ type: 'offline', world }); }} onRename={() => { setError(''); setWorldName(world.name); setDialog({ type: 'rename', world }); }} onFavorite={() => run('favorite', { world: world.key, favorite: !world.favorite })} />)}</div> : <p className="muted-copy">No worlds match that search.</p>) : <EmptyWorlds onJoin={() => setDialog('join')} ready={ready} />}</div>}
      {page === 'settings' && <div className="interior narrow"><button className="back" onClick={() => go('play')}><ArrowLeft size={16} /> Back to play</button><span className="eyebrow gold">THE DETAILS</span><h1>Settings</h1><p className="lead">A little more control, when you need it.</p><div className="settings-card"><div className="settings-icon"><ShieldCheck size={22} /></div><div><h3>Your adventure stays yours</h3><p>Trainer saves stay on this device. Invitations are private credentials, so only import one from a trusted host.</p></div></div><div className="settings-card"><div className="settings-icon"><Settings2 size={22} /></div><div><h3>Game setup</h3><p>Basic checks for the native Linux game. Follow INSTALL_PC.md for installation and troubleshooting.</p><ul className="setup-list">{state.setup.map(item => <li key={item.name}><span className={`dot ${item.ready ? 'online' : 'error-dot'}`} /><span><strong>{item.name}</strong> {item.ready ? 'available' : 'needed'}{!item.ready && <small>{item.help}</small>}</span></li>)}</ul><p>Passing these checks does not guarantee the game will launch.</p></div></div><button className="text-button danger" onClick={() => setDialog('quit')}><DoorOpen size={16} /> Quit launcher</button></div>}
      <footer className="footer"><div><span className={`dot ${ready ? (state.connected ? 'online' : 'idle') : 'error-dot'}`} /> {ready ? state.status : 'Local launcher unavailable'}</div><span>EMERALD WORLD <b>•</b> YOUR ADVENTURE, TOGETHER</span></footer>
    </main>
    {error && !dialog && <div className="toast" role="alert"><span>{error}</span><button aria-label="Dismiss" onClick={() => setError('')}><X size={16} /></button></div>}
    {dialog && <div className="modal-backdrop" onMouseDown={e => { if (e.target === e.currentTarget && !busy) { setDialog(null); setError(''); } }}><section className="modal" role="dialog" tabIndex={-1} aria-modal="true" aria-labelledby="modal-title"><button className="modal-close icon-button" aria-label="Close" onClick={() => { setDialog(null); setError(''); }} disabled={busy}><X size={20} /></button>
      {dialog === 'join' && <><div className="modal-icon"><UsersRound size={22} /></div><span className="eyebrow gold">BETTER TOGETHER</span><h2 id="modal-title">Join a world</h2><p>Choose the private invitation your host shared with you. We’ll use it to connect your trainer securely.</p><div className="invite-tabs" aria-label="Invitation method"><button type="button" aria-pressed={inviteMode === 'file'} onClick={() => { setInviteMode('file'); setInvitation(null); setFileName(''); setError(''); }}>From a file</button><button type="button" aria-pressed={inviteMode === 'paste'} onClick={() => { setInviteMode('paste'); setInvitation(null); setFileName(''); setError(''); }}>Paste invitation</button></div>{inviteMode === 'file' ? <><input ref={fileRef} className="visually-hidden" tabIndex={-1} type="file" accept=".json,application/json" onChange={event => { const file = event.target.files?.[0]; event.target.value = ''; chooseInvitation(file); }} /><button className={`upload ${fileName ? 'chosen' : ''} ${dragging ? 'dragging' : ''}`} onClick={() => fileRef.current?.click()} onDragOver={event => { event.preventDefault(); if (!busy) setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={event => { event.preventDefault(); setDragging(false); if (!busy) chooseInvitation(event.dataTransfer.files?.[0]); }} disabled={busy}><span className="upload-icon">{fileName ? <Check size={21} /> : <ArrowDownToLine size={21} />}</span><span><strong>{fileName || 'Choose invitation file'}</strong><small>{fileName ? 'Ready to connect' : 'Drop the file here or browse'}</small></span><ArrowRight size={17} /></button></> : <><label className="field-label" htmlFor="invite-paste">Invitation JSON</label><textarea id="invite-paste" className="text-input invite-paste" maxLength={4096} autoComplete="off" value={pasteText} onChange={event => { setPasteText(event.target.value); setInvitation(null); setFileName(''); }} placeholder="Paste the invitation shared by your host" spellCheck={false} /><button className="button small ghost paste-confirm" disabled={busy || !pasteText} onClick={() => acceptInvitation(pasteText, 'Pasted invitation')}>{invitation ? 'Invitation ready' : 'Use invitation'}</button></>}{invitation && inviteKind === 'hosted' && <div className="join-trainer"><label className="field-label" htmlFor="join-trainer">Choose your trainer profile</label><input className="text-input" id="join-trainer" value={joinTrainer} maxLength={24} onChange={event => setJoinTrainer(event.target.value)} /><p className="field-hint">Letters, numbers, underscores and hyphens. This invitation binds to one trainer.</p></div>}<div className="security-note"><LockKeyhole size={15} /> Invitations are private. Confirm the server fingerprint with your host through a separate trusted channel.</div>{invitation && inviteFingerprint && <div className="fingerprint"><strong>Server fingerprint</strong><span>{inviteFingerprint}</span></div>}{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" onClick={() => { setDialog(null); setError(''); }} disabled={busy}>Cancel</button><button className="button primary" onClick={() => run(inviteKind === 'hosted' ? 'host_join' : 'join', inviteKind === 'hosted' ? { invitation, trainer: joinTrainer } : { invitation })} disabled={!invitation || busy || (inviteKind === 'hosted' && !/^[A-Za-z0-9_-]{1,24}$/.test(joinTrainer))}>{busy ? <LoaderCircle size={17} className="spin" /> : <><span>Join world</span><ArrowRight size={17} /></>}</button></div></>}
      {dialog === 'solo' && <><div className="modal-icon"><Gamepad2 size={22} /></div><span className="eyebrow gold">YOUR OWN ADVENTURE</span><h2 id="modal-title">Play solo</h2><p>Start a new offline adventure without an invitation. Your save stays on this device and is separate from online worlds.</p><label className="field-label" htmlFor="solo-trainer">Trainer profile</label><input className="text-input" id="solo-trainer" maxLength={24} value={soloTrainer} onChange={event => setSoloTrainer(event.target.value)} /><p className="field-hint">Letters, numbers, underscores and hyphens. This labels your local profile.</p><div className="seed-control"><input ref={seedInput} className="visually-hidden" tabIndex={-1} type="file" accept=".sav,application/octet-stream" onChange={event => { const file = event.target.files?.[0]; event.target.value = ''; chooseSoloSave(file); }} /><button className="button small ghost" disabled={busy || seedLoading} onClick={() => seedInput.current?.click()}>{soloSeedName ? 'Change save file' : 'Import an existing save'}</button>{soloSeedName && <button className="text-button" onClick={() => { seedRequest.current++; setSoloSeed(null); setSoloSeedName(''); setSeedLoading(false); }}>Remove</button>}<span>{seedLoading ? 'Reading save…' : soloSeedName || 'Optional. Your original file is never changed.'}</span></div>{soloSeedName && <p className="field-hint">A separate copy will be used. The game may reject incompatible or damaged saves.</p>}{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" onClick={() => setDialog(null)}>Cancel</button><button className="button primary" disabled={busy || seedLoading || !soloTrainer.trim()} onClick={() => run('solo_new', { trainer: soloTrainer, ...(soloSeed ? { seed: soloSeed } : {}) })}>Start adventure <ArrowRight size={16} /></button></div></>}
      {dialog === 'create' && <><div className="modal-icon"><Leaf size={22} /></div><span className="eyebrow gold">A NEW ADVENTURE</span><h2 id="modal-title">Create a world</h2>{!state.hosting.available ? <><p>The hosted-world backend is not installed in this version yet. Once it is available, this is where you can create a persistent world on the server.</p><div className="modal-actions"><button className="button primary" onClick={() => setDialog(null)}>Got it</button></div></> : !state.hosting.enrolled ? <><p>{hostMode === 'restore' ? 'Restore an existing owner profile. This never replaces a different account on this device.' : 'Import a private host access file to set up your account. You only need to do this once on this device.'}</p>{state.hosting.backup_available && <div className="invite-tabs"><button type="button" aria-pressed={hostMode === 'access'} onClick={() => { hostFileRequest.current++; setHostMode('access'); setHostAccess(null); setHostFileName(''); setHostFingerprint(''); setError(''); }}>New account</button><button type="button" aria-pressed={hostMode === 'restore'} onClick={() => { hostFileRequest.current++; setHostMode('restore'); setHostAccess(null); setHostFileName(''); setHostFingerprint(''); setError(''); }}>Use backup</button></div>}<input ref={hostInput} className="visually-hidden" tabIndex={-1} type="file" accept=".json,application/json" onChange={event => { const file = event.target.files?.[0]; event.target.value = ''; chooseHostAccess(file); }} /><button className="upload" disabled={busy} onClick={() => hostInput.current?.click()}><span className="upload-icon"><LockKeyhole size={20} /></span><span><strong>{hostFileName || (hostMode === 'restore' ? 'Choose owner profile backup' : 'Choose host access file')}</strong><small>{hostMode === 'restore' ? 'Use your private owner profile backup' : 'Only import access from a trusted host'}</small></span><ArrowRight size={17} /></button><div className="security-note"><LockKeyhole size={15} /> Host access is private. Confirm the server fingerprint with your host through a separate trusted channel.</div>{hostFingerprint && <div className="fingerprint"><strong>Server fingerprint</strong><span>{hostFingerprint}</span></div>}{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" onClick={() => setDialog(null)}>Cancel</button><button className="button primary" disabled={!hostAccess || busy} onClick={() => run(hostMode === 'restore' ? 'host_restore' : 'host_enroll', hostMode === 'restore' ? { profile: hostAccess } : { access: hostAccess })}>{hostMode === 'restore' ? 'Restore account' : 'Set up account'}</button></div></> : <><p>Your world lives on the hosted service, independent of your game. Choose a name and your trainer profile.</p>{state.hosting.pending && <p className="inline-error">{state.hosting.pending.invalid ? 'A previous creation request needs attention before another can be started.' : 'A previous creation may have reached the server. Retry the same request to avoid duplicates.'}</p>}<label className="field-label" htmlFor="host-world-name">World name</label><input className="text-input" id="host-world-name" maxLength={80} value={hostName} readOnly={Boolean(state.hosting.pending)} onChange={event => setHostName(event.target.value)} /><label className="field-label spaced-label" htmlFor="host-trainer">Trainer profile</label><input className="text-input" id="host-trainer" maxLength={24} value={hostTrainer} readOnly={Boolean(state.hosting.pending)} onChange={event => setHostTrainer(event.target.value)} /><p className="field-hint">Profile: letters, numbers, underscores or hyphens. Your save stays on this device.</p>{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" onClick={() => setDialog(null)}>Cancel</button><button className="button primary" disabled={busy || !hostName.trim() || !/^[A-Za-z0-9_-]{1,24}$/.test(hostTrainer) || state.hosting.pending?.invalid} onClick={() => run('host_create', { name: hostName, trainer: hostTrainer })}>{state.hosting.pending ? 'Retry creation' : 'Create and connect'}</button></div></>}</>}
      {dialog === 'backup-owner' && <><div className="modal-icon"><LockKeyhole size={22} /></div><span className="eyebrow gold">PROTECT YOUR WORLDS</span><h2 id="modal-title">Back up your owner account?</h2><p>This file contains the private credential that controls your hosted worlds. Anyone with it can manage those worlds. Save it in an encrypted, private place and never share it as a friend invitation.</p><p className="field-hint">Your browser may save it in a regular downloads folder. Player saves and server-world data are not included.</p>{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" onClick={() => setDialog(null)}>Cancel</button><button className="button primary" disabled={busy} onClick={() => run('host_export')}>Create backup</button></div></>}
      {dialog === 'invite-owner' && <><div className="modal-icon"><LockKeyhole size={22} /></div><span className="eyebrow gold">SHARE HOST ACCESS</span><h2 id="modal-title">Invite another owner?</h2><p>This creates a private access file that lets someone set up their own hosted-world account. Only share it with someone you trust. The host may restrict which accounts can issue these invitations.</p>{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" onClick={() => setDialog(null)}>Cancel</button><button className="button primary" disabled={busy} onClick={() => run('host_invite_account')}>Create access file</button></div></>}
      {dialog?.type === 'share' && <><div className="modal-icon"><LockKeyhole size={22} /></div><span className="eyebrow gold">{dialog.kind === 'backup' ? 'OWNER ACCOUNT BACKUP' : dialog.kind === 'owner' ? 'SHARE HOST ACCESS' : 'INVITE A FRIEND'}</span><h2 id="modal-title">{dialog.kind === 'backup' ? 'Your backup is ready' : 'Your invitation is ready'}</h2><p>{dialog.kind === 'backup' ? 'Keep this private account credential somewhere encrypted. Anyone with it can manage your hosted worlds.' : dialog.kind === 'owner' ? 'This private file lets someone set up a hosted-world account. Share it only through a trusted channel.' : 'Download this private invitation and send it to one friend through a trusted channel. It binds to the trainer who redeems it.'}</p><a className="button primary" href={dialog.url} download={dialog.kind === 'backup' ? 'emerald-owner-backup.json' : dialog.kind === 'owner' ? 'emerald-host-access.json' : 'emerald-world-invitation.json'}><ArrowDownToLine size={17} /> {dialog.kind === 'backup' ? 'Download backup' : 'Download invitation'}</a><div className="modal-actions"><button className="button ghost" onClick={() => setDialog(null)}>Done</button></div></>}

      {dialog?.type === 'offline' && <><div className="modal-icon"><Gamepad2 size={22} /></div><span className="eyebrow gold">A SEPARATE ADVENTURE</span><h2 id="modal-title">Play offline</h2><p>Play as <strong>{dialog.world.trainer}</strong> in {dialog.world.name}. Offline progress is kept in a separate save and never merges back into your online world.</p><p>Start a fresh offline save or resume an existing one. You can also make a one-time copy of your online save if no offline save exists yet.</p>{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" disabled={busy} onClick={() => run('offline', { world: dialog.world.key, copy: true })}>Copy online save</button><button className="button primary" disabled={busy} onClick={() => run('offline', { world: dialog.world.key, copy: false })}>Start or resume</button></div></>}
      {dialog?.type === 'leave' && <><div className="modal-icon"><DoorOpen size={22} /></div><span className="eyebrow gold">CLOSE GAME</span><h2 id="modal-title">Finished playing?</h2><p>Save in the game first. Closing it can discard progress since your last save.</p>{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" onClick={() => setDialog(null)}>Keep playing</button><button className="button danger-button" disabled={busy} onClick={() => run('leave', { game: dialog.game })}>Close game</button></div></>}
      {dialog?.type === 'rename' && <><div className="modal-icon"><Leaf size={22} /></div><span className="eyebrow gold">MAKE IT YOURS</span><h2 id="modal-title">Name this world</h2><p>This name is only for your launcher. It won’t change the server or anyone else’s view.</p><label className="field-label" htmlFor="world-name">World name</label><input className="text-input" id="world-name" maxLength={80} value={worldName} onChange={event => setWorldName(event.target.value)} />{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" onClick={() => setDialog(null)}>Cancel</button><button className="button primary" disabled={busy || !worldName.trim()} onClick={() => run('rename', { world: dialog.world.key, label: worldName })}>Save name</button></div></>}
      {dialog?.type === 'forget' && <><div className="modal-icon"><LockKeyhole size={22} /></div><span className="eyebrow gold">SAVED CONNECTION</span><h2 id="modal-title">Forget this world?</h2><p>This removes the saved connection for <strong>{dialog.world.name}</strong>. Your trainer and offline saves stay on this device. You will need a new invitation to access this world here again.</p>{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" onClick={() => setDialog(null)}>Cancel</button><button className="button danger-button" disabled={busy} onClick={() => run('forget', { world: dialog.world.key })}>Forget connection</button></div></>}
      {dialog === 'reconnect' && <><div className="modal-icon"><Globe2 size={22} /></div><span className="eyebrow gold">RETURN TO YOUR WORLD</span><h2 id="modal-title">Reconnect?</h2><p>This closes games started by the launcher, then reconnects using your saved invitation. Save in the game first. Interrupted battles or trades are not restored automatically.</p>{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" onClick={() => setDialog(null)}>Cancel</button><button className="button primary" disabled={busy} onClick={() => run('reconnect')}>Reconnect</button></div></>}
      {dialog === 'disconnect' && <><div className="modal-icon"><DoorOpen size={22} /></div><span className="eyebrow gold">DISCONNECT</span><h2 id="modal-title">Disconnect and close games?</h2><p>Disconnecting closes games started by this launcher. Save in the game first. Your remote world keeps running.</p>{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" onClick={() => setDialog(null)}>Keep playing</button><button className="button danger-button" disabled={busy} onClick={() => run('disconnect')}>Disconnect</button></div></>}
      {dialog === 'quit' && <><div className="modal-icon"><DoorOpen size={22} /></div><span className="eyebrow gold">LEAVING HOENN</span><h2 id="modal-title">Quit the launcher?</h2><p>This closes games and local services started by this launcher. Save in the game first. A remote dedicated world keeps running.</p><div className="modal-actions"><button className="button ghost" onClick={() => setDialog(null)}>Cancel</button><button className="button danger-button" onClick={() => run('quit')}>Quit launcher</button></div></>}
    </section></div>}
  </div>;
}

function WorldCard({ world, index, busy, ready, onContinue, onForget, onOffline, onRename, onFavorite }) {
  return <article className="world-card"><div className={`world-art art-${index % 3}`}><span className="world-tag"><Leaf size={13} /> SAVED WORLD</span>{onFavorite && <button className={`favorite-button ${world.favorite ? 'is-favorite' : ''}`} aria-label={world.favorite ? `Remove ${world.name} from favorites` : `Add ${world.name} to favorites`} aria-pressed={Boolean(world.favorite)} disabled={busy || !ready} onClick={onFavorite}><Star size={16} fill={world.favorite ? 'currentColor' : 'none'} /></button>}</div><div className="world-body"><div className="world-icon"><Leaf size={18} /></div><div className="world-info"><h3>{world.name}</h3><p>Trainer <strong>{world.trainer}</strong></p></div><button className="round-button" aria-label={`Connect to ${world.name}`} disabled={busy || !ready} onClick={onContinue}><ArrowRight size={18} /></button></div>{onRename && <button className="card-forget" disabled={busy || !ready} onClick={onRename}>Rename</button>}{onOffline && <button className="card-forget" disabled={busy || !ready} onClick={onOffline}>Play offline</button>}{onForget && <button className="card-forget" onClick={onForget}>Forget connection</button>}</article>;
}

function EmptyWorlds({ onJoin, ready }) {
  return <div className="empty-worlds"><div className="empty-icon"><Compass size={23} /></div><div><h3>A new story starts here</h3><p>Join a world with an invitation, and it will be waiting here when you return.</p></div><button className="button small ghost" disabled={!ready} onClick={onJoin}>Join a world <ArrowRight size={15} /></button></div>;
}

const root = document.getElementById('root');
if (root) createRoot(root).render(<App />);
