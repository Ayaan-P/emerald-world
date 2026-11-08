import React from 'react';
import { ArrowRight, Compass, Gamepad2, Globe2, Monitor, Plus, UsersRound } from 'lucide-react';
import { sessionSummary } from './player-state';
import './player-home.css';

export function WorldTile({ title, subtitle, onPlay, onInvite, disabled, playing }) {
  return <article className="journey-world">
    <div className="world-row-icon"><Gamepad2 size={20} /></div>
    <div className="journey-world-label"><h3>{title}</h3><p>{subtitle}</p></div>
    <div className="journey-world-actions">{onInvite && <button className="button small ghost" disabled={disabled} onClick={onInvite}>Invite friend</button>}
      <button className="button small primary" aria-label={playing ? `Playing ${title}` : `Play ${title}`} disabled={disabled || playing} onClick={onPlay}>{playing ? 'Playing' : 'Play'} {!playing && <ArrowRight size={15} />}</button></div>
  </article>;
}

export default function PlayerHome({ state, ready, busy, onJoin, onCreate, onSolo, onWorlds, onLocal, onExplore, onHelp,
  onLocalOpen, onPlaySaved, onPlayHosted, onPlayOffline, onLaunch, onScreen, onClose, onDisconnect, onReconnect }) {
  const session = sessionSummary(state);
  if (!ready) {
    session.status = 'Launcher unavailable';
    session.tone = 'error';
    session.detail = 'Game status is unknown until the launcher responds.';
  }
  const disabled = busy || !ready;
  const local = state.local_worlds || [];
  const owned = new Set(state.hosting.worlds.map(world => `hosted-${world.id}`));
  const worlds = [...state.worlds].filter(world => !owned.has(world.key)).sort((a, b) => Number(b.favorite) - Number(a.favorite) || a.name.localeCompare(b.name));
  const saved = [
    ...local.map(world => ({ ...world, id: `local/${world.key}`, mode: 'Local', playing: session.running && state.world_key === world.key,
      play: () => onLocalOpen('local_resume', { world: world.key, trainer: world.trainer }, world.key, { playAfter: true }) })),
    ...state.hosting.worlds.map(world => ({ ...world, id: `hosted/${world.id}`, mode: 'Hosted', playing: session.running && state.world_key === `hosted-${world.id}`, play: () => onPlayHosted(world) })),
    ...worlds.map(world => ({ ...world, id: `remote/${world.key}`, mode: 'Hosted', playing: session.running && state.world_key === world.key, play: () => onPlaySaved(world) })),
    ...state.offline_saves.map(save => ({ ...save, id: `solo/${save.world}/${save.trainer}`, mode: 'Solo', playing: session.running && session.game === `offline/${save.trainer}` && state.offline_world_key === save.world, play: () => onPlayOffline(save) })),
  ];
  return <div className="content player-home">
    <header className="page-heading"><div><h1>Play</h1><p>{state.engine === 'expansion-native' ? 'Expansion' : 'Emerald'} · Native PC</p></div><button className="text-button" onClick={onHelp}>Controls & help <ArrowRight size={15} /></button></header>
    {(state.connected || session.running) && <section className={`session-card ${session.tone}`} aria-label="Current session">
      <div className="session-main"><span className="mode-label">{session.mode}</span><h2>{session.name}</h2><p>{session.trainer && <>Trainer <strong>{session.trainer}</strong> · </>}<span className={`dot ${session.tone === 'error' ? 'error-dot' : session.tone}`} /> {session.status}</p><p className="session-detail">{session.detail}</p></div>
      <div className="session-controls">{session.running ? <>
        <button className="button ghost" disabled={disabled} onClick={() => onClose(session.game)}>Close game</button>
        <button className="text-button" disabled={disabled} onClick={onScreen}>In-page preview</button>
      </> : <button className="button primary" disabled={disabled} onClick={onLaunch}><Gamepad2 size={18} /> Play now</button>}
        {state.connected && !state.local_host && <button className="text-button" disabled={disabled} onClick={onReconnect}>Reconnect</button>}
        {state.connected && <button className="text-button" disabled={disabled} onClick={onDisconnect}>Disconnect</button>}
      </div>
      {state.local_host && <button className="session-area" onClick={onExplore}><Compass size={17} /><span>{state.active_generated_area?.label || 'No generated area selected'}</span><span>Explore <ArrowRight size={15} /></span></button>}
    </section>}
    {!state.games.length && state.game_exit?.unexpected && <section className="notice error" role="alert"><strong>Game closed unexpectedly</strong><p>Only your last in-game save can be recovered. Unsaved progress is not restored automatically. Select Play to reopen.</p></section>}
    <section className="play-options" aria-label="Where to play">
      <article className="play-option"><div className="option-icon"><Monitor size={23} /></div><h2>Local</h2><p>Runs on this computer.</p><div className="option-actions"><button className="button primary" disabled={disabled} onClick={onCreate}><Plus size={16} /> Create local world</button><button className="text-button" onClick={onLocal}>Browse local saves <ArrowRight size={15} /></button></div><span className="option-note">The host stops when you quit the launcher.</span><button className="text-button generate-link" onClick={onExplore}><Compass size={15} /> Generate caves & areas</button></article>
      <article className="play-option"><div className="option-icon"><Globe2 size={23} /></div><h2>Hosted</h2><p>Runs on a server, such as Hetzner.</p><div className="option-actions"><button className="button primary" disabled={disabled} onClick={onJoin}><UsersRound size={16} /> Join a world</button><button className="text-button" onClick={onWorlds}>Manage hosted worlds <ArrowRight size={15} /></button></div><span className="option-note">Join with a private invitation from the host.</span></article>
    </section>
    <div className="solo-shortcut"><Gamepad2 size={18} /><span>Solo play without a world server</span><button className="text-button" disabled={disabled} onClick={onSolo}>New solo save <Plus size={15} /></button></div>
    {saved.length > 0 && <section className="worlds-section" aria-labelledby="saved-games-title"><div className="section-heading"><h2 id="saved-games-title">Saved games</h2><span className="muted-copy">Trainer saves stay on this computer.</span></div><div className="save-list">{saved.map(save => <WorldTile key={save.id} title={save.name} subtitle={`${save.mode} · ${save.trainer}`} playing={save.playing} disabled={disabled} onPlay={save.play} />)}</div></section>}
    {ready && session.running && !session.game?.startsWith('offline/') && state.presence?.state === 'connected' && <section className="worlds-section" aria-labelledby="nearby-title"><div className="section-heading"><h2 id="nearby-title">Nearby trainers</h2><button className="text-button" onClick={onHelp}>How to tag up <ArrowRight size={15} /></button></div>{state.presence.nearby?.length ? <div className="nearby-list">{state.presence.nearby.map(peer => <div className="nearby-person" key={peer.trainer}><div className="nearby-avatar">{peer.trainer.slice(0, 1).toUpperCase()}</div><div><strong>{peer.trainer}</strong><span>{peer.ready ? 'Available' : 'Busy'}{!peer.rendered ? ' · Off screen' : ''}</span></div></div>)}</div> : <p className="muted-copy">{state.presence.nearby === null ? 'Nearby trainer information is unavailable.' : 'No trainers nearby.'}</p>}</section>}
  </div>;
}
