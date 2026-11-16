# Composable space authoring

This draft extends app #300, which extends #299 and the living-cast candidate.
The native pin remains #32, `30a4fae1b19340225926d350895a30e516615a8c`.
No integration branch, release, native save or normal Hoenn map is changed.

`world.extend_space` is discovered through the existing actor capability catalog.
A world-owned actor supplies its exact current revision and `blueprint`, a JSON
string (at most 800 characters, also subject to the normal 1024-byte step bound):

- `seed`: integer 0..4294967295; deterministic route preference.
- `landmarks`: 2..12 distinct `{id,x,y,radius}` clearings, radius 2..10.
- `reservations`: at most 32 `[x,y,width,height]` no-build rectangles.
- `loops`: 0..4 extra alternative connections.

The existing `route_landscape.compile_plan` connects clearings and native
endpoints around reservations. Plans choose spatial parameters, not exact paths
or canned quests. Clearings and reservations must fit within the 1..125 interior.
The resulting floor is unioned with existing floor, never replacing it. A
reservation overlapping existing walkable ground is refused rather than silently
erasing it. The final SharedCave validator checks format and connected geometry.
The receipt's landmark labels describe requested geometry, not invented visits,
biomes, items, resources or local lore.

## Actual execution and composition

The capability commits a new immutable revision through `_replace_cave`, retains
the logical place identity and existing actors/props at their positions, and
atomically writes the tool receipt. A subsequent `world.navigate` can reference
`{result: "build", key: "revision"}` and travel into the added space using the
normal movement executor. The model chooses the next plan; successful editing
does not assert construction work, training, travel or resource consumption.

Publication requires an empty active archived plain XL map (format 16), no
pending mechanic/character work, and all existing admission/rebinding guards.
Carried props must be placed first. Stale revisions, immutable opened regions,
wildlife formats, invalid/unchanged proposals and occupied maps are refused.
No player is warped or has their bag/save altered. Old revisions remain archived.
This is additive geometry within the existing 127x127 destination, not new
cross-map portals, original-map editing, custom tilesets or unlimited map size.

## Evidence and handoff

Actual authority tests cover two actors, new sparse geometry with over 100 added
tiles, protected reservations, preserving all old floor and logical identity,
restart/no replay, occupied-map refusal, atomic failure and
extend -> real movement executor -> arrived position. Compiler and authority run
for real in these tests; model choices are supplied as fixture plans. Native
source components are tested separately by the paired candidate. Full linked
native rendering, live model authoring and integration QA remain for Maya.
