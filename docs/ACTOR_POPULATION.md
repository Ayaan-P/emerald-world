# Composable population

This draft extends #304. Native #32 remains pinned unchanged; the feature uses
its existing REGION_OBJECT/CHARACTER and distinct REGION_PROP transport.

`world.populate(revision, definition)` stages an original character or typed prop
on exact archived geometry. Definition is a bounded JSON string with id, kind,
x, y, gfx, text. A character adds name, role, goals and team (existing enabled
numeric species/level pairs); a prop adds an explicit portable boolean. Character
graphics are 7/8, prop graphics 0/1. A prop is not disguised as an NPC or native
item. Portable creation is an explicit authored world rule, not a bag grant.

The normal validators retain placement bounds, walkability, joint connectivity,
entry/exit protection, native cohort compatibility, stable identities and record
limits. Identity reuse, known canonical duplicates and overlaps with ready
players are refused. Newly populated characters have version 1, no invented
relationship, no prior experiences, and evidence referring only to actual public
history. Familiar cast still use their original canonical bindings.

Execution stages a source wrapper through the normal sandbox/admission path.
A pending tool receipt reports success only after the exact object and character
record are admitted. Failed/interrupted staging never claims creation. Retained
source/state keeps population through subsequent ticks and restart; subsequent
normal character actions can revise the new record and move the character.
Population does not itself launch a separate model process or pretend autonomy.
The existing host-author/reaction worker remains responsible for future choices.

## Composition and limits

A plan can create a place, pass its returned revision into world.populate, then
the new character can receive its own normal plan: navigate, observe, address,
use objects and other supported capabilities. Tests execute create -> populate
-> new actor navigation -> actual arrival -> observation. Props use the actual
separate prop snapshot and can opt into existing exclusive custody operations.

Supported locations are plain opened 31x31 regions and archived shared XL maps.
Wildlife-region population is still refused, preserving the existing guard.
This draft does not claim arbitrary native-map spawning, canonical replacement,
NPC travel to the new place, catches, new art or player-save changes. Region menu
use still requires the existing GENERATED_WORLD_REGIONS=1 build option.

Tests cover actual authority admission, independent plans for spawned actors,
authenticated region transfer/snapshot, props, invalid placement, canonical-copy
refusal, interrupted staging and restart. Full linked-native rendering and live
model choices remain Maya's integration QA; no merge/release is performed here.
