# Original Hoenn collision planning prerequisite

This draft adds **no visible gameplay, movement dispatch or native admission**. It does not make world characters walk on original maps. It is an independent prerequisite for that future integration, not a replacement for it or a workaround for any held native operation.

## Implemented

`world/hoenn_collision.py` builds a conservative collision catalog from exact native map blocks, per-map primary/secondary metatile attributes, behavior enumeration, map groups/layouts and original events. Every input must match its recorded Git blob SHA; the manifest pins native #131, commit `377a7892e12ebcde149befa33d99c64c3b19342a`. No donor assets are imported. The committed catalog is derived facts, not a new region or a guessed collision bitmap.

Initial real maps: Route102, Route103, Route104, Route116, OldaleTown, PetalburgCity and RustboroCity. The builder can be extended with newly verified sources, but unknown layouts, attributes or ABI changes fail closed.

It preserves the 10-bit metatile / 2-bit collision / 4-bit elevation interpretation and 8-bit Emerald behavior field. Only an explicit ordinary, direction-independent walking behavior allowlist is admitted. Water, ledges, bridges, transition/multilevel elevations, unknown behavior, nonzero collision, borders/map connections, warp/coordinate/background event cells and every stock NPC's declared movement range are excluded. It never assumes a hidden-by-flag NPC is absent. It intentionally rejects some routes the native player could traverse.

The catalog retains actual collision/elevation/behavior facts and immutable map digests. Script mutation indicators are advisory, not an exhaustive analysis of script effects. For example Route103 contains `setmetatile`; no static map is treated as proof of current player-specific state.

## Pure authority planner

- `preview(...)` returns a bounded cardinal static candidate explicitly labeled `static_preview_not_executable`.
- `plan(...)` requires the exact nonempty set of current authenticated observer sessions supplied by a future trusted authority caller. Every view must be complete, at most two seconds old, match the map digest/map number/elevation/walking mode and authority epoch, and include current collision-safe cells plus occupied/blocked cells.
- Allowed cells are the intersection of all views and conservative source cells. One player's closed path or occupied tile therefore blocks the plan; another save's open route cannot overrule it.
- Routes stay on one map and one unambiguous elevation, have at most 64 steps and never warp. No Surf, ledge jumps, scripted travel, original-character relocation or cross-map teleport is implied.
- `revalidate_step(...)` checks current views, epoch, per-session revisions, adjacency and current occupancy again. Stale/disconnected/missing observers or changed revisions require replanning. A plan is not a reservation or execution receipt.

**There is currently no authenticated native survey collector or production caller of these APIs.** Tests construct synthetic views. The `complete` field is a future trusted collector contract, not something an arbitrary client may assert to gain movement authority. Runtime integration must validate view provenance, membership/epoch changes, active scripted movements, dynamic terrain, occupancy and every actual native step. Do not wire this directly to user-authored JSON or generic position updates.

## Verification

Eight tests pass against the generated seven-map catalog and exact pinned input files. They cover source hash corruption, complete deterministic regeneration, real ordinary route candidates, collision/elevation/warp exclusion, private-save-view intersections, stale/wrong/incomplete/missing observers, revision/epoch invalidation and newly occupied next steps. No real saves, live providers or native gameplay execution were used.

Run `python -B test/test_hoenn_collision.py`. The exact-source regeneration test requires the pinned native submodule's source/assets; it explicitly skips if the checkout is absent, while catalog/planning tests still run. To regenerate:

`python -B world/hoenn_collision.py engines/expansion-native --manifest world/hoenn_collision_sources.json --output world/hoenn_collision_catalog.json`

## Still blocked / not changed

The existing native `world_bridge.c` `CharacterWalkLine` requires `characterRegion` and rejects ordinary unrevisioned maps. This draft does not modify it, send a false generated revision, emit CHARACTER_WALK, mutate actor state, or fake walking through coordinate snapshots. Native collision survey and an appropriately reviewed original-map walking protocol remain future work. Maya's integration/release and all held operations remain untouched. The denied persistent-Cut native commit and its matching app candidate are unrelated and unchanged.
