import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ArrowDownToLine, ArrowLeft, ArrowRight, Check, Compass, DoorOpen, Gamepad2, Globe2, Leaf, LoaderCircle, LockKeyhole, Menu, Plus, Settings2, ShieldCheck, Sparkles, UsersRound, X } from 'lucide-react';
import { forgetCapability, loadState, perform } from './api';
import './style.css';

const empty = { worlds: [], setup: [], connected: false, trainer: null, games: [], status: 'Choose a world to begin.' };

function App() {
  const [state, setState] = useState(empty);
  const [ready, setReady] = useState(false);
  const [page, setPage] = useState('play');
  const [dialog, setDialog] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [menu, setMenu] = useState(false);
  const [invitation, setInvitation] = useState(null);
  const [fileName, setFileName] = useState('');
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
      const controls = [...modal.querySelectorAll('button:not(:disabled), input:not(:disabled), [href], [tabindex]:not([tabindex="-1"])')].filter(el => el.offsetParent !== null);
      if (!controls.length) { event.preventDefault(); return; }
      const first = controls[0], last = controls[controls.length - 1];
      if (event.shiftKey && (document.activeElement === first || document.activeElement === modal)) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('keydown', onKey); previous?.focus?.(); };
  }, [dialog, busy]);

  async function run(action, payload = {}) {
    setBusy(true); setError('');
    try {
      const next = await perform(action, payload);
      if (action === 'quit') {
        forgetCapability(); setState(empty); setReady(false); setDialog(null);
        setError('Launcher closed. You can close this window.'); return;
      }
      setState(next); setReady(true); setDialog(null);
      if (action === 'join' || action === 'rejoin') setPage('play');
      if (action === 'join') { setInvitation(null); setFileName(''); }
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  async function chooseInvitation(event) {
    const file = event.target.files?.[0];
    setInvitation(null); setFileName(''); setError('');
    if (!file) return;
    if (file.size > 4096) { setError('That invitation is too large. Ask your host for a new one.'); return; }
    try {
      const raw = await file.text();
      const parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error();
      setInvitation(raw); setFileName(file.name);
    } catch { setError('That file is not a valid invitation. Ask your host for a new one.'); }
  }

  const nav = [
    { id: 'play', label: 'Play', icon: Compass },
    { id: 'worlds', label: 'Your worlds', icon: Globe2 },
    { id: 'settings', label: 'Settings', icon: Settings2 },
  ];
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
        <section className="hero"><div className="hero-shade" /><div className="hero-copy"><div className="hero-kicker"><span className="diamond" /> A WORLD WORTH SHARING</div><h1>Your adventure,<br /><em>together.</em></h1><p>Explore Hoenn with friends. Your trainer, your team, your story.</p><div className="hero-actions"><button className="button primary" onClick={() => { setDialog('join'); setError(''); }} disabled={!ready || busy}><UsersRound size={18} /> Join a world <ArrowRight size={17} /></button><button className="button outline" onClick={() => setDialog('create')}><Plus size={18} /> Create a world</button></div></div><div className="hero-coordinate">HOENN REGION <span>•</span> YOUR NEXT CHAPTER</div></section>
        <section className="worlds-section"><div className="section-heading"><div><span className="eyebrow gold">PICK UP WHERE YOU LEFT OFF</span><h2>Your worlds <span className="count">{state.worlds.length}</span></h2></div><button className="text-button" onClick={() => go('worlds')}>View all <ArrowRight size={15} /></button></div>
          {state.worlds.length ? <div className="world-grid">{state.worlds.slice(0, 3).map((world, i) => <WorldCard key={world.key} world={world} index={i} busy={busy} ready={ready} onContinue={() => run('rejoin', { world: world.key })} />)}</div> : <EmptyWorlds onJoin={() => { setError(''); setDialog('join'); }} ready={ready} />}
        </section>
        <section className="session-strip"><div className="session-icon"><Gamepad2 size={21} /></div><div className="session-copy"><strong>{state.connected ? `Ready as ${state.trainer || 'your trainer'}` : 'Your trainer, your story'}</strong><span>{state.connected ? 'Session open. Launch your game to enter.' : 'Your team, bag and save stay yours wherever you play.'}</span></div><div className="session-actions">{state.connected && <><button className="button small primary" disabled={busy} onClick={() => run('launch')}><Gamepad2 size={16} /> Launch game</button>{state.games.length > 0 && <button className="button small ghost" disabled={busy} onClick={() => setDialog({ type: 'leave', game: state.trainer })}>Leave game</button>}<button className="button small ghost" disabled={busy} onClick={() => state.games.length ? setDialog('disconnect') : run('disconnect')}>Disconnect</button></>}</div></section>
        {state.games.filter(game => game.startsWith('offline/')).map(game => <section className="session-strip" key={game}><div className="session-icon"><Gamepad2 size={21} /></div><div className="session-copy"><strong>Playing offline as {game.slice(8)}</strong><span>Offline progress stays separate from your online save.</span></div><button className="button small ghost" onClick={() => setDialog({ type: 'leave', game })}>Close game</button></section>)}
      </div>}
      {page === 'worlds'  && <div className="interior"><button className="back" onClick={() => go('play')}><ArrowLeft size={16} /> Back to play</button><span className="eyebrow gold">YOUR ADVENTURES</span><h1>Worlds worth<br /><em>returning to.</em></h1><p className="lead">Your saved connections live here. Your private trainer progress stays on your device.</p><div className="world-toolbar"><h2>Saved worlds <span className="count">{state.worlds.length}</span></h2><button className="button small primary" onClick={() => { setError(''); setDialog('join'); }} disabled={!ready || busy}><Plus size={16} /> Join a world</button></div>{state.worlds.length ? <div className="world-grid">{state.worlds.map((world, i) => <WorldCard key={world.key} world={world} index={i} busy={busy} ready={ready} onContinue={() => run('rejoin', { world: world.key })} onForget={() => setDialog({ type: 'forget', world })} onOffline={() => { setError(''); setDialog({ type: 'offline', world }); }} />)}</div> : <EmptyWorlds onJoin={() => setDialog('join')} ready={ready} />}</div>}
      {page === 'settings' && <div className="interior narrow"><button className="back" onClick={() => go('play')}><ArrowLeft size={16} /> Back to play</button><span className="eyebrow gold">THE DETAILS</span><h1>Settings</h1><p className="lead">A little more control, when you need it.</p><div className="settings-card"><div className="settings-icon"><ShieldCheck size={22} /></div><div><h3>Your adventure stays yours</h3><p>Trainer saves stay on this device. Invitations are private credentials, so only import one from a trusted host.</p></div></div><div className="settings-card"><div className="settings-icon"><Settings2 size={22} /></div><div><h3>Game setup</h3><p>Basic checks for the native Linux game. Follow INSTALL_PC.md for installation and troubleshooting.</p><ul className="setup-list">{state.setup.map(item => <li key={item.name}><span className={`dot ${item.ready ? 'online' : 'error-dot'}`} /><span><strong>{item.name}</strong> {item.ready ? 'available' : 'needed'}{!item.ready && <small>{item.help}</small>}</span></li>)}</ul><p>Passing these checks does not guarantee the game will launch.</p></div></div><button className="text-button danger" onClick={() => setDialog('quit')}><DoorOpen size={16} /> Quit launcher</button></div>}
      <footer className="footer"><div><span className={`dot ${ready ? (state.connected ? 'online' : 'idle') : 'error-dot'}`} /> {ready ? state.status : 'Local launcher unavailable'}</div><span>EMERALD WORLD <b>•</b> YOUR ADVENTURE, TOGETHER</span></footer>
    </main>
    {error && !dialog && <div className="toast" role="alert"><span>{error}</span><button aria-label="Dismiss" onClick={() => setError('')}><X size={16} /></button></div>}
    {dialog && <div className="modal-backdrop" onMouseDown={e => { if (e.target === e.currentTarget && !busy) { setDialog(null); setError(''); } }}><section className="modal" role="dialog" tabIndex={-1} aria-modal="true" aria-labelledby="modal-title"><button className="modal-close icon-button" aria-label="Close" onClick={() => { setDialog(null); setError(''); }} disabled={busy}><X size={20} /></button>
      {dialog === 'join' && <><div className="modal-icon"><UsersRound size={22} /></div><span className="eyebrow gold">BETTER TOGETHER</span><h2 id="modal-title">Join a world</h2><p>Choose the private invitation your host shared with you. We’ll use it to connect your trainer securely.</p><input ref={fileRef} className="visually-hidden" type="file" accept=".json,application/json" onChange={chooseInvitation} /><button className={`upload ${fileName ? 'chosen' : ''}`} onClick={() => fileRef.current?.click()} disabled={busy}><span className="upload-icon">{fileName ? <Check size={21} /> : <ArrowDownToLine size={21} />}</span><span><strong>{fileName || 'Choose invitation file'}</strong><small>{fileName ? 'Ready to connect' : 'Select the file sent by your host'}</small></span><ArrowRight size={17} /></button><div className="security-note"><LockKeyhole size={15} /> Only import invitations from someone you trust. Your invitation is private.</div>{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" onClick={() => { setDialog(null); setError(''); }} disabled={busy}>Cancel</button><button className="button primary" onClick={() => run('join', { invitation })} disabled={!invitation || busy}>{busy ? <LoaderCircle size={17} className="spin" /> : <><span>Join world</span><ArrowRight size={17} /></>}</button></div></>}
      {dialog === 'create' && <><div className="modal-icon"><Leaf size={22} /></div><span className="eyebrow gold">A NEW ADVENTURE</span><h2 id="modal-title">Create a world</h2><p>Creating worlds on the hosted service is the direction for Emerald World. The server’s world-creation service isn’t available in this client yet, so this button won’t create a local world by mistake.</p><div className="modal-actions"><button className="button primary" onClick={() => setDialog(null)}>Got it</button></div></>}
      {dialog?.type === 'offline' && <><div className="modal-icon"><Gamepad2 size={22} /></div><span className="eyebrow gold">A SEPARATE ADVENTURE</span><h2 id="modal-title">Play offline</h2><p>Play as <strong>{dialog.world.trainer}</strong> in {dialog.world.name}. Offline progress is kept in a separate save and never merges back into your online world.</p><p>Start a fresh offline save or resume an existing one. You can also make a one-time copy of your online save if no offline save exists yet.</p>{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" disabled={busy} onClick={() => run('offline', { world: dialog.world.key, copy: true })}>Copy online save</button><button className="button primary" disabled={busy} onClick={() => run('offline', { world: dialog.world.key, copy: false })}>Start or resume</button></div></>}
      {dialog?.type === 'leave' && <><div className="modal-icon"><DoorOpen size={22} /></div><span className="eyebrow gold">CLOSE GAME</span><h2 id="modal-title">Finished playing?</h2><p>Save in the game first. Closing it can discard progress since your last save.</p>{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" onClick={() => setDialog(null)}>Keep playing</button><button className="button danger-button" disabled={busy} onClick={() => run('leave', { game: dialog.game })}>Close game</button></div></>}
      {dialog?.type === 'forget' && <><div className="modal-icon"><LockKeyhole size={22} /></div><span className="eyebrow gold">SAVED CONNECTION</span><h2 id="modal-title">Forget this world?</h2><p>This removes the saved connection for <strong>{dialog.world.name}</strong>. Your trainer and offline saves stay on this device. You will need a new invitation to access this world here again.</p>{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" onClick={() => setDialog(null)}>Cancel</button><button className="button danger-button" disabled={busy} onClick={() => run('forget', { world: dialog.world.key })}>Forget connection</button></div></>}
      {dialog === 'disconnect' && <><div className="modal-icon"><DoorOpen size={22} /></div><span className="eyebrow gold">DISCONNECT</span><h2 id="modal-title">Disconnect and close games?</h2><p>Disconnecting closes games started by this launcher. Save in the game first. Your remote world keeps running.</p>{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" onClick={() => setDialog(null)}>Keep playing</button><button className="button danger-button" disabled={busy} onClick={() => run('disconnect')}>Disconnect</button></div></>}
      {dialog === 'quit' && <><div className="modal-icon"><DoorOpen size={22} /></div><span className="eyebrow gold">LEAVING HOENN</span><h2 id="modal-title">Quit the launcher?</h2><p>This closes games and local services started by this launcher. Save in the game first. A remote dedicated world keeps running.</p><div className="modal-actions"><button className="button ghost" onClick={() => setDialog(null)}>Cancel</button><button className="button danger-button" onClick={() => run('quit')}>Quit launcher</button></div></>}
    </section></div>}
  </div>;
}

function WorldCard({ world, index, busy, ready, onContinue, onForget, onOffline }) {
  return <article className="world-card"><div className={`world-art art-${index % 3}`}><span className="world-tag"><Leaf size={13} /> SAVED WORLD</span></div><div className="world-body"><div className="world-icon"><Leaf size={18} /></div><div className="world-info"><h3>{world.name}</h3><p>Trainer <strong>{world.trainer}</strong></p></div><button className="round-button" aria-label={`Connect to ${world.name}`} disabled={busy || !ready} onClick={onContinue}><ArrowRight size={18} /></button></div>{onOffline && <button className="card-forget" disabled={busy || !ready} onClick={onOffline}>Play offline</button>}{onForget && <button className="card-forget" onClick={onForget}>Forget connection</button>}</article>;
}

function EmptyWorlds({ onJoin, ready }) {
  return <div className="empty-worlds"><div className="empty-icon"><Compass size={23} /></div><div><h3>A new story starts here</h3><p>Join a world with an invitation, and it will be waiting here when you return.</p></div><button className="button small ghost" disabled={!ready} onClick={onJoin}>Join a world <ArrowRight size={15} /></button></div>;
}

createRoot(document.getElementById('root')).render(<App />);
