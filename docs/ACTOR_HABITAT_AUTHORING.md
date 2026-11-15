# Composable populated destinations

This draft extends #303, not Maya's integration branch. Native #32 remains
30a4fae1b19340225926d350895a30e516615a8c; no native payload is changed.

`world.create_habitat` composes the existing room/link compiler, enabled Expansion
species catalogue, native encounter encoder and persistent region publication.
Arguments are `label`, `blueprint` (as world.create_place), and `population`:
a JSON string containing `profile` (granite/meteor/ice/victory), `rate` (1..100),
and exactly 12 `slots`, each `[enabled_species_name, level]` with level 1..100.
The existing weighted wild encounter machinery interprets the slots. This is
actual native encounter data, not a character team, item grant or simulated catch.
Normal bounded plan/argument sizes apply; no network/model call is needed to
execute the compiled plan.

The authority creates a separate immutable format-10 cave, archives its complete
geometry and wildlife table under their joint digest, and opens its durable place
identity. It does not alter an existing place's encounters or switch the shared
map. Tables/species are validated before publication. Duplicate geometry+table
is refused; different populations have different immutable revisions/places.

REGION LIST filters these destinations out for clients lacking CAVE10, and
REGION SELECT refuses them before changing selected state. Existing CAVE GET
cohort checks still apply. A compatible Expansion client selects a region,
transfers/ACKs its exact table+geometry, then uses the normal generated-cave entry
and native wild encounters. The existing player party/save rules are unchanged.

## Boundaries and QA

Native region selection requires GENERATED_WORLD_REGIONS=1, still default-off.
Maya must enable/test that existing flag for a playable release. This is explicit
region selection, not seamless inter-map portals or NPC travel. Original Hoenn
maps are untouched. Character/prop placement and expedition-goal validators
remain conservative: this change does not silently add their support to wildlife
regions. No catches, victories, training or inventory changes are asserted.

Tests use actual authority authentication, catalogue filtering, exact byte/table
transfer, ACK, region entry, restart and invalid-species refusal. An additional
test compiles the exact paired native WorldCaveWire decoder and feeds the actual
authority stream; it checks format, encounter rate, species ID and level.
Full linked native encounter/capture/save playtest and live provider behavior
remain Maya's integration QA. Fixture plans demonstrate execution, not model
quality or an unobserved autonomous wildlife simulation.
