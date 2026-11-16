# Autonomous generated-world journeys

Existing persistent world characters can now follow an authored journey of
2..65 unique cardinal points on one exact archived generated-map revision.
The authority executes it independently; no player errand or follow action is
required. This uses the already published native CHARWALK1 held-movement bridge.

The ordinary character_actions response accepts journey instead of walk, with
the replacement object at the final endpoint. It consumes one action publication.
The trusted reducer chains six-point native walking segments, preserving identity
and team. Each segment has a stable movement ID and a versioned transition.
No new native protocol, engine upload, or player-save format is introduced.

## Safety and persistence

The entire path is checked against exact archived walkable geometry and current
world objects before departure. Steps are cardinal and cannot repeat, skip,
rewrite, or change revision. Ready player occupancy and other world objects
cause movement to yield. This is bounded authored navigation, not automatic
pathfinding or deadlock resolution. An unavailable route may need a new action.

The durable control stores the full journey, current segment and native step.
Restart resumes authority position. A versioned action can cancel or replace
the journey. Battles/offers remain gated for the entire journey, including the
pause between native segments; legacy clients hide the moving character until
the full journey ends.

Only actual final authority arrival produces a one-time public receipt. The
receipt gives exact map revision, start/end, committed step count and actor
identity. It does not expose player names or credit player travel. Native clients
may still be animating; authority arrival is not proof every observer rendered
every frame. New observers join at current authority position, and severe
snapshot loss can require ordinary native position reconciliation.

## Existing cast connection

Original Wally, Briney, Steven and Rydel are not relocated or duplicated. Their
ordinary scripts and services remain intact. An authored canonical record can
watch up to four existing exact archived revisions through journey_interests.
Actual world-character arrivals there can inform that actor's next decision.
This is awareness of a public authority result, not an invented physical meeting.
Other revisions sharing the same generated map ID do not match.

## Verification

Tests execute actual authority validation/commits over a 19-step multi-segment
journey, player collision yielding, segment-boundary interaction gating, restart,
single final receipt, invalid-route refusal and exact-revision cast relevance.
A C component test compiles the current published SyncCharacterWalk function,
feeds snapshots from that authority journey and verifies all 19 held movement
steps reach the endpoint without teleport reconciliation. Native object APIs in
that fixture are explicit stubs, not a rendered game or full collision engine.

Full native rendering and integrated gameplay remain Maya's QA gate. No native
source changes or app engine-pin update are included in this batch.
