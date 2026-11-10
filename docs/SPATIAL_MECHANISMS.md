# Cooperative spatial world mechanisms

Agents can now use the existing `world.program_network` capability to build
mechanisms driven by actual nearby players and recurring NPCs, as well as native
A-button interactions. No predefined puzzle, character role or story is installed.

## What players experience

In an already supported generated place, two to four anchored props can change
appearance, text and position together when authored proximity conditions hold.
For example, players can cooperate by occupying different nearby zones, or a
mechanism can respond to an NPC's actual arrival. These are examples of composition,
not shipped content. Other players receive the same committed object snapshot.

The visible changes use the existing native prop renderer and collision objects.
There is no new pressure-pad graphic, sliding animation, terrain editing, reward,
item transfer or original-Hoenn override. Props can move only one tile per
transition and remain within one tile of their original anchors. All placements
must preserve the area's connected routes. Thus these can change local obstacle
arrangements and shortcuts, not lock every route behind a puzzle.

## Author interface

Each state in a network's existing `program.states` may optionally include
`when`, an ordered list of up to two rules:

- `to`: another state in this network.
- `mode`: `all` or `any` across its zones.
- `occupied`: whether the combined condition must be true or false.
- `hold`: 1–30 seconds of continuously sampled eligibility.
- `zones`: one to four `{x,y,radius,players,characters}` records.

A zone uses Manhattan radius 0–2 and minimum counts of 0–4 players and 0–8
characters, with at least one nonzero minimum. Its center must be walkable and
within four tiles of a network member. A player can satisfy multiple overlapping
zones, so authors should use disjoint zones if distinct participants are intended.
No participant identity, private save, party or chat becomes part of this state.
The existing 2,600-character definition limit and six-state limit still apply.

Counts come from authenticated, ready, at-most-three-second-old field reports
with the exact generated revision ACK, or active authoritative world-character
positions in that same map and revision. Menus, stale state, another region and
disconnects do not activate zones. Position reports are client attestations, not
anti-cheat proof. A last-known occupied destination remains protected even when
a trainer is in a menu or stale; the transition waits rather than placing an
object on them. Original character locations are never fabricated.

## Execution and recovery

Rules run during normal mechanic admission, not through repeated model calls or
source rewrites. One rule can advance a network per admission. Explicit object
interactions take precedence in that admission. The first eligible rule whose
proposed placement is not occupied wins; all existing placement and collision
validation still follows, and the entire state/object change commits atomically.

Committed phase, turn and object appearances survive restart, and actual object
changes enter the existing public mechanic history. Hold timers intentionally do
not survive restart: an interrupted hold must be observed again. No offline time
is treated as continued participation. There is no lifetime interaction counter
or per-transition generated-source growth for these spatial transitions.

Mechanics are sampled at the configured authority tick rate; this is not a
frame-perfect switch or combat trigger. Actors can inspect and react to the
resulting shared objects/history through existing capabilities. No model output
or victory is invented.

## Verification and integration

Tests drive actual authenticated positions and the production mechanic admission
path into native REGION_PROP snapshots for two observers. They cover multiple
players, actual NPC presence, revision mismatch, stale/menu state, disconnect,
occupied-destination postponement, restart persistence and invalid distant zones.
Existing manual network interaction regressions remain covered.

This is app-only atop #353, retaining native #49 at
be08691d7e5b9d3cb19fdfed0e742849180d8297. No new native protocol or pin change.
Component checks do not constitute rendered multiplayer QA or live model testing.
Maya owns integration and playtesting. This stack is not based on released RC12;
preserve app f484577b606348d07337387f14f75ab8cf4970b6 and native
f7a813317d1b9fec803b48b682f5d74245c79037 when integrating.
