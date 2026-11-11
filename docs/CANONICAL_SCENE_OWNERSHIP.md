# Shared original-actor scenes

## Paired implementation

The canonical author may offer `scene: "rydel_step"` on the existing Rydel record.
After talking to original Rydel, a trainer uses `/history scene ask`. Every connected
trainer must be ready in the Bike Shop with scene support. Each must explicitly
`/history scene join`; `/history scene cancel` declines. Private in-game notices
announce invitations. Explorers elsewhere are not pulled into a cutscene.

The deliberately small first scene moves **the original Rydel object** one tile
east and then home using normal native held movement. Every observer acknowledges
each completed step before the next starts. Joined trainers' field controls pause;
B cancels and initiates a real walking return. Bike-service bytecode, items, flags,
NPC templates and save layout are unchanged. This is physical synchronization,
not a bike lesson, follower, autonomous journey, training or predefined story arc.

The ownership primitive supports the broader cast, but the live runner permits
only this reviewed fixed actor/room/path. It does not move Wally, Briney or Steven
through potentially conflicting story scenes or spawn duplicate original actors.

## Real protocol and collision path

A nonce-bound CORE `SCENES native private` probe precedes scene messages. Older
servers refuse it safely; no new protocol is sent before positive negotiation.

The authority checks the current authored invitation/version, recent original
Rydel conversation, fresh room presence and the exact cohort of connected clients
(up to four). Native PREPARE verifies the real map/local ID/graphics/home position,
absence of scripts/battle/field locks, and actual collision/elevation behavior.
Native reservations cover both home and adjacent tile before ACK. Both ordinary
and flag-based engine collision queries respect this reservation; only the managed
original actor is exempt.

All clients ACK before STEP 1. Each uses actual held movement and sends AT only when
it finishes at the expected tile. The authority waits for every observer before
STEP 2 returns home. An early RELEASE cannot unlock a moving actor. No teleport is
used. Every HOME receipt is required to finish the transaction. Returned clients
can resume controls while their path reservation remains until release.

New game connections are temporarily refused while a live scene owns the room;
they can retry after restoration. Control/admin connections are unaffected.
A connected legacy client or trainer outside the room prevents scene admission.
No public scene completion, relationship or training credit is invented from these
native attestations, and private player history is not shared with authors.

## Cancellation and durable recovery

Preparation has a three-second deadline; active execution has ten seconds.
Deadline, B cancellation, failure or disconnect requests restoration, not presumed
success. Native disconnect handling continues the real return, retains reservation
until home, and unlocks. Failed HOME sends can retry; the scene itself is not replayed.

Before PREPARE, the server persists token, map, exact trainers and save lineages with
unresolved restoration. Restart reloads this debt and refuses a new scene until
matching saves certify the actual original actor idle at home. Native recovery
waits for the Bike Shop and checks its original object. Another save for the same
trainer cannot clear the debt. Normal play remains available while recovery is
pending. Missing participants can defer future scenes until they return; there is
no unsafe forced release or fabricated restoration.

Unexpected original scripts or battles keep their own controls and movement; the
scene relinquishes ownership rather than overwriting them. An interrupted actor
away from home may require leaving and returning to the room for recovery.
Unexpected map/object replacement never writes to a reused object slot or reports
HOME. Returning to the reviewed map/save permits recovery. Resets, loads, process
crashes and unusual field-task interruptions remain important integration QA.

## Source verification and remaining QA

Reviewed baseline: engine PR26 `b5504fd4e433f0cd3ea04c8c99487b5ec9754b7a`.
`ObjectEventSetHeldMovement` unfreezes the original object; `ScrCmd_release` does
not restore coordinates. This necessitates coordinated restoration, not a local
uncontrolled walk hook.

Exact Bike Shop map blob: `9891b9fd56e30d829c5d09cdbacd663e50deca03`. Rydel's home
is (2,5), local ID 1, MAN_2 graphics. The next tile (3,5) has the same raw floor
entry `0x323f`, collision 0, elevation 3; neither is a warp. Runtime checks still
win if an occupant or another condition makes it unsafe.

`test_canonical_scenes` pairs two compiled production native controllers with the
actual authority dispatcher. It checks barriers, step acknowledgements, return,
restart, lineage fencing, occupied paths and legacy refusal. Engine globals,
collision responses and sprite motion are explicitly doubled. Native tests cover
disconnect, reused objects and actual CORE capability reply/refusal routing.

This is **not** a full linked build or rendered multi-client playtest. Maya must
verify actual drawing/held-animation timing, controls, chat interruption, network
loss and save/reload before integration and release. The app engine pin remains
unchanged in this draft batch.
