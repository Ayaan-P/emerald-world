# Shared player and agent object use

This draft extends #306. Native #32 is unchanged: its normal A-button handling
already sends authenticated INTERACT_REGION for a facing adjacent typed prop.

An authored mechanic can map a prop ID to one advertised action ID in
`state.world_object_player_use`. Without that mapping the prop remains text-only.
With it, a valid A-button interaction stages the same
`actor_interact(object_id, action, own_state)` used by `world.use_object`.
The author-facing capability inspection explains this optional rule.

Normal authority admission checks the authenticated connection, exact region
ACK, fresh ready presence, facing/adjacency, sequence and interaction rate.
Only actual typed props on WORLDOBJ1 clients can invoke the default. Busy actions
are refused rather than queued invisibly or retried. There is no new command
syntax, invented inventory or generic NPC standing in for a prop.

Player and agent execution share one source wrapper, own-state limit, exact
object/action preconditions, native graphic enum, bounded text and one-cell
movement limit. The existing sandbox and mechanic validators determine whether
the result is admitted. Collision, player occupancy and region guards still
apply. Opening text is not a success receipt: private existing chat feedback
reports pending, applied, or not applied. Successful use records a public object
change without putting trainer identity into the handler or completion event.
The ordinary interaction log retains its existing semantics.

The effects are actual persistent world object state/text/appearance/position,
not native bag items, money, rewards, save flags or arbitrary other-object edits.
The native field initially displays the current prop text; changed text and
appearance arrive with subsequent snapshots. No new native choice menu or
rendered animation is claimed. An interrupted server does not automatically
retry a player's action; already admitted source/state remains durable.

## Validation

Authority tests send the real A-button wire message after authenticated region
transfer, apply the admitted source, then use the same handler from an agent
plan. Shared state advances twice and survives restart. Additional tests verify
text-only behavior, busy duplicate refusal, wrong facing/revision rejection and
unadmitted actions never reporting success. These component fixtures do not
substitute for linked native rendering/live server sandbox QA, owned by Maya.
