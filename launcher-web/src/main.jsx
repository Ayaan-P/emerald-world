import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ArrowDownToLine, ArrowLeft, ArrowRight, Check, Compass, DoorOpen, Gamepad2, Globe2, Leaf, LoaderCircle, LockKeyhole, Menu, Plus, Settings2, ShieldCheck, Sparkles, Star, UsersRound, X } from 'lucide-react';
import { forgetCapability, loadState, perform } from './api';
import './style.css';
import SaveBackups from './SaveBackups';
import PlayerHome, { WorldTile } from './PlayerHome';
import ExpeditionPanel from './ExpeditionPanel';
import ControlsHelp from './ControlsHelp';
import CoopGuide from './CoopGuide';
import ReleaseModes from './ReleaseModes';
import { sessionSummary } from './player-state';
import GameMirror from './GameMirror';
import WorldOptions from './WorldOptions';
import WorldJournal from './WorldJournal';
import PersonalSettings from './PersonalSettings';
import LocalFriends from './LocalFriends';
import TerrainEditor from './TerrainEditor';
import ContentWorkshop from './ContentWorkshop';
import { saveImportLimit } from './save-import';

const empty = { local_worlds: [], local_host: false, cave_authoring: false, cave_persistent: false, worlds: [], offline_saves: [], presence: null, hosting: { available: false, backup_available: false, enrolled: false, loaded: false, worlds: [], pending: null }, setup: [], connected: false, world_key: null, offline_world_key: null, trainer: null, games: [], status: 'Choose a world to begin.' };

export function App() {
  const [state, setState] = useState(empty);
  const [ready, setReady] = useState(false);
  const [closed, setClosed] = useState(false);
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
  const [localName, setLocalName] = useState('');
  const [localTrainer, setLocalTrainer] = useState('Player');
  const [soloTrainer, setSoloTrainer] = useState('Player');
  const [soloSeed, setSoloSeed] = useState(null);
  const [soloSeedName, setSoloSeedName] = useState('');
  const [seedLoading, setSeedLoading] = useState(false);
  const seedInput = useRef(null);
  const seedRequest = useRef(0);
  const [worldSearch, setWorldSearch] = useState('');
  const [rulesWorld, setRulesWorld] = useState('');
  const [rulesDirty, setRulesDirty] = useState(false);
  const [personalDirty, setPersonalDirty] = useState(false);
  const [friendsWorld, setFriendsWorld] = useState('');
  const [journalWorld, setJournalWorld] = useState(null);
  const [terrain, setTerrain] = useState(null);
  const [contentWorld, setContentWorld] = useState(null);
  const [terrainDirty, setTerrainDirty] = useState(false);
  const fileRef = useRef(null);
  const invitationRequest = useRef(0);

  useEffect(() => {
    if (closed) return;
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
  }, [busy, closed]);

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
    if (busyRef.current) return false;
    busyRef.current = true; setBusy(true); setError('');
    setWorkLabel(action === 'author_cave' ? 'Generating and installing area' : action === 'activate_area' ? 'Opening saved area or adventure' : options.disconnectFirst ? 'Closing current session' : options.playAfter ? 'Connecting' : 'Working');
    try {
      if (options.disconnectFirst) {
        const detached = await perform('disconnect', {});
        setState(detached);
        setWorkLabel('Opening session');
      }
      let next = await perform(action, payload);
      if (options.responseOnly) return next;
      if (action === 'quit') {
        forgetCapability(); setClosed(true); setState(empty); setReady(false); setDialog(null); return true;
      }
      let confirmationError = '';
      if (action === 'host_create') {
        try { Object.assign(next, await perform('host_ack', {})); }
        catch { confirmationError = 'World creation confirmation is pending. Refresh hosted worlds before creating another.'; }
      }
      if (next.download) {
        const url = URL.createObjectURL(new Blob([next.download], { type: 'application/json' }));
        delete next.download;
        const kind = next.download_kind; delete next.download_kind;
        setState(next); setReady(true); setDialog({ type: 'share', url, kind }); return true;
      }
      setState(next); setReady(true);
      if (action === 'host_enroll') { setHostAccess(null); setHostFileName(''); setDialog('create'); }
      else setDialog(null);
      if (['join', 'rejoin', 'reconnect', 'offline', 'solo_new', 'solo_resume', 'local_create', 'local_resume', 'host_create', 'host_resume', 'host_join', 'host_restore'].includes(action)) setPage(options.returnPage || (['local_create', 'local_resume'].includes(action) && !options.playAfter ? 'explore' : 'play'));
      if (action === 'join') { setInvitation(null); setFileName(''); }
      if (options.playAfter) {
        setWorkLabel('Opening game');
        try {
          next = await perform('launch', {});
          setState(next);
        } catch (launchError) {
          setError(`The session is ready, but the game did not start. ${launchError.message}`);
          return false;
        }
      }
      if (confirmationError) setError(confirmationError);
      return confirmationError ? false : options.returnState ? next : true;
    } catch (e) { setError(e.message); return false; }
    finally { busyRef.current = false; setBusy(false); setWorkLabel('Working'); }
  }

  function requestPlay(action, payload = {}, key = null, options = {}) {
    if (busyRef.current) return;
    const playAfter = options.playAfter !== false;
    if (state.connected && key && state.world_key === key) {
      if (playAfter && !state.games.includes(state.trainer)) run('launch');
      else setPage(options.returnPage || (playAfter ? 'play' : 'explore'));
      return;
    }
    if (state.connected || state.games.length) {
      setDialog({ type: 'switch', action, payload, playAfter, returnPage: options.returnPage });
      return;
    }
    run(action, payload, { playAfter, returnPage: options.returnPage });
  }

  function acceptInvitation(raw, label) {
    setInvitation(null); setFileName(''); setInviteFingerprint(''); setError('');
    if (new TextEncoder().encode(raw).length > 4096) { setError('That invitation is too large. Ask your host for a new one.'); return; }
    try {
      const parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error();
      if (parsed.kind === 'host-access') { setError('This is a host access file. Use Hosted worlds → Add host access to set up your account.'); return; }
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
    const limit = saveImportLimit(state);
    if (!file.size || file.size > limit) { setError(`Choose a nonempty save file no larger than ${limit.toLocaleString()} bytes.`); return; }
    setSeedLoading(true);
    try {
      const bytes = new Uint8Array(await file.arrayBuffer());
      if (request !== seedRequest.current) return;
      if (!bytes.length || bytes.length > limit) throw new Error();
      let binary = '';
      for (let i = 0; i < bytes.length; i += 8192) binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
      setSoloSeed(btoa(binary)); setSoloSeedName(file.name);
    } catch { if (request === seedRequest.current) setError('Could not read that save file. Choose it again.'); }
    finally { if (request === seedRequest.current) setSeedLoading(false); }
  }

  const nav = [
    { id: 'play', label: 'Play', icon: Compass },
    { id: 'local', label: 'Local worlds', icon: Gamepad2 },
    { id: 'worlds', label: 'Hosted worlds', icon: Globe2 },
    { id: 'explore', label: 'Explore', icon: Compass },
    { id: 'help', label: 'Controls & help', icon: UsersRound },
    { id: 'backups', label: 'Save backups', icon: ShieldCheck },
    { id: 'settings', label: 'Settings', icon: Settings2 },
  ];
  const orderedWorlds = [...state.worlds].sort((a, b) => Number(b.favorite) - Number(a.favorite) || a.name.localeCompare(b.name));
  const visibleWorlds = orderedWorlds.filter(world => `${world.name} ${world.trainer}`.toLowerCase().includes(worldSearch.trim().toLowerCase()));
  const busyText = busy ? <><LoaderCircle size={15} className="spin" /> {workLabel}…</> : null;
  const go = (id, world = rulesWorld) => {
    if (busyRef.current) return;
    if (page === 'rules' && rulesDirty && (id !== page || world !== rulesWorld)) {
      setDialog({ type: 'leave-rules', page: id, world }); return;
    }
    if (page === 'settings' && personalDirty && id !== page) {
      setDialog({ type: 'leave-personal', page: id }); return;
    }
    if (page === 'terrain' && terrainDirty && id !== page) {
      setDialog({ type: 'leave-terrain', page: id }); return;
    }
    setRulesWorld(world); setPage(id); setMenu(false);
  };
  const session = sessionSummary(state);
  const navPage = ['rules', 'friends', 'journal'].includes(page) ? 'local' : page === 'terrain' ? 'explore' : page;
  const pageLabel = nav.find(item => item.id === page)?.label || (page === 'journal' ? 'World journal' : page === 'rules' ? 'World options' : page === 'friends' ? 'Invite friends' : page === 'terrain' ? 'Edit terrain' : 'In-page preview');
  const localWorlds = state.local_worlds || [];
  const localOpen = (action, payload, key, options = {}) => requestPlay(action, payload, key, { playAfter: false, ...options });
  const openLocal = () => { setLocalName(''); setError(''); setDialog('local'); };
  const openSolo = () => { setError(''); setDialog('solo'); };
  const playSolo = save => requestPlay('solo_resume', { world: save.world, trainer: save.trainer }, null, { playAfter: false });

  return <div className="app-shell">
    <aside className={`sidebar ${menu ? 'open' : ''}`} aria-label="Main navigation">
      <div className="brand"><div className="brand-mark"><Leaf size={23} strokeWidth={1.6} /></div><div><span className="eyebrow">NATIVE PC</span><strong>EMERALD<span>WORLD</span></strong></div></div>
      <div className="side-label">LIBRARY</div>
      <nav>{nav.map(({ id, label, icon: Icon }) => <button key={id} className={`nav-item ${navPage === id ? 'active' : ''}`} onClick={() => go(id)} aria-current={navPage === id ? 'page' : undefined}><Icon size={19} strokeWidth={1.7} /><span>{label}</span>{navPage === id && <span className="active-dot" />}</button>)}</nav>
      <div className="sidebar-bottom"><div className="host-indicator">{state.local_hosts?.length > 0 && <button className="text-button" onClick={() => go('local')}>{state.local_hosts.length} local {state.local_hosts.length === 1 ? 'host' : 'hosts'} running</button>}</div><div className="engine-badge"><span className="dot idle" />{state.engine === 'expansion-native' ? 'Expansion' : 'Emerald'}</div><div className="connection"><span className={`dot ${!ready || session.tone === 'error' ? 'error-dot' : session.tone}`} /><span>{closed ? 'Launcher closed' : ready ? session.status : 'Launcher unavailable'}</span></div></div>
    </aside>
    {menu && <button className="mobile-scrim" aria-label="Close menu" onClick={() => setMenu(false)} />}
    <main className="main">
      <header className="topbar"><button className="menu-button icon-button" aria-label="Open navigation" onClick={() => setMenu(true)}><Menu size={21} /></button><div className="top-path"><span>EMERALD WORLD</span><span className="slash">/</span><b>{pageLabel}</b></div><div className="top-right">{busyText || <><span className={`dot ${ready ? 'idle' : 'error-dot'}`} /><span>{closed ? 'Launcher closed' : ready ? 'Launcher ready' : 'Connecting to launcher'}</span></>}</div></header>
      {closed && <section className="launcher-notice" role="status"><strong>Launcher closed.</strong> You can close this tab.</section>}
      {(error || connectionError) && !dialog && <section className="launcher-alert" role="alert"><div><strong>{error ? 'Action could not finish' : 'Launcher connection unavailable'}</strong><p>{error || connectionError}</p>{error && connectionError && <p>{connectionError}</p>}</div>{error && <button className="icon-button" aria-label="Dismiss error" onClick={() => setError('')}><X size={18} /></button>}</section>}
      {page === 'play' && <PlayerHome state={state} ready={ready} busy={busy}
        onLocalOpen={localOpen}
        onJoin={() => { setError(''); setDialog('join'); }} onCreate={openLocal} onLocal={() => go('local')} onExplore={() => go('explore')} onHelp={() => go('help')}
        onSolo={openSolo} onWorlds={() => go('worlds')}
        onLaunch={() => run('launch')} onScreen={() => go('screen')} onClose={game => setDialog({ type: 'leave', game })}
        onDisconnect={() => state.games.length ? setDialog('disconnect') : run('disconnect')}
        onReconnect={() => setDialog('reconnect')}
        onPlaySaved={world => requestPlay('rejoin', { world: world.key }, world.key)}
        onPlayHosted={world => requestPlay('host_resume', { world: world.id }, `hosted-${world.id}`)}
        onPlayOffline={playSolo} />}
      {page === 'worlds' && <div className="interior">
        <header className="page-heading"><div><h1>Hosted worlds</h1><p>Dedicated servers, including Hetzner. Your trainer save stays here.</p></div><button className="button primary" onClick={() => { setError(''); setDialog('join'); }} disabled={!ready || busy}>Join a world</button></header>
        <section className="hosting-summary" aria-label="Hosting account"><div><h2>{!state.hosting.available ? 'Hosting management unavailable' : state.hosting.enrolled ? 'Owner account configured' : 'Add hosting access'}</h2><p>{!state.hosting.available ? 'You can still join an existing server with a player invitation.' : state.hosting.enrolled ? (state.hosting.endpoint ? `${state.hosting.endpoint.host}:${state.hosting.endpoint.port}` : 'Create worlds and invite players on your configured service.') : 'Import host access from your server operator, or restore your owner backup.'}</p></div><button className="button ghost" disabled={!ready || busy || !state.hosting.available} onClick={openCreate}>{state.hosting.enrolled ? 'Create hosted world' : 'Add host access'}</button></section>
        {state.hosting.available && state.hosting.enrolled && <section className="worlds-section"><div className="section-heading"><h2>Owned by you</h2><button className="text-button" disabled={!ready || busy} onClick={() => run('host_refresh')}>{state.hosting.loaded ? 'Refresh' : 'Load worlds'}</button></div>{state.hosting.worlds.length ? <div className="save-list">{state.hosting.worlds.map(world => <WorldTile key={world.id} title={world.name} subtitle={`Hosted · ${world.trainer}`} disabled={!ready || busy} playing={Boolean(session.running && state.world_key === `hosted-${world.id}`)} onPlay={() => requestPlay('host_resume', { world: world.id }, `hosted-${world.id}`)} onInvite={() => run('host_invite', { world: world.id })} />)}</div> : <p className="muted-copy">{state.hosting.loaded ? 'No owned worlds.' : 'Load worlds to check your server.'}</p>}<details className="account-tools"><summary>Owner account</summary><div className="host-actions">{state.hosting.backup_available && <button className="text-button" disabled={!ready || busy} onClick={() => setDialog('backup-owner')}>Back up account</button>}<button className="text-button" disabled={!ready || busy} onClick={() => setDialog('invite-owner')}>Invite an owner</button></div></details></section>}
        <div className="world-toolbar"><h2>Saved connections <span className="count">{state.worlds.length}</span></h2></div>{state.worlds.length > 0 && <label className="world-search"><span className="visually-hidden">Search saved worlds</span><input className="text-input" type="search" value={worldSearch} placeholder="Search worlds or trainers" onChange={event => setWorldSearch(event.target.value)} /></label>}{state.worlds.length ? (visibleWorlds.length ? <div className="world-grid">{visibleWorlds.map((world, i) => <WorldCard key={world.key} world={world} index={i} busy={busy} ready={ready} onContinue={() => requestPlay('rejoin', { world: world.key }, world.key)} onForget={() => setDialog({ type: 'forget', world })} onOffline={() => { setError(''); setDialog({ type: 'offline', world }); }} onRename={() => { setError(''); setWorldName(world.name); setDialog({ type: 'rename', world }); }} onFavorite={() => run('favorite', { world: world.key, favorite: !world.favorite })} />)}</div> : <p className="muted-copy">No worlds match that search.</p>) : <EmptyWorlds onJoin={() => setDialog('join')} ready={ready} />}</div>}
      {page === 'local' && <div className="interior"><header className="page-heading"><div><h1>Local worlds</h1><p>Worlds and saves on this computer.</p></div><button className="button primary" disabled={!ready || busy} onClick={openLocal}><Plus size={16} /> Create local world</button></header><section className="worlds-section"><div className="section-heading"><h2>Local worlds</h2><button className="text-button" onClick={() => go('explore')}>Generated areas <ArrowRight size={15} /></button></div>{localWorlds.length ? <div className="save-list">{localWorlds.map(world => <div key={world.key}><WorldTile title={world.name} subtitle={`Local · ${world.trainer} · ${state.local_hosts?.includes(world.key) ? 'Host running' : 'Host stopped'}`} disabled={!ready || busy || !world.trainer} playing={session.running && state.world_key === world.key} onPlay={() => localOpen('local_resume', { world: world.key, trainer: world.trainer }, world.key, { playAfter: true })} />{state.engine === 'expansion-native' && <button className="text-button local-options" disabled={!ready || busy} onClick={() => { setContentWorld(world.key); go('content'); }}>Author content</button>}<button className="text-button local-options" disabled={!ready || busy} onClick={() => go('rules', world.key)}>World options</button><button className="text-button local-options" disabled={!ready || busy} onClick={() => { setJournalWorld(world.key); go('journal'); }}>World journal</button><button className="text-button local-options" disabled={!ready || busy} onClick={() => { setFriendsWorld(world.key); go('friends'); }}>Invite friends</button>{state.local_hosts?.includes(world.key) && <button className="text-button stop-host" disabled={!ready || busy} onClick={() => setDialog({ type: 'stop-local', world })}>Stop host</button>}</div>)}</div> : <p className="muted-copy">No local worlds yet.</p>}<p className="field-hint">Local hosting stops when the launcher quits. Creating a world does not publish an Internet server.</p></section><section className="worlds-section"><div className="section-heading"><h2>Solo saves</h2><button className="text-button" disabled={!ready || busy} onClick={openSolo}>New solo save <Plus size={15} /></button></div>{state.offline_saves.length ? <div className="save-list">{state.offline_saves.map(save => <WorldTile key={`${save.world}/${save.trainer}`} title={save.name} subtitle={`Solo · ${save.trainer}`} disabled={!ready || busy} playing={session.running && session.game === `offline/${save.trainer}` && state.offline_world_key === save.world} onPlay={() => playSolo(save)} />)}</div> : <p className="muted-copy">Offline play without a world server. Solo progress is separate from multiplayer.</p>}</section></div>}
      {page === 'friends' && <LocalFriends key={friendsWorld} state={state} worldKey={friendsWorld} ready={ready} busy={busy}
        onBack={() => go('local')} onOpen={world => localOpen('local_resume', { world: world.key, trainer: world.trainer }, world.key, { returnPage: 'friends' })}
        onAction={run} />}
      {page === 'content' && <ContentWorkshop key={contentWorld} world={localWorlds.find(w => w.key === contentWorld)} available={state.local_hosts?.includes(contentWorld)} ready={ready} busy={busy} onBack={() => go('local')} onOpen={world => localOpen('local_resume', { world: world.key, trainer: world.trainer }, world.key, { returnPage: 'content' })} onRequest={(action, payload) => run(action, payload, { responseOnly: true })} />}
      {page === 'journal' && <WorldJournal key={journalWorld} world={localWorlds.find(w => w.key === journalWorld)} available={state.local_hosts?.includes(journalWorld)} ready={ready} busy={busy}
        onBack={() => go('local')} onOpen={world => localOpen('local_resume', { world: world.key, trainer: world.trainer }, world.key, { returnPage: 'journal' })}
        onRequest={(action, payload) => run(action, payload, { responseOnly: true })} />}
      {page === 'rules' && <WorldOptions key={rulesWorld} state={state} worldKey={rulesWorld} ready={ready} busy={busy}
        onChoose={key => go('rules', key)} onBack={() => go('local')} onDirtyChange={setRulesDirty}
        onOpen={world => localOpen('local_resume', { world: world.key, trainer: world.trainer }, world.key, { returnPage: 'rules' })}
        onSave={payload => run('rules_replace', payload, { returnState: true })}
        onRefresh={() => run('rules_refresh', {}, { returnState: true })} />}
      {page === 'explore' && <div className="interior"><header className="page-heading"><div><h1>Explore</h1><p>Generate and choose areas for a local world or an owned hosted world.</p></div><button className="text-button" onClick={() => go('play')}>Back to play <ArrowRight size={15} /></button></header>{state.local_host && <div className="library-actions"><button className="button primary" disabled={!ready || busy || session.running} onClick={() => run('launch')}>{session.running ? 'Game running' : 'Play now'}</button><button className="text-button" disabled={!ready || busy} onClick={() => state.games.length ? setDialog('disconnect') : run('disconnect')}>Disconnect</button></div>}<ExpeditionPanel state={state} ready={ready} busy={busy} onOpen={localOpen} onSelectHostedArea={world => run('host_select_area', { world: world.id })} onRefreshHosted={() => run('host_refresh')} onHostedWorlds={() => go('worlds')} onInspect={state.local_host && !state.hosted_area_world ? payload => run('inspect_area', payload, { responseOnly: true }) : undefined} onEditTerrain={state.local_host && !state.hosted_area_world ? area => { setTerrain({ world: state.world_key, area }); go('terrain'); } : undefined} onAuthor={payload => run('author_cave', payload)} onActivate={payload => run('activate_area', payload)} /></div>}
      {page === 'terrain' && terrain && <TerrainEditor key={`${terrain.world}/${terrain.area.identity}`} world={terrain.world} area={terrain.area} ready={ready} busy={busy} available={state.local_host && state.world_key === terrain.world && state.generated_areas?.some(area => area.identity === terrain.area.identity && area.active)} onRequest={(action, payload) => run(action, payload, { responseOnly: true })} onBack={() => go('explore')} onDirtyChange={setTerrainDirty} />}
      {page === 'help' && <div className="interior help-page"><header className="page-heading"><div><h1>Controls & help</h1><p>Play in the native game window.</p></div></header><div className="quick-controls"><span><kbd>↑ ↓ ← →</kbd> Move</span><span><kbd>Z</kbd> Confirm</span><span><kbd>X</kbd> Back</span><span><kbd>Enter</kbd> Menu</span><span><kbd>T</kbd> Chat</span></div><ControlsHelp engine={state.engine} /><CoopGuide /><details className="controls-help"><summary>WORLD menu</summary><dl><div><dt>Fly to a friend</dt><dd>Feather Badge and Fly required</dd></div><div><dt>Guilds</dt><dd>Chat and group goals</dd></div><div><dt>Story rally</dt><dd>Roxanne group visit</dd></div><div><dt>DexNav</dt><dd>Pokémon search</dd></div></dl><p>On hosts with world rules, the host chooses wild shuffle for everyone. Other builds use the game’s launch-local shuffle setting. Shuffle covers ordinary encounters from the first 386 species, not every encounter.</p><p>Guild expeditions are map-visit goals, separate from generated caves. Story progress stays personal.</p></details><section className="settings-card"><div><h3>Saves and recovery</h3><p>Save from the game menu before quitting. Reconnect closes the game and returns to your last save; interrupted battles and trades cannot resume.</p><p>Each trainer has separate progress. Solo saves never merge back into a multiplayer save.</p></div></section><ReleaseModes /></div>}
      {page === 'screen' && <GameMirror gameRunning={state.games.length > 0} onBack={() => go('play')} />}
      {page === 'backups' && <SaveBackups state={state} busy={busy} onBack={() => go('play')} />}
      {page === 'settings' && <div className="interior narrow"><button className="back" onClick={() => go('play')}><ArrowLeft size={16} /> Back to play</button><span className="eyebrow gold">SETUP</span><h1>Settings</h1><p className="lead">Native game setup.</p>{!closed && <PersonalSettings ready={ready} busy={busy} onDirtyChange={setPersonalDirty} onRequest={(action, payload) => action === 'personal_settings_save' ? run(action, payload, { responseOnly: true }) : perform(action, payload)} />}<div className="settings-card"><div className="settings-icon"><ShieldCheck size={22} /></div><div><h3>Private saves</h3><p>Trainer saves stay on this device. Invitations are private credentials, so only import one from a trusted host.</p></div></div><div className="settings-card"><div className="settings-icon"><Settings2 size={22} /></div><div><h3>Game setup</h3><p>Native Linux prerequisites. Shared gameplay options are under Local worlds → World options. Display and keyboard settings above apply to the selected Expansion profile on its next launch.</p><ul className="setup-list">{state.setup.map(item => <li key={item.name}><span className={`dot ${item.ready ? 'online' : 'error-dot'}`} /><span><strong>{item.name}</strong> {item.ready ? 'available' : 'needed'}{!item.ready && <small>{item.help}</small>}</span></li>)}</ul><p>These checks do not test a server connection.</p></div></div><button className="text-button danger" disabled={!ready || busy} onClick={() => setDialog('quit')}><DoorOpen size={16} /> Quit launcher</button></div>}
      <footer className="footer"><div><span className={`dot ${!ready || session.tone === 'error' ? 'error-dot' : session.tone}`} /> {closed ? 'Launcher closed' : ready ? session.status : 'Local launcher unavailable'}</div><span>Save in the game before quitting.</span></footer>
    </main>
    {dialog && <div className="modal-backdrop" onMouseDown={e => { if (e.target === e.currentTarget && !busy) { setDialog(null); setError(''); } }}><section className="modal" role="dialog" tabIndex={-1} aria-modal="true" aria-labelledby="modal-title">{connectionError && <p className="inline-error" role="alert">{connectionError}</p>}<button className="modal-close icon-button" aria-label="Close" onClick={() => { setDialog(null); setError(''); }} disabled={busy}><X size={20} /></button>
      {dialog?.type === 'stop-local' && <><h2 id="modal-title">Stop {dialog.world.name}?</h2><p>This stops this local world and disconnects its players. Save in the game first. The world and trainer saves are kept.</p>{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" disabled={busy} onClick={() => setDialog(null)}>Cancel</button><button className="button danger-button" disabled={busy} onClick={() => run('local_stop', { world: dialog.world.key })}>Stop host</button></div></>}
      {dialog === 'local' && <><div className="modal-icon"><Gamepad2 size={22} /></div><h2 id="modal-title">Create local world</h2><p>Runs on this computer with a separate trainer save.</p><label className="field-label" htmlFor="local-name">World name</label><input className="text-input" id="local-name" maxLength={80} value={localName} onChange={event => setLocalName(event.target.value)} /><label className="field-label spaced-label" htmlFor="local-trainer">Trainer profile</label><input className="text-input" id="local-trainer" maxLength={24} value={localTrainer} onChange={event => setLocalTrainer(event.target.value)} /><p className="field-hint">1–24 letters, numbers, underscores or hyphens.</p>{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" disabled={busy} onClick={() => setDialog(null)}>Cancel</button><button className="button ghost" disabled={busy || !localName.trim() || /[\x00-\x1f]/.test(localName) || !/^[A-Za-z0-9_-]{1,24}$/.test(localTrainer)} onClick={() => localOpen('local_create', { name: localName, trainer: localTrainer })}>Set up areas first</button><button className="button primary" disabled={busy || !localName.trim() || /[\x00-\x1f]/.test(localName) || !/^[A-Za-z0-9_-]{1,24}$/.test(localTrainer)} onClick={() => localOpen('local_create', { name: localName, trainer: localTrainer }, null, { playAfter: true })}>Create and play</button></div></>}
      {dialog === 'join' && <><div className="modal-icon"><UsersRound size={22} /></div><span className="eyebrow gold">HOSTED WORLD</span><h2 id="modal-title">Join a world</h2><p>Choose the private invitation your host shared with you. Use a matching client version.</p><div className="invite-tabs" aria-label="Invitation method"><button type="button" aria-pressed={inviteMode === 'file'} onClick={() => { invitationRequest.current++; setInviteMode('file'); setInvitation(null); setFileName(''); setError(''); }}>From a file</button><button type="button" aria-pressed={inviteMode === 'paste'} onClick={() => { invitationRequest.current++; setInviteMode('paste'); setInvitation(null); setFileName(''); setError(''); }}>Paste invitation</button></div>{inviteMode === 'file' ? <><input ref={fileRef} className="visually-hidden" tabIndex={-1} type="file" accept=".json,application/json" onChange={event => { const file = event.target.files?.[0]; event.target.value = ''; chooseInvitation(file); }} /><button className={`upload ${fileName ? 'chosen' : ''} ${dragging ? 'dragging' : ''}`} onClick={() => fileRef.current?.click()} onDragOver={event => { event.preventDefault(); if (!busy) setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={event => { event.preventDefault(); setDragging(false); if (!busy) chooseInvitation(event.dataTransfer.files?.[0]); }} disabled={busy}><span className="upload-icon">{fileName ? <Check size={21} /> : <ArrowDownToLine size={21} />}</span><span><strong>{fileName || 'Choose invitation file'}</strong><small>{fileName ? 'Ready to connect' : 'Drop the file here or browse'}</small></span><ArrowRight size={17} /></button></> : <><label className="field-label" htmlFor="invite-paste">Invitation JSON</label><textarea id="invite-paste" className="text-input invite-paste" maxLength={4096} autoComplete="off" value={pasteText} onChange={event => { invitationRequest.current++; setPasteText(event.target.value); setInvitation(null); setFileName(''); }} placeholder="Paste the invitation shared by your host" spellCheck={false} /><button className="button small ghost paste-confirm" disabled={busy || !pasteText} onClick={() => acceptInvitation(pasteText, 'Pasted invitation')}>{invitation ? 'Invitation ready' : 'Use invitation'}</button></>}{invitation && inviteKind === 'hosted' && <div className="join-trainer"><label className="field-label" htmlFor="join-trainer">Choose your trainer profile</label><input className="text-input" id="join-trainer" value={joinTrainer} maxLength={24} onChange={event => setJoinTrainer(event.target.value)} /><p className="field-hint">Letters, numbers, underscores and hyphens. This invitation binds to one trainer.</p></div>}<div className="security-note"><LockKeyhole size={15} /> Invitations are private. Confirm the server fingerprint with your host through a separate trusted channel.</div>{invitation && inviteFingerprint && <div className="fingerprint"><strong>Server fingerprint</strong><span>{inviteFingerprint}</span></div>}{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" onClick={() => { setDialog(null); setError(''); }} disabled={busy}>Cancel</button><button className="button primary" onClick={() => requestPlay(inviteKind === 'hosted' ? 'host_join' : 'join', inviteKind === 'hosted' ? { invitation, trainer: joinTrainer } : { invitation })} disabled={!invitation || busy || (inviteKind === 'hosted' && !/^[A-Za-z0-9_-]{1,24}$/.test(joinTrainer))}>{busy ? <LoaderCircle size={17} className="spin" /> : <><span>Join and play</span><ArrowRight size={17} /></>}</button></div></>}
      {dialog === 'solo' && <><div className="modal-icon"><Gamepad2 size={22} /></div><span className="eyebrow gold">OFFLINE</span><h2 id="modal-title">Play solo</h2><p>Start a new offline adventure without an invitation. Your save stays on this device and is separate from online worlds.</p><label className="field-label" htmlFor="solo-trainer">Trainer profile</label><input className="text-input" id="solo-trainer" maxLength={24} aria-invalid={soloTrainer.length > 0 && !/^[A-Za-z0-9_-]{1,24}$/.test(soloTrainer)} aria-describedby="solo-trainer-help" value={soloTrainer} onChange={event => setSoloTrainer(event.target.value)} /><p className="field-hint" id="solo-trainer-help">Use 1–24 letters, numbers, underscores or hyphens. This labels your local profile.</p><div className="seed-control"><input ref={seedInput} className="visually-hidden" tabIndex={-1} type="file" accept=".sav,application/octet-stream" onChange={event => { const file = event.target.files?.[0]; event.target.value = ''; chooseSoloSave(file); }} /><button className="button small ghost" disabled={busy || seedLoading} onClick={() => seedInput.current?.click()}>{soloSeedName ? 'Change save file' : 'Import an existing save'}</button>{(seedLoading || soloSeedName) && <button className="text-button" onClick={() => { seedRequest.current++; setSoloSeed(null); setSoloSeedName(''); setSeedLoading(false); setError(''); }}>{seedLoading ? 'Cancel import' : 'Remove'}</button>}<span>{seedLoading ? 'Reading save…' : soloSeedName || 'Optional. Your original file is never changed.'}</span></div>{soloSeedName && <p className="field-hint">A separate copy will be used. The game may reject incompatible or damaged saves.</p>}{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" disabled={busy} onClick={() => setDialog(null)}>Cancel</button><button className="button primary" disabled={busy || seedLoading || !/^[A-Za-z0-9_-]{1,24}$/.test(soloTrainer)} onClick={() => requestPlay('solo_new', { trainer: soloTrainer, ...(soloSeed ? { seed: soloSeed } : {}) }, null, { playAfter: false })}>Start adventure <ArrowRight size={16} /></button></div></>}
      {dialog === 'create' && <><div className="modal-icon"><Leaf size={22} /></div><span className="eyebrow gold">HOSTED</span><h2 id="modal-title">Create hosted world</h2>{!state.hosting.available ? <><p>Hosting management is unavailable. Join an existing server with a player invitation, or create a local world.</p><div className="modal-actions"><button className="button primary" onClick={() => setDialog(null)}>Got it</button></div></> : !state.hosting.enrolled ? <><p>{hostMode === 'restore' ? 'Restore an existing owner profile. This never replaces a different account on this device.' : 'Import a private host access file to set up your account. You only need to do this once on this device.'}</p>{state.hosting.backup_available && <div className="invite-tabs"><button type="button" aria-pressed={hostMode === 'access'} onClick={() => { hostFileRequest.current++; setHostMode('access'); setHostAccess(null); setHostFileName(''); setHostFingerprint(''); setError(''); }}>New account</button><button type="button" aria-pressed={hostMode === 'restore'} onClick={() => { hostFileRequest.current++; setHostMode('restore'); setHostAccess(null); setHostFileName(''); setHostFingerprint(''); setError(''); }}>Use backup</button></div>}<input ref={hostInput} className="visually-hidden" tabIndex={-1} type="file" accept=".json,application/json" onChange={event => { const file = event.target.files?.[0]; event.target.value = ''; chooseHostAccess(file); }} /><button className="upload" disabled={busy} onClick={() => hostInput.current?.click()}><span className="upload-icon"><LockKeyhole size={20} /></span><span><strong>{hostFileName || (hostMode === 'restore' ? 'Choose owner profile backup' : 'Choose host access file')}</strong><small>{hostMode === 'restore' ? 'Use your private owner profile backup' : 'Only import access from a trusted host'}</small></span><ArrowRight size={17} /></button><div className="security-note"><LockKeyhole size={15} /> Host access is private. Confirm the server fingerprint with your host through a separate trusted channel.</div>{hostFingerprint && <div className="fingerprint"><strong>Server fingerprint</strong><span>{hostFingerprint}</span></div>}{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" disabled={busy} onClick={() => setDialog(null)}>Cancel</button><button className="button primary" disabled={!hostAccess || busy} onClick={() => run(hostMode === 'restore' ? 'host_restore' : 'host_enroll', hostMode === 'restore' ? { profile: hostAccess } : { access: hostAccess })}>{hostMode === 'restore' ? 'Restore account' : 'Set up account'}</button></div></> : <><p>Your world lives on the hosted service, independent of your game. Choose a name and your trainer profile.</p>{state.hosting.pending && <p className="inline-error">{state.hosting.pending.invalid ? 'A previous creation request needs attention before another can be started.' : 'A previous creation may have reached the server. Retry the same request to avoid duplicates.'}</p>}<label className="field-label" htmlFor="host-world-name">World name</label><input className="text-input" id="host-world-name" maxLength={80} value={hostName} readOnly={Boolean(state.hosting.pending)} onChange={event => setHostName(event.target.value)} /><label className="field-label spaced-label" htmlFor="host-trainer">Trainer profile</label><input className="text-input" id="host-trainer" maxLength={24} value={hostTrainer} readOnly={Boolean(state.hosting.pending)} onChange={event => setHostTrainer(event.target.value)} /><p className="field-hint">Profile: letters, numbers, underscores or hyphens. Your save stays on this device.</p>{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" disabled={busy} onClick={() => setDialog(null)}>Cancel</button><button className="button ghost" disabled={busy || !hostName.trim() || !/^[A-Za-z0-9_-]{1,24}$/.test(hostTrainer) || state.hosting.pending?.invalid} onClick={() => requestPlay('host_create', { name: hostName, trainer: hostTrainer }, null, { playAfter: false })}>Create only</button><button className="button primary" disabled={busy || !hostName.trim() || !/^[A-Za-z0-9_-]{1,24}$/.test(hostTrainer) || state.hosting.pending?.invalid} onClick={() => requestPlay('host_create', { name: hostName, trainer: hostTrainer })}>{state.hosting.pending ? 'Retry and play' : 'Create and play'}</button></div></>}</>}
      {dialog === 'backup-owner' && <><div className="modal-icon"><LockKeyhole size={22} /></div><span className="eyebrow gold">PROTECT YOUR WORLDS</span><h2 id="modal-title">Back up your owner account?</h2><p>This file contains the private credential that controls your hosted worlds. Anyone with it can manage those worlds. Save it in an encrypted, private place and never share it as a friend invitation.</p><p className="field-hint">Your browser may save it in a regular downloads folder. Player saves and server-world data are not included.</p>{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" disabled={busy} onClick={() => setDialog(null)}>Cancel</button><button className="button primary" disabled={busy} onClick={() => run('host_export')}>Create backup</button></div></>}
      {dialog === 'invite-owner' && <><div className="modal-icon"><LockKeyhole size={22} /></div><span className="eyebrow gold">SHARE HOST ACCESS</span><h2 id="modal-title">Invite another owner?</h2><p>This creates a private access file that lets someone set up their own hosted-world account. Only share it with someone you trust. The host may restrict which accounts can issue these invitations.</p>{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" disabled={busy} onClick={() => setDialog(null)}>Cancel</button><button className="button primary" disabled={busy} onClick={() => run('host_invite_account')}>Create access file</button></div></>}
      {dialog?.type === 'share' && <><div className="modal-icon"><LockKeyhole size={22} /></div><span className="eyebrow gold">{dialog.kind === 'backup' ? 'OWNER ACCOUNT BACKUP' : dialog.kind === 'owner' ? 'SHARE HOST ACCESS' : 'INVITE A FRIEND'}</span><h2 id="modal-title">{dialog.kind === 'backup' ? 'Your backup is ready' : 'Your invitation is ready'}</h2><p>{dialog.kind === 'backup' ? 'Keep this private account credential somewhere encrypted. Anyone with it can manage your hosted worlds.' : dialog.kind === 'owner' ? 'This private file lets someone set up a hosted-world account. Share it only through a trusted channel.' : dialog.kind === 'local_friend' ? 'This private file grants access to the named trainer in this local world. Share it only with that player and confirm the server fingerprint separately.' : 'Download this private invitation and send it to one friend through a trusted channel. It binds to the trainer who redeems it.'}</p><a className="button primary" href={dialog.url} download={dialog.kind === 'backup' ? 'emerald-owner-backup.json' : dialog.kind === 'owner' ? 'emerald-host-access.json' : 'emerald-world-invitation.json'}><ArrowDownToLine size={17} /> {dialog.kind === 'backup' ? 'Download backup' : 'Download invitation'}</a><div className="modal-actions"><button className="button ghost" disabled={busy} onClick={() => setDialog(null)}>Done</button></div></>}

      {dialog?.type === 'offline' && <><div className="modal-icon"><Gamepad2 size={22} /></div><span className="eyebrow gold">A SEPARATE ADVENTURE</span><h2 id="modal-title">Play offline</h2><p>Play as <strong>{dialog.world.trainer}</strong> in {dialog.world.name}. Offline progress is kept in a separate save and never merges back into your online world.</p><p>Start a fresh offline save or resume an existing one. You can also make a one-time copy of your online save if no offline save exists yet.</p>{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" disabled={busy} onClick={() => requestPlay('offline', { world: dialog.world.key, copy: true }, null, { playAfter: false })}>Copy online save</button><button className="button primary" disabled={busy} onClick={() => requestPlay('offline', { world: dialog.world.key, copy: false }, null, { playAfter: false })}>Start or resume</button></div></>}
      {dialog?.type === 'leave' && <><div className="modal-icon"><DoorOpen size={22} /></div><span className="eyebrow gold">CLOSE GAME</span><h2 id="modal-title">Finished playing?</h2><p>Save in the game first. Closing it can discard progress since your last save.</p>{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" disabled={busy} onClick={() => setDialog(null)}>Keep playing</button><button className="button danger-button" disabled={busy} onClick={() => run('leave', { game: dialog.game })}>Close game</button></div></>}
      {dialog?.type === 'rename' && <><div className="modal-icon"><Leaf size={22} /></div><span className="eyebrow gold">LOCAL NAME</span><h2 id="modal-title">Name this world</h2><p>This name is only for your launcher. It won’t change the server or anyone else’s view.</p><label className="field-label" htmlFor="world-name">World name</label><input className="text-input" id="world-name" maxLength={80} value={worldName} onChange={event => setWorldName(event.target.value)} />{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" disabled={busy} onClick={() => setDialog(null)}>Cancel</button><button className="button primary" disabled={busy || !worldName.trim()} onClick={() => run('rename', { world: dialog.world.key, label: worldName })}>Save name</button></div></>}
      {dialog?.type === 'forget' && <><div className="modal-icon"><LockKeyhole size={22} /></div><span className="eyebrow gold">SAVED CONNECTION</span><h2 id="modal-title">Forget this world?</h2><p>This removes the saved connection for <strong>{dialog.world.name}</strong>. Your trainer and offline saves stay on this device. You will need a new invitation to access this world here again.</p>{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" disabled={busy} onClick={() => setDialog(null)}>Cancel</button><button className="button danger-button" disabled={busy} onClick={() => run('forget', { world: dialog.world.key })}>Forget connection</button></div></>}
      {dialog === 'reconnect' && <><div className="modal-icon"><Globe2 size={22} /></div><span className="eyebrow gold">RETURN TO YOUR WORLD</span><h2 id="modal-title">Reconnect?</h2><p>This closes games started by the launcher, then reconnects using your saved invitation. Save in the game first. Interrupted battles or trades are not restored automatically.</p>{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" disabled={busy} onClick={() => setDialog(null)}>Cancel</button><button className="button primary" disabled={busy} onClick={() => run('reconnect', {}, { playAfter: true })}>Reconnect and play</button></div></>}
      {dialog?.type === 'leave-personal' && <><h2 id="modal-title">Leave settings?</h2><p>Your unapplied draft will be discarded. Reload settings if a save was interrupted.</p><div className="modal-actions"><button className="button ghost" onClick={() => setDialog(null)}>Keep editing</button><button className="button primary" onClick={() => { setPersonalDirty(false); setPage(dialog.page); setMenu(false); setDialog(null); }}>Discard draft</button></div></>}
      {dialog?.type === 'leave-terrain' && <><h2 id="modal-title">Leave terrain editor?</h2><p>Your unapplied draft will be discarded. Reload terrain if a save was interrupted.</p><div className="modal-actions"><button className="button ghost" onClick={() => setDialog(null)}>Keep editing</button><button className="button primary" onClick={() => { setTerrainDirty(false); setPage(dialog.page); setMenu(false); setDialog(null); }}>Discard draft</button></div></>}
      {dialog?.type === 'leave-rules' && <><h2 id="modal-title">Leave world options?</h2><p>Your draft will be discarded. If a save was interrupted, reload the options to check it.</p><div className="modal-actions"><button className="button ghost" onClick={() => setDialog(null)}>Keep editing</button><button className="button primary" onClick={() => { setRulesDirty(false); setRulesWorld(dialog.world); setPage(dialog.page); setMenu(false); setDialog(null); }}>Discard draft</button></div></>}
      {dialog?.type === 'switch' && <><div className="modal-icon"><DoorOpen size={22} /></div><span className="eyebrow gold">SWITCH ADVENTURES</span><h2 id="modal-title">Switch worlds?</h2><p>This disconnects your current world and closes games started by this launcher. Save in the game first. An interrupted battle or trade does not resume automatically.</p>{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" disabled={busy} onClick={() => setDialog(null)}>Cancel</button><button className="button primary" disabled={busy} onClick={() => run(dialog.action, dialog.payload, { disconnectFirst: true, playAfter: dialog.playAfter, returnPage: dialog.returnPage })}>Switch and continue</button></div></>}
      {dialog === 'disconnect' && <><div className="modal-icon"><DoorOpen size={22} /></div><span className="eyebrow gold">DISCONNECT</span><h2 id="modal-title">Disconnect and close games?</h2><p>Disconnecting closes games started by this launcher. Save in the game first. {state.local_host ? 'The local host keeps running until you stop it or quit the launcher.' : 'Your remote world keeps running.'}</p>{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" disabled={busy} onClick={() => setDialog(null)}>Keep playing</button><button className="button danger-button" disabled={busy} onClick={() => run('disconnect')}>Disconnect</button></div></>}
      {dialog === 'quit' && <><div className="modal-icon"><DoorOpen size={22} /></div><span className="eyebrow gold">QUIT</span><h2 id="modal-title">Quit the launcher?</h2><p>This closes games and local services started by this launcher. Save in the game first. A remote dedicated world keeps running.{personalDirty && ' Your unapplied settings draft will be discarded.'}</p>{error && <p className="inline-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button ghost" disabled={busy} onClick={() => setDialog(null)}>Cancel</button><button className="button danger-button" disabled={busy} onClick={() => run('quit')}>Quit launcher</button></div></>}
    </section></div>}
  </div>;
}

function WorldCard({ world, index, busy, ready, onContinue, onForget, onOffline, onRename, onFavorite }) {
  return <article className="world-card"><div className={`world-art art-${index % 3}`}><span className="world-tag"><Leaf size={13} /> SAVED WORLD</span>{onFavorite && <button className={`favorite-button ${world.favorite ? 'is-favorite' : ''}`} aria-label={world.favorite ? `Remove ${world.name} from favorites` : `Add ${world.name} to favorites`} aria-pressed={Boolean(world.favorite)} disabled={busy || !ready} onClick={onFavorite}><Star size={16} fill={world.favorite ? 'currentColor' : 'none'} /></button>}</div><div className="world-body"><div className="world-icon"><Leaf size={18} /></div><div className="world-info"><h3>{world.name}</h3><p>Trainer <strong>{world.trainer}</strong></p></div><button className="button small primary" aria-label={`Play ${world.name}`} disabled={busy || !ready} onClick={onContinue}>Play <ArrowRight size={15} /></button></div>{onRename && <button className="card-forget" disabled={busy || !ready} onClick={onRename}>Rename</button>}{onOffline && <button className="card-forget" disabled={busy || !ready} onClick={onOffline}>Play offline</button>}{onForget && <button className="card-forget" onClick={onForget}>Forget connection</button>}</article>;
}

function EmptyWorlds({ onJoin, ready }) {
  return <div className="empty-worlds"><div className="empty-icon"><Compass size={23} /></div><div><h3>No saved connections</h3><p>Join with a private player invitation.</p></div><button className="button small ghost" disabled={!ready} onClick={onJoin}>Join a world <ArrowRight size={15} /></button></div>;
}

const root = document.getElementById('root');
if (root) createRoot(root).render(<App />);
