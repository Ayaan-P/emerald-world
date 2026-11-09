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

## Custody of existing portable props

A prop may explicitly declare `portable: true`. This is an authored world rule, not an inference from its rock/boulder art. `world.observe` exposes a `portable_revision` fingerprint. `world.take_prop` requires that exact current object and an adjacent stationary actor; the authority atomically records exclusive custody, removes the prop from rendered objects and commits the tool receipt. Nothing is minted. Four props per actor and 32 custody identities per world bound this initial implementation.

`world.place_prop` requires the same owner and custody version, and a free adjacent tile on the same exact generated revision. It restores the same identity, appearance and existing object state. Collision, ready-player and legacy-client checks remain mandatory. A failed placement or receipt leaves custody intact. The ordinary snapshot protocol removes/restores the prop; no carrying sprite or native bag UI is implied.

The authoritative custody table survives restart and takes precedence over a mechanic returning its old object list. An old source cannot recreate a carried duplicate, silently delete a tracked placed prop or reinterpret it as a character. Rebinding the immutable map is blocked while it has carried props, and carriers cannot change generated-map scope until placing them. This is deliberately same-map prop transport, not cross-region inventories, harvesting, resource quantities or Pokémon-item transfer. Native player bags and save structures are untouched.

Capability discovery lists custody owner, version and revision. Place, then another actor may take the same existing prop under the normal adjacency rules. Ownership is not transferred by dialogue or a model assertion. Tests cover actual take -> authority navigation -> place, source refreshes, restart, stale/non-owner actions, rollback and occupied placement. An aged-evidence issue exposed by this longer composition was fixed: recalled navigation evidence now retains its real database sequence.
