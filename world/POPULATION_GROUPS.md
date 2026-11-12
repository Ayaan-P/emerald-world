# Persistent agent-authored populations (draft)

The existing `world.populate` capability still creates an original character or typed prop. `world.populate_group` now admits two to four definitions together on one exact supported generated revision. Its arguments are `revision` and `definitions` (a JSON list, maximum 700 characters, using the same individual definition fields as `world.populate`). The configured author discovers it through the normal capability catalog; there is no fixed cast or scenario.

Every identity, tile, character/team definition and joint route is validated before staging any member. A duplicate identity, occupied player tile, blocked route, unsupported geometry or capacity failure rejects the whole group. A pending request is not success. Only normal mechanic admission produces a result naming all actual members. Created NPCs use existing enrollment, model budgets, movement, optional challenges and public interaction systems; creation is not evidence of a model turn, catch, birth or travel.

Players select an existing compatible generated destination and see the admitted characters or props through normal region snapshots. Native object/capability admission remains unchanged. A client without prop support cannot enter a prop-bearing region; this feature does not silently downgrade it.

## Long-lived source behavior

Population uses one verified reusable source projector with a retained entity catalog instead of adding a function/wrapper per creation. The artificial sixteen-population-receipt stop is removed. Immutable receipts remain in admitted state and ordinary committed history; existing creations and individual identities are not replayed or reset. Previously emitted append-only projectors are preserved, not rewritten. Unknown/tampered reserved dispatchers fail closed.

This is not unbounded population: the unchanged budgets remain 32 persistent world characters, 64 catalog objects, eight objects per exact map/revision, 64 KiB state and 256 KiB source. Retired character identity remains reserved. Additional population is refused at the actual budget rather than discarded, silently despawned or claimed complete.

## Verification and ancestry

Authority tests exercise twenty actual population admissions across three distinct generated places, one projector, persistence after restart, joint creation, bad-second-member rollback, original identity safeguards and existing spawned-NPC navigation. They use the existing in-memory transport fixtures, not a rendered game or live provider.

Based on #372 at 6bf6fc3c80bc941231fdf6723657b4d02e0c074d; native pin unchanged. This feature stack diverges from released RC12 and does not incorporate Maya's release fixes. No native changes or denied-upload payloads are included. Maya owns integration, linked playtesting and release.

## Independent resident authors after batch admission

The optional future-population lifecycle now covers single population, original native residents, mixed population groups and complete procedural adventures. Previously it recognized only the two single-character tool receipts. This is not automatic model startup: the host must already have enabled the future-population policy and enrolled the creating actor, and a configured author worker must be running separately. Existing provider choice, attempted-turn budgets, polling and eight-followed-character limit remain. No live provider was used to test this change.

A new resident qualifies only when the lifecycle observes both its actual first `character_changed` admission (version 1, no previous character) after opt-in and a successful reviewed creation receipt naming that character. A pending request, prop, old imported identity, restored archive, pre-opt-in admission or repeated successful adventure publication cannot enroll an older character. No retroactive identity linking or fictional experience is added. The first turn uses the child's current version, goals, real position and its own creation evidence, not its creator's plan.

Eligible residents wait durably if the existing eight-author capacity is full. Freeing a slot can admit a waiting resident on a later inspection without replaying the creation or raising the limit. An unfinished current plan defers that first turn. This is not rotation: the host still decides which existing subscriptions to stop, and waiting does not promise an eventual turn. Disabling the policy cancels waiting admissions; explicit unfollow also cancels a waiting child. Removing the creator's enrollment cancels still-waiting children. Existing active children remain independent under the established lifecycle. Re-enabling does not resurrect cancelled admissions. Ordinary queued turns are interrupted on disable; this does not claim to undo an already running author or committed action.

Batch members have distinct durable request identities, even when they share one creation receipt. Restart retains waiting/admitted/cancelled status and does not duplicate initial turns. Manual host enrollment takes precedence. Existing per-actor budgets still count attempted claims and survive restart; they are not dollar caps. If no author is configured or the host leaves the feature off, the admitted NPCs remain ordinary authored characters.

The independent draft follows #456 at `6633d637783392f9147f0d8defe65f55dcdbf511`, with native #100 unchanged. Tests create a real procedural adventure and prepare separate resident turns, then feed hand-written independent decisions through the normal character-action compiler and authority runtime. The two residents open different actual native retail catalogs visible on existing shop snapshots. These fixtures demonstrate that ordinary capabilities can execute, not autonomous model behavior, a rendered shopping session or a guarantee of interesting decisions. Capacity waiting, restart, cancellation, pre-opt-in replay rejection, mixed character/prop receipts and existing lifecycle budgets are tested. Integration candidates and held actions remain untouched.
