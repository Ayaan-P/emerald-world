# Shared directional object movement

`world.enable_pushing(object, revision)` turns an observed unused anchored prop into a shared movable body. An agent chooses the object, not a predetermined route or puzzle sequence. Existing text/appearance remain. The object must not already have a program, controls, actions, portable custody or a cave link.

## Actual player interaction

Face the object and press A through the existing native REGION_PROP interaction. The authority derives a one-cell push away from the player's actual admitted adjacent position. Other players receive the changed object in ordinary scoped snapshots. An autonomous character can use the same advertised `push` action through `world.use_object`; its own committed adjacent position determines direction. Neither client nor model supplies a trusted force vector.

This uses existing sign/pot artwork and snapshot repositioning. It does not add boulder artwork, a Strength animation, a following player step, native HM requirements, terrain editing or player inventory. Players manually step forward before pushing again. It is suitable for shared spatial arrangements without prescribing a puzzle or story. Existing spatial mechanism rules can observe nearby characters/players, but this change does not claim automatic pressure-plate or reward wiring.

## Authority and persistence

Pushes use the unchanged sandboxed object-action dispatcher, normal mechanic staging, collision validation and durable transition receipts. Geometry, other NPCs/props, warp tiles, complete route connectivity and player occupancy are preserved. Even players in a menu block destinations, and occupancy is checked again at admission. A stale, busy, blocked or unadmitted action does not move the object. Simultaneous input cannot independently apply the same staged move twice.

The direction literal is substituted only in a bounded, verified assignment belonging to the installed object definition. Existing handlers and old object dispatcher source remain compatible. Each successful push changes only the object's coordinates and bounded own state; current receipt rotation preserves the existing causal archive. A regression performs 37 pushes without accumulating request wrappers or hitting a lifetime interaction limit. Positions persist across subsequent mechanic ticks and authority restart.

No source/state/object limit is raised. This supports the existing generated-place object system, not movable original Hoenn story objects. There is no promise of native animation or latency-free pushing; linked/rendered co-op verification remains necessary.

## Integration

Stacked on #357, native #49 unchanged. The cumulative candidate is not based on released RC12. No uncertain outdoor-region operation, native upload, original campaign/save edit, merge or deployment is involved. Maya owns integration and final linked/rendered QA.
