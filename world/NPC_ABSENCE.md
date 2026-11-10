# Temporary absence and safe return

Independent draft on #425 (`0c94a810ab19a42fea0aaca265d9ff1f7331e81c`), not Maya #410 or RC12. Native #79 unchanged. No held files/operations or live providers.

An active generated-place NPC can independently choose `world.take_leave(seconds)` for 60..86400 seconds. Its existing optional expedition offer must first be withdrawn, and it cannot be walking or have a frozen player battle. The normal character compiler/admission removes the real rendered object and changes status to away. The duration starts only after admitted departure is observed.

The same pending capability retains the original individual record and exact placement. After the interval, it revalidates the original current/opened revision, geometry, object collisions, corridor connectivity and player occupancy, including menus. It stages ordinary character admission to restore the same object and active status. Admission rechecks the exact target/revision and live player occupancy, closing the staging race. Cached challenge requests are rejected while the lifecycle is pending. No automatic relocation to another map or tile.

Name, goals, relationships, team, companion state and history are retained. The actual character version advances for departure and return. No off-screen travel, resting benefit, healing, training, friendship, item gathering or other simulated accomplishment is asserted. This does not free the 32-live-record capacity or resurrect retired archives.

## Recovery and control

Pending lifecycle data is durable. Restart while absent preserves the interval and original target. A wall-clock rollback preserves remaining duration rather than shortening the absence. A return that was staged but not admitted retries only after fresh safety validation; a real admitted return is recognized before staging again. Unsafe occupancy/revision leaves the character away and reports why, rather than forcing entry.

Replacing the pending plan, changing the character externally, or failure of departure yields a blocked/unconfirmed lifecycle, never a fabricated return. A deliberately interrupted away character needs an explicit subsequent authored action/host decision; there is no secret respawn. Exact original geometry becoming unavailable may leave the return waiting indefinitely. The runtime does not claim a new route or relocation.

For automatically enrolled population NPCs, only a genuine pending `world.take_leave` receipt preserves the existing enrollment while away. It does not enroll arbitrary absent characters, reset budgets or reactivate a host-stopped subscription. Explicit unfollow still stops future author turns; it does not cancel an already committed world action's safe return. Existing action plans/authority continue independently of model polling.

Players can inspect `/guild npc availability ID`; authors see `actor_runtime.character_absences`. Status is the lifecycle state, not a report of off-screen events. This uses existing command UI and object transport, with no new native animation or disappearance effect.

## Tests

`test_npc_absence test_actor_runtime test_population_agents test_character_reactions test_region_characters test_characters test_npc_goal_reviews test_move_assistance test_author_capability_loop`: 59 tests, 57 passed, two existing sandbox/provider skips. Actual authority object removal/reintroduction, identity retention, restart, occupied tile, menu occupancy admission guard, changed-revision wait, battle refusal, enrollment/unfollow, unadmitted departure and rollback tested. `git diff --check` clean.

No rendered two-client/native build or live-model QA was performed. Existing native object replication is reused; a component test is not a visual playtest.
