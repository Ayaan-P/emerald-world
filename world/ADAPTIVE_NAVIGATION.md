# Adaptive destination navigation (draft)

`world.navigate_adaptively` is an optional generated-world actor capability. Its arguments are an exact `revision`, destination `x`/`y`, and `max_steps` (1–256 committed cardinal steps). An agent chooses the destination; no named actor, fixed route or scripted scene is supplied.

The authority computes a real route from archived geometry and current public occupancy, then admits one ordinary character step. Only its existing arrival receipt advances the journey. Before the next step, route selection runs again. If a player or object blocks a staged step, the system admits an explicit versioned halt at the actor's current tile before choosing another route. It never edits a running path in place, skips a tile or moves a player. Menu/busy player positions remain obstacles.

Players with the existing matched character movement client see ordinary NPC walking. Original actors and Hoenn scripts are not relocated. Other capabilities retain their existing routing behavior. This uses the published authority/native movement protocol without new native code.

Journey state is durable. Restart after a step was admitted resumes its receipt/position checks without replaying completed movement. If staging or a halt was not admitted, the operation is blocked and requires an explicit new plan; it does not claim recovery or arrival. An unrelated character version/location change or changed immutable scope also interrupts rather than taking ownership of another action. Player battles pause navigation.

A fully obstructed destination waits without simulated progress. The agent may replace its plan. An already admitted single step may settle after replacement; no further old-plan steps are issued. The explicit step allowance bounds actual walking, not elapsed wait time or model spending. Exhaustion reports the real current tile as `navigation_step_budget_exhausted`, never arrival. Completion reports actual authority step receipts, not proof of rendered animation.

Validation uses actual movement reducers, versioned admission, occupancy, source generation and receipt persistence with in-memory fixtures. Tests cover a newly blocking player, halt and alternate route, no jump/occupied-tile traversal, a second actor exhausting its allowance, restart after admission, and lost staging. No live model or rendered gameplay was used.

Based on #374 at 63dc29f12802b7f1fcd88d1c78691e9caf41a7e3; unchanged native pin. This remains the divergent feature stack, not released RC12 or Maya's integration. All three denied uploads remain excluded. Do not start live direct-provider co-player sessions while the separate finite-budget correction remains unpublished. Maya owns integration, native playtesting and release.
