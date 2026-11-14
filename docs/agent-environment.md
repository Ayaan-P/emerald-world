# Agent-authored connected outdoor terrain

This candidate adds a public environment authoring capability to the existing
provider-neutral actor plan runtime. It does not add a scenario or NPC service.
An agent can inspect a public patch, choose grass, tall grass, water or the original
surface, then receive the actual durable revision. Subsequent plans can react to
the committed terrain event or receipt. The choice remains model-authored.

## Actual scope and entry

The host must already have an archived active **63×63 CAVE9 event outdoor area**.
This is the existing shared generated Wilds entrance, not Hoenn, selectable
regions, 127×127 XL geography or a new biome. Neither this feature nor its tests
activate a new world by default. `world.inspect_environment(x,y,width,height)`
inspects up to 8×8 cells. It returns public authority geometry and surface state,
not physical NPC eyesight, player identity or client reports.

`world.reshape_environment(observation,tiles)` consumes that actor's inspection
receipt and a JSON tile list (up to 700 characters). The world and terrain revision
must still match. The normal server executor preserves original endpoints and
cast placements, ensures remaining walkable ground stays connected and requires
all trainers to leave before applying geometry. Edits accumulate in the existing
512-cell overlay; `original` frees a cell, so the bound is simultaneous altered
terrain, not a lifetime interaction limit.

A compatible CAVE9G/H player later receives the real durable terrain snapshot.
Existing native surface rendering and movement rules apply: water is a water
surface, tall grass uses existing encounter behavior. No species table, catch,
Surf ability, player inventory or character labor is fabricated. Unsupported
clients cannot enter a terrain state they cannot reproduce.

The patch and successful capability receipt commit atomically, including no-op
completion. Failure to save the receipt rolls the terrain change back. Restart
preserves the overlay and completed plan; it does not repeat the edit. History
carries the actor's committed evidence. There is no cross-revision retargeting.

## Validation and integration

App branch is based on #334, with the unchanged #40 native pin. This reuses the
existing native terrain transport; no native edits or outdoor REGION1 changes.
Tests execute real authority plans, terrain validation/persistence, receipt
rollback, restart, second-actor plans and CAVE GET compatibility handling. They
are not a rendered playtest or a live model run. Maya still owns integration and
paired native grass/water/Surf/encounter QA. Do not infer autonomous physical
construction from an agent's authoring receipt.
