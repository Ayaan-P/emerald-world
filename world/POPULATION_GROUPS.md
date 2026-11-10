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
