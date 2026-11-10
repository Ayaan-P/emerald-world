# Real shared mechanisms inside optional campaigns

This connects existing agent-authored object networks to the existing private/shared native campaign board. It adds no fixed puzzle, native save field, reward, map format or new interaction executor.

Authors inspect `world.discover`'s `campaign_mechanisms` catalog, then use `world.publish_battle_campaign` with a node:

```
{"mechanism":{"network":"EXISTING_NETWORK","phase":"EXISTING_PHASE","definition":"CATALOG_DIGEST","label":"Player-facing objective"},"next":["ANOTHER_NODE"]}
```

Use real catalog values. The digest binds the entire network program and every member's admitted region revision. Existing battle, preparation, visit and route nodes can precede/follow it. Mechanism nodes are ordinary stages, not split-role tasks. Existing acyclic graph limits apply. Actors do not gain control of mechanisms owned by someone else merely by publishing a campaign.

## Player flow

1. Start/join an optional campaign using its existing native board.
2. At a mechanism stage, choose **Begin watching future changes**. This durably records the current public event watermark for this save-scoped run.
3. Play the existing object network normally. Ordinary A actions, explicit choices, learned-move checks and distinct-participant move gates retain their existing authority and client-report semantics. NPCs may act independently; the campaign never orders them to succeed.
4. Once an admitted object interaction actually transitions the network into the requested phase, stand adjacent to any member in its exact region and select **Check the committed change nearby**.
5. A private run offers authored next routes. A shared run waits for every participant's separate witness, then uses existing party route choice.

A previously completed state is not retroactive progress. Every party member should begin watching before changing a one-way mechanism. The system never resets a mechanism for a campaign. Authors should make reusable mechanisms when repeat runs are intended. If others reverse the state, checking fails until it is reached again. A successful earlier witness is retained, not silently revoked.

## Evidence, persistence and consent

Only the normal object admission path writes receipts, in the same database transaction as the actual world change. The receipt must have a new phase and exactly one turn increment, unchanged network definition, and a previously validated real object transition. Merely editing a phase, waiting on a timer, declaring an objective or visiting a tile does not qualify. Existing source compaction cannot remove these indexed durable receipts.

Watching and witness records survive server restart in the existing save-lineage run. Old transitions, different definitions/regions, stale player presence, current wrong phase, duplicate completion and other save lineages fail. No player action attribution is inferred: the record says `committed_world_transition_witness`, `presence=client_reported`, `attribution=shared_world_not_personal_action`. Another player or NPC may have caused the world change. Shared-party consent text includes mechanism witnesses. There is no new public player identity or inferred private activity.

Cancel/leave uses the existing campaign semantics. It never undoes shared objects, spends PP, grants items, changes native story flags, or changes another player's save. A client disconnect between world admission and checking loses no world receipt; the player can return and explicitly check if the phase still matches. There is no automatic completion or cross-save progression.

## Scope and verification

This is an app-only child of #431 (4cf5776cf46f93b3cba2e538da33885f67189bde). The native pin remains #82 (31b800a1376d68e6361e8c22a7ee0778f3adf897); it is not based on Maya's #410/#72 or released RC12. No held operation, native source or live provider used.

Focused integration tests execute the actual existing fixture INTERACT_REGION path, mechanic admission and object projection, observing a linked panel's position change before campaign completion. Coverage includes board action tokens, post-watch receipts, no retroactive completion, reversal, party waiting, SQLite restart, occupied-destination rollback, definition/region and save-lineage isolation. Existing campaign, split-party, runtime, object-network and cooperative-move regressions are run too.

The historical test fixture is not a rendered playtest of the pinned native engine. Full linked/UI/two-client controller QA remains pending. This composes optional generated-world mechanics with campaigns; it does not rewrite Emerald's core story or enable arbitrary live terrain construction. Existing experimental feature gates still apply.
