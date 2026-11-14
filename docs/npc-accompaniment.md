# Optional generated-NPC walking companions

A real movement capability, not a player follower flag or scripted story. This
app-only candidate builds on #337 and retains published native #40. It excludes
the unpublished doubles payload and leaves original Hoenn cast/services alone.

## Player journey

In an admitted generated place, stand beside an existing recurring NPC using a
matched CHARREG1/CHARWALK1 client. In the existing private-command chat, use:

- `/guild npc walk-with ID`: explicitly send a public fictional invitation.
- `/guild npc walk-stop`: withdraw it or end your current accompaniment.

The character's configured author receives the real invitation. It may ignore
it or choose `world.accompany_player(request)`. This does not force a plan or
promise a reply. An NPC can accompany only one invitation at a time, and one
player session can request one NPC at a time.

After acceptance, the authority computes routes toward an unoccupied tile near
the player's latest ready position. It admits one cardinal step at a time through
the existing character-action compiler, journey reducer and published native
movement snapshot. Other players see the same scoped NPC object and movement.
The NPC stays approximately two tiles away rather than occupying the player.
This is actual authoritative walking, not teleportation or a second fake NPC.

## Scope and pace

Only the same exact generated-map revision is supported. No cross-map following,
warp, canonical relocation, player control, battle participation, party mutation
or save flag. Field menus, battles, stale state and unreachable destinations pause
new steps. Player cancellation, disconnect, a new session, or leaving the map
ends accompaniment. A currently admitted step is removed by a versioned stop at
the actual current tile; it may finish before the stop is admitted. It cannot
continue an arbitrary queued route. Collision-blocked steps can also be stopped.

This intentionally uses the existing five-second capability scheduler and
normal mechanic staging. It is leisurely accompaniment, **not** a tight or
full-speed native follower formation; the player can outpace it. No per-tile
model call is requested: intermediate journey arrivals remain real history but
are not reaction turns for the ongoing accompaniment plan. Existing configured
provider limits remain in force. Restart retains action evidence and safely ends
the old session instead of attaching the NPC to a reconnecting trainer.

Invitation/session ownership is held privately in the authority. The author
sees the NPC, request number, map revision and request state, not player names,
private saves or session credentials. Public events assert the invitation and
actual NPC actions, not a personal relationship or an invented adventure.

## Verification and integration

Tests use the real authority, staged character source, collision reducer,
CHARACTER_WALK snapshot, and independent-author queue. They cover two different
NPCs, an occupied route, a moving player, menu pause, session replacement,
restart, withdrawal and cancellation of an occupied in-flight step. Native
rendering and motion smoothness remain Maya's linked/multiplayer QA task. No
live provider, player save or rendered playtest was used. The entry point is
currently the existing chat command, not a new native menu item.
