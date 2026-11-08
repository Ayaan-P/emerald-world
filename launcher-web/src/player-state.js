// Session availability is not proof that the native game has connected.
export function sessionSummary(state) {
  const games = state.games || [];
  const offline = games.find(game => game.startsWith('offline/'));
  const running = Boolean(offline || (state.connected && games.includes(state.trainer)));
  const local = (state.local_worlds || []).find(world => world.key === state.world_key);
  const remote = (state.worlds || []).find(world => world.key === state.world_key);
  const hosted = (state.hosting?.worlds || []).find(world => `hosted-${world.id}` === state.world_key);
  const solo = (state.offline_saves || []).find(save => save.world === state.offline_world_key && `offline/${save.trainer}` === offline);
  const trainer = offline ? offline.slice('offline/'.length) : state.trainer;
  const name = offline ? solo?.name || 'Solo save' : local?.name || remote?.name || hosted?.name || 'Current world';
  const mode = offline ? 'Solo' : state.local_host ? 'Local' : 'Hosted';
  const live = running && !offline && state.presence?.state === 'connected';
  const lost = running && !offline && state.presence?.state === 'disconnected';
  return { running, game: offline || state.trainer, name, trainer, mode,
    status: offline ? 'Offline game running' : lost ? 'Connection lost' : live ? 'Game connected' : running ? 'Waiting for game connection' : state.connected ? 'Ready to launch' : 'No game running',
    tone: lost ? 'error' : live || offline ? 'online' : 'idle',
    detail: lost ? 'Reconnect returns to your last save. An interrupted battle cannot be resumed.' : running ? 'Play in the game window. Save before closing.' : 'Launch the game to continue your trainer save.' };
}
