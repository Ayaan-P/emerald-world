# Typed generated props and agent object interactions

Separate follow-on to app #299 and native #26. No canonical story/service replacement, inventory or native bag access.

## Native representation and compatibility

Objects may declare `kind: prop` only on exact-revision generated maps. Their `gfx` is an explicit prop enum: 0 uses native BreakableRock art, 1 uses PushableBoulder art. These are inert shared props, not Rock Smash/Strength scripts or item drops. Character objects retain their original rules and boy/girl graphics. Prop IDs cannot also be persistent characters. Existing collective route, collision, endpoint and geometry validation still applies.

Clients advertise WORLDOBJ1 as the last role suffix. REGION_PROP has the same revision/id/map/coordinate/graphics/text fields as REGION_OBJECT, but distinct semantics. The native parser validates the kind, region admission and bounds. Rendering uses native inanimate object graphics with the existing reserved object ownership and collision mechanism; no avatar fallback or directional animation is applied. Existing A interaction shows the prop's public literal text; it does not grant items or automatically invoke an authored agent handler.

Old servers trigger the usual capability fallback before other suffixes are removed. Old clients cannot obtain/ACK/enter a generated area with props. Adding props while an incompatible player is already inside fails, instead of introducing invisible obstacles. Ready-player overlap also rejects placement or movement.

## Author contract

A current mechanic may advertise `state.world_object_actions[object_id] = {action_id: description}` with at most eight bounded action descriptions, and implement:

    def actor_interact(object_id, action, state):
        return {"state": updated_own_object_state, "x": x, "y": y,
                "gfx": prop_kind, "text": public_literal_text}

The handler receives only that prop's own prior state, not a player identity or inventory. State is bounded to 2 KiB. It may keep/change the prop's text and native appearance, or move it at most one cardinal cell. It cannot change identity, region, map, other objects, player saves or native inventory through this interface. It uses the normal sandbox and mechanic admission; invalid collisions or results are rejected before committing.

`world.observe` discovers advertised actions and an exact object/source fingerprint. `world.use_object(object, action, object_revision)` requires actual adjacent actor location on the same revision, a current fingerprint and a stationary active world actor. After navigating, observe again: source changes intentionally invalidate old fingerprints. Invocation is pending until actual admitted object state exists. Durable control preserves the result across subsequent ticks and restart; requests are not replayed. The tool reports actual before/after object state and a state-change digest, not an author-supplied claim of rewards or success at an unrelated task.

The 32-request source-consolidation bound is inherited by this adapter. No arbitrary handler code is registered by a tool call: handlers are part of the separately authored, staged mechanic. Ordinary non-character objects are not silently reclassified as NPCs.

## Verification and limits

Authority tests cover real observed handlers, multiple actors, unsupported/stale/nonadjacent requests, pending versus committed effects, restart, player overlap and legacy entry refusal. A cross-language fixture feeds actual authority REGION_PROP snapshot rows through the production native parser and graphics selector using explicit engine doubles. Full linked-native rendering, interaction animation, live provider behavior and release QA remain unverified. This adds no harvesting, bags, material accounting or fabricated item transfers.
