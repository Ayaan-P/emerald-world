# Shared original-actor scene ownership: staged, not live

Status: the authority reservation state machine is implemented and tested. It is
**not registered as a server endpoint or author action**. No existing actor moves
as a result of this patch. Native execution and recovery must be integrated before
activation. This is a safety-critical prerequisite, not a completed gameplay claim.

## Why a local walk hook is insufficient

Reviewed engine PR26 `b5504fd4e433f0cd3ea04c8c99487b5ec9754b7a`:

- `ObjectEventSetHeldMovement` unfreezes the original object, sets its held action,
  and invokes normal movement/follower machinery.
- `ScrCmd_release` clears finished held movement and unfreezes objects. It does
  not restore the actor's original coordinates or sprite state.
- Object collision checks current and previous coordinates. Human peers are
  exempted only for **player** movement in generated maps, not canonical NPCs
  walking in their normal rooms. A peer can obstruct a return path.
- `MoveObjectEventToMapCoords` would teleport an actor and reset field effects;
  it is not an acceptable silent substitute for a completed walking return.
- The existing CAST hooks run after original lock/faceplayer. Their continuation
  belongs to the real service/story script. Briney's transport, Rydel's bike
  service and Wally/Steven's progress-specific scenes cannot be resumed from an
  unverified arbitrary location.

## Implemented authority primitive

`SceneLeases` reserves a verified bounded closed cardinal path for one original
actor and one exact cohort of connection objects. The path includes the home tile
throughout. The integration must supply a geometry validator, not model claims.

All participants install the reservation and attest to an idle original actor at
home and clear occupancy before the owner can start. Only the exact initiating
connection can start/finish. A timeout, failed preparation or disconnect enters
`restoring`; it never releases tiles or records success. Every original participant
must certify home and idle before release. A new connection cannot impersonate an
old participant by reusing its trainer name. New admissions must be explicitly
deferred while the reservation exists. Tokens fence stale acknowledgements.

The state machine does not freeze players, mutate saves, grant a movement lease to
a model, or interpret a generic STATE report as an actor-restoration receipt.

## Required native and live-server integration

1. Negotiate a separate capability. Do not advertise it on current clients. A
   scene cannot start with legacy, unready or unsynchronized participants.
2. Use reviewed original-object local IDs and script-safe points; verify each
   local actor's current map, graphics, object identity, original position and
   absence of a conflicting script/follower/battle. Different personal story
   states may make an actor unavailable; refusal is valid, not a reason to spawn
   a replacement. Start with one reviewed fixed service actor, not global cast.
3. Validate native geometry including warps, stairs and elevation. Install path
   reservations in ordinary player collision **before** ACK. Bound canonical
   actor movement is the only exemption. Apply complete reservations at map
   entry, not only to clients currently seeing the actor.
4. Synchronize step indices to observers; use real held movement and recheck
   collisions for each step. Keep the ordinary script suspended until every
   controlled actor is home. Never write a movement type/hide flag/save template.
5. On cancellation, return through the reserved path using real animation.
   On disconnect, complete the local return while retaining local reservations.
   Object replacement/map transition must not move or clear a reused object slot.
6. Persist or reconstruct outstanding leases across authority restart, and add
   a bounded authenticated native restoration/recovery handshake. The current
   in-memory primitive deliberately has **no** forced-release escape hatch.
   Do not expose it live before recovery exists: otherwise a disconnected cohort
   could hold admission indefinitely. Replay, crash and save/reload QA are required.
7. Only after those pieces are tested may canonical author actions request a
   scene and actual completion receipts inform later character decisions.
   An authored path is not proof of execution, attendance or shared progress.

## Current tests

`test_canonical_scene_leases` exercises all-participant barrier ordering, exclusive
ownership, return-home acknowledgement, connection fencing, disconnects, deadline
handling, stale leases, path validation and geometry refusal. It moves no sprites
and is not a substitute for paired native/authority or rendered multi-client QA.
