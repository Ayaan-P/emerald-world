# Autonomous cast construction

A retained construction intention now has a real authority-executed consequence:
a connected courtyard and access path added to an existing generated outdoor map.
No player is asked to visit, gather resources, accept a quest, or finish the work.
This is abstract world-project execution, not a claim that a native NPC walked to
the site or that labor was animated/simulated.

## Reusable author contract

Any registered original actor can retain:
- worksite: exact source revision, literal label, existing outpost plan
  {x,y,width,height,gate,reservations}
- intention: id, kind construction, target equal to the source revision, reason

Existing typed canonical author admission still requires inspected public evidence.
The authority loop evaluates pending work between mechanic jobs, at most one
successful project per five seconds. Each actor can complete at most eight
projects. This does not require a player event or another model request.
No project is seeded by default: a configured author must first choose and commit
the actor's intention. Model output is fixture-tested, not live-model verified.

The existing plain XL construction compiler preserves all prior walkable tiles,
adds a bounded 5..15 tile courtyard with an access path, refuses overlap/reserved
terrain, and enforces connected geometry. Only a durably published plain XL
shared map is eligible. Other formats are refused rather than losing their
wildlife or palettes.

## Publication and safety

The exact source map must still be active, the shared area must be empty, and no
mechanic deployment, pending character battle/offer, or scoped NPC walk may be in
progress. A changed/occupied/busy source waits without a public success event.
Withdrawal of the intention cancels uncommitted work. Normal original maps,
story flags, gifts, trainer parties and player saves are untouched.

Existing same-place migration preserves compatible scoped NPC positions and
source bindings. Immutable opened-region placements cannot be migrated.
Map archive, place continuity, character rebinding and construction receipt share
one transaction. A receipt failure rolls back the geometry. One actor/intention
receipt prevents repeating construction after restart or a lost response.

The completed event contains the actual before/after revisions, footprint,
access trail and added/preserved tile counts. This is the committed result, not
an authored assertion of success. It can queue the owner's next goal decision.
Authors cannot mark a construction intention fulfilled themselves.

## Visible effect and limits

Entering the new active generated map reveals the real added courtyard and path
using the existing native outdoor palette. There are no new building sprites,
shops, resources, crowds, actor travel, or reward claims. /guild cast ACTOR
construction exposes pending/completed projects; the world journal describes
the committed map change. Existing studies remain attached to their old exact
revision and are not silently migrated.

Tests execute the real compiler, persistence and authority dispatcher without
player participation; prove occupied-map waiting and later execution, one-time
receipt/restart, withdrawal, stale-source refusal, rollback, and actual result
feeding a new character goal. A component test compiles the exact current native
StageXLWilds and accepts the constructed bytes while rejecting damaged bytes.

This batch is app-only. Native PR26 remains unchanged and the app engine pin is
not moved. Full rendered play and integration remain Maya's QA/release gate.
