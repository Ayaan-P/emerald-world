# Shared move feedback (experimental)

Stacked on app #411 and native #73, not released RC12. Frozen #384/#56 are untouched.
Use the existing default-off `--development --experimental-field-moves` launcher path.
Party → WORLD MOVE → a learned move → an authored action → confirm. The selector
previews the visual family and retains the public move/action disclosure. The server
still commits only the authored prop/network action; this does not add a fixed puzzle.

## Real effects
The native engine's static move type selects reusable cosmetic feedback:
- Water: stock large splash.
- Grass/Bug: stock jump-grass leaf burst.
- Normal/Fighting/Ground/Rock/Steel: stock ground-impact dust.
- Other types: stock sparkle (not a bespoke fire/electric/ice animation).

No inferred elemental world rules: authors decide which learned moves satisfy each
action, and what validated object changes result. These visual families neither
mutate tiles nor spend PP, award experience or modify a player Pokémon/save.
Dynamic battle type conversion is not evaluated outside battle.

An admitted `object_move_committed` event delivers one best-effort FM FX receipt to
opted-in nearby clients on the same exact generated-place revision. It covers player
menu/command actions and NPC `world.use_move`, sharing the existing authority path.
Player move evidence remains client-reported; NPC evidence requires the existing
current native individual-move inspection. No new party data is sent. Clients without
the experiment do not subscribe. Historical/reconnected events are not replayed.

Transport: client FM WATCH 1 → server FM WATCH 1; server FM FX seq group num x y move.
Only the authenticated current link can subscribe. Server filters ready, fresh presence,
exact cave ACK/revision, map, distance (10 tiles per axis), and no link session. Client
checks sequence, map/range, actual field state, battle/script/link exclusions and sprite
capacity, then runs the stock effect once. Busy visuals can be dropped, not queued
indefinitely. Cosmetic loss never changes an already admitted gameplay outcome.
Escape after confirmation closes UI but cannot cancel an already submitted action.

## Verification and limits
Component tests compile the actual native feedback/controller code with fixture engine
state; test type families, map offsets, default-off, duplicate, disconnect reset,
wrong map, distance, busy effects, full sprite pool and script suppression. App tests
exercise actual authority admission and second-client filtering, failed admission,
revision/freshness/distance, durable source metadata and no historical replay.
These are not rendered/native linked playtests. Stock sprite/palette loading and
callback cleanup, party-return timing, two-client visuals, save/load and frame pacing
still require Maya's linked QA. No live model calls. No denied file changes.
