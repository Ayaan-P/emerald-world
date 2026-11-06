import ControlsHelp from './ControlsHelp';
import CoopGuide from './CoopGuide';
import ExpeditionPanel from './ExpeditionPanel';
import ReleaseModes from './ReleaseModes';
import React from 'react';
import { ArrowRight, Compass, Gamepad2, Globe2, Leaf, Plus, UsersRound } from 'lucide-react';
import './player-home.css';

function WorldTile({ title, subtitle, onPlay, onInvite, disabled, playing }) {
  return <article className="journey-world">
    <div className="journey-world-art"><span><Leaf size={13} /> YOUR ADVENTURE</span></div>
    <div className="journey-world-content"><div className="journey-world-label"><h3>{title}</h3><p>{subtitle}</p></div>
      <div className="journey-world-actions">{onInvite && <button className="button small ghost" disabled={disabled} onClick={onInvite}>Invite friend</button>}
        <button className="button small primary" aria-label={playing ? `Playing ${title}` : `Play ${title}`} disabled={disabled || playing} onClick={onPlay}>{playing ? 'Playing' : 'Play'} {!playing && <ArrowRight size={15} />}</button></div>
    </div>
  </article>;
}

export default function PlayerHome({ state, ready, busy, onJoin, onCreate, onSolo, onWorlds,
  onLocalOpen, onAuthorCave, onActivateArea, onPlaySaved, onPlayHosted, onPlayOffline, onLaunch, onScreen, onClose, onDisconnect, onReconnect, onHostRefresh, onHostInvite, onInviteOwner, onBackupOwner }) {
  const onlineGame = state.connected && state.trainer && state.games.includes(state.trainer);
  const offlineGame = state.games.find(game => game.startsWith('offline/'));
  const playing = Boolean(onlineGame || offlineGame);
  const currentGame = onlineGame ? state.trainer : offlineGame;
  const savedWorld = state.worlds.find(world => world.key === state.world_key);
  const ordered = [...state.worlds].sort((a, b) => Number(b.favorite) - Number(a.favorite) || a.name.localeCompare(b.name));
  const ownedKeys = new Set(state.hosting.worlds.map(world => `hosted-${world.id}`));
  const saved = ordered.filter(world => !ownedKeys.has(world.key));
  const localWorlds = state.local_worlds || [];
  const localWorld = localWorlds.find(world => world.has_save) || localWorlds[0];
  const currentLocalWorld = localWorlds.find(world => world.key === state.world_key);
  const featured = localWorld ? { name: localWorld.name, trainer: localWorld.trainer, local: true, hasSave: localWorld.has_save,
    play: () => onLocalOpen('local_resume', { world: localWorld.key, trainer: localWorld.trainer }, localWorld.key, { playAfter: true }) }
    : ordered.length ? { name: ordered[0].name, trainer: ordered[0].trainer, play: () => onPlaySaved(ordered[0]) }
    : state.hosting.worlds.length ? { name: state.hosting.worlds[0].name, trainer: state.hosting.worlds[0].trainer, play: () => onPlayHosted(state.hosting.worlds[0]) }
    : state.offline_saves.length ? { name: state.offline_saves[0].name, trainer: state.offline_saves[0].trainer, play: () => onPlayOffline(state.offline_saves[0]) }
    : null;
  const disabled = busy || !ready;

  return <div className="content player-home">
    <section className="hero journey-hero"><div className="hero-shade" /><div className="hero-copy">
      <div className="hero-kicker"><span className="diamond" /> YOUR WORLD, YOUR ADVENTURE</div>
      <h1>{playing ? <>Your game<br /><em>is open.</em></> : state.connected ? <>Ready to<br /><em>play.</em></> : featured ? <>Pick up your<br /><em>adventure.</em></> : <>Your adventure,<br /><em>together.</em></>}</h1>
      <p>{playing ? 'Your game is running in its own window. Save in the game before you close it.' : state.connected ? `Your world session is open${state.trainer ? ` as ${state.trainer}` : ''}. Start the game to enter.` : featured ? `${featured.local && !featured.hasSave ? 'Open' : 'Continue'} ${featured.name} as ${featured.trainer}.${featured.local ? ' Opens your game in a separate window.' : ''}` : 'Create a world for friends, join theirs, or start a solo adventure.'}</p>
      <div className="hero-actions">{playing ? <><button key="screen" className="button primary" disabled={disabled} onClick={onScreen}><Gamepad2 size={18} /> View in page</button><button key="close" className="button outline" disabled={disabled} onClick={() => onClose(currentGame)}>Close game</button><button key="join" className="button outline" disabled={disabled} onClick={onJoin}>Join another world</button><button key="create" className="button outline" disabled={disabled} onClick={onCreate}>New world / save</button></> : state.connected ? <><button key="play" className="button primary" disabled={disabled} onClick={onLaunch}><Gamepad2 size={18} /> Play now <ArrowRight size={17} /></button><button key="join" className="button outline" disabled={disabled} onClick={onJoin}>Join another world</button><button key="create" className="button outline" disabled={disabled} onClick={onCreate}>New world / save</button></> : featured ? <><button key="featured" className="button primary" disabled={disabled} onClick={featured.play}><Gamepad2 size={18} /> {featured.local ? `${featured.hasSave ? 'Continue' : 'Open'} ${featured.name} · ${featured.trainer}` : 'Continue adventure'} <ArrowRight size={17} /></button><button key="join" className="button outline" disabled={disabled} onClick={onJoin}><UsersRound size={18} /> Join a world</button><button key="create" className="button outline" disabled={disabled} onClick={onCreate}><Plus size={18} /> New world / save</button></> : <><button key="join" className="button primary" disabled={disabled} onClick={onJoin}><UsersRound size={18} /> Join a world</button><button key="create" className="button outline" disabled={disabled} onClick={onCreate}><Plus size={18} /> New world / save</button><button key="solo" className="button outline" disabled={disabled} onClick={onSolo}><Gamepad2 size={18} /> Play solo</button></>}</div>
    </div><div className="hero-coordinate">HOENN REGION <span>•</span> YOUR NEXT CHAPTER</div></section>

    {playing ? <section className="journey-status"><span className={`dot ${state.presence?.state === 'disconnected' ? 'error-dot' : 'online'}`} /><div><strong>{state.presence?.state === 'disconnected' ? 'Your game reports a lost connection' : 'Your game is running'}</strong><p>{state.presence?.state === 'disconnected' ? 'Save if you can. Reconnecting closes the game and cannot restore an interrupted battle or trade.' : 'Switch to the game window to play. F11 toggles its fullscreen mode. Save before closing.'}</p></div>{state.connected && !state.local_host && <button className="button small ghost" disabled={disabled} onClick={onReconnect}>Reconnect</button>}{state.connected && <button className="button small ghost" disabled={disabled} onClick={onDisconnect}>Disconnect</button>}</section> : state.connected ? <section className="journey-status"><span className="dot idle" /><div><strong>{currentLocalWorld?.name || savedWorld?.name || 'World session open'}</strong><p>{state.trainer ? `Trainer ${state.trainer}. ` : ''}Choose Play now above to enter in a separate game window.</p></div>{!state.local_host && <button className="button small ghost" disabled={disabled} onClick={onReconnect}>Reconnect</button>}<button className="button small ghost" disabled={disabled} onClick={onDisconnect}>Disconnect</button></section> : featured ? <section className="journey-status"><span className="dot idle" /><div><strong>{featured.name} · {featured.trainer}</strong><p>{featured.local ? `${featured.hasSave ? 'Saved game available.' : 'No trainer save yet.'} Continue opens its local session and game in a separate window.` : 'Continue opens your selected game in a separate window.'}</p></div></section> : <section className="journey-guide" aria-label="How it works"><div><span>01</span><strong>Choose a world</strong><p>Create with host access, join with a private invitation, or play solo.</p></div><div><span>02</span><strong>Start playing</strong><p>The game opens in its own window. Your launcher keeps the connection.</p></div><div><span>03</span><strong>Keep your progress</strong><p>Save in the game. Your trainer's progress stays on this device.</p></div></section>}

    {!state.games.length && state.game_exit?.unexpected && <section className="journey-status" role="alert"><span className="dot error-dot" /><div><strong>Your game closed unexpectedly</strong><p>Only your last in-game save can be recovered. Reopen the game with Play now or Continue above. Unsaved progress is not restored automatically.</p></div></section>}

    <ExpeditionPanel state={state} ready={ready} busy={busy} onOpen={onLocalOpen} onAuthor={onAuthorCave} onActivate={onActivateArea} />

    <ReleaseModes />

    <ControlsHelp />

    {state.hosting.available && state.hosting.enrolled && <section className="worlds-section"><div className="section-heading"><div><span className="eyebrow gold">PERSISTENT WORLDS</span><h2>Hosted by you</h2></div><div className="host-actions">{state.hosting.backup_available && <button className="text-button" disabled={disabled} onClick={onBackupOwner}>Back up account</button>}<button className="text-button" disabled={disabled} onClick={onInviteOwner}>Invite an owner</button><button className="text-button" disabled={disabled} onClick={onHostRefresh}>{state.hosting.loaded ? 'Refresh' : 'Load worlds'} <ArrowRight size={15} /></button></div></div>{state.hosting.worlds.length ? <div className="world-grid">{state.hosting.worlds.map(world => <WorldTile key={world.id} title={world.name} subtitle={`Hosted world · ${world.trainer}`} disabled={disabled} playing={Boolean(onlineGame && state.world_key === `hosted-${world.id}`)} onPlay={() => onPlayHosted(world)} onInvite={() => onHostInvite(world)} />)}</div> : <p className="muted-copy">{state.hosting.loaded ? 'No hosted worlds yet. Create one when you are ready.' : 'Load your hosted worlds to see the worlds you own.'}</p>}</section>}

    {(saved.length > 0 || !localWorlds.length) && <section className="worlds-section"><div className="section-heading"><div><span className="eyebrow gold">PICK UP WHERE YOU LEFT OFF</span><h2>Saved connections <span className="count">{saved.length}</span></h2></div><button className="text-button" disabled={disabled} onClick={onWorlds}>Manage worlds <ArrowRight size={15} /></button></div>{saved.length ? <div className="world-grid">{saved.slice(0, 3).map(world => <WorldTile key={world.key} title={world.name} subtitle={`Trainer ${world.trainer}`} disabled={disabled} playing={Boolean(onlineGame && state.world_key === world.key)} onPlay={() => onPlaySaved(world)} />)}</div> : <div className="empty-worlds"><div className="empty-icon"><Compass size={23} /></div><div><h3>{state.worlds.length ? 'Your hosted worlds are above' : 'Your next adventure starts here'}</h3><p>{state.worlds.length ? 'Your other saved connections will appear here.' : 'Join with a private invitation, and your world will be here next time.'}</p></div>{!state.worlds.length && <button className="button small ghost" disabled={disabled} onClick={onJoin}>Join a world <ArrowRight size={15} /></button>}</div>}</section>}

    {(state.offline_saves.length > 0 || !localWorlds.length) && <section className="worlds-section"><div className="section-heading"><div><span className="eyebrow gold">YOUR OWN PACE</span><h2>Solo adventures <span className="count">{state.offline_saves.length}</span></h2></div><button className="text-button" disabled={disabled} onClick={onSolo}>New solo save <Plus size={15} /></button></div>{state.offline_saves.length ? <div className="world-grid">{state.offline_saves.map(save => <WorldTile key={`${save.world}/${save.trainer}`} title={save.name} subtitle={`Offline · ${save.trainer}`} disabled={disabled} playing={Boolean(offlineGame === `offline/${save.trainer}` && state.offline_world_key === save.world)} onPlay={() => onPlayOffline(save)} />)}</div> : <p className="muted-copy">Play without an invitation. Solo progress is kept separately from online worlds.</p>}</section>}

    <CoopGuide />

    {state.presence && <section className="worlds-section"><div className="section-heading"><div><span className="eyebrow gold">LIVE FROM YOUR GAME</span><h2>Nearby trainers</h2></div><span className="presence-state"><span className={`dot ${state.presence.state === 'connected' ? 'online' : 'error-dot'}`} /> {state.presence.state === 'connected' ? 'Game connected' : state.presence.state === 'disconnected' ? 'Game disconnected' : 'Waiting for game'}</span></div>{state.presence.state === 'connected' ? (state.presence.nearby === null ? <p className="muted-copy">Nearby trainer information is unavailable.</p> : state.presence.nearby.length ? <div className="nearby-list">{state.presence.nearby.map(peer => <div className="nearby-person" key={peer.trainer}><div className="nearby-avatar">{peer.trainer.slice(0, 1).toUpperCase()}</div><div><strong>{peer.trainer}</strong><span>{peer.ready ? 'Available' : 'Busy'}{!peer.rendered ? ' · Not visible on screen' : ''}</span></div></div>)}</div> : <p className="muted-copy">No nearby trainers reported by your game right now.</p>) : <p className="muted-copy">Nearby trainers appear when your running game reports a fresh connection.</p>}</section>}
  </div>;
}
