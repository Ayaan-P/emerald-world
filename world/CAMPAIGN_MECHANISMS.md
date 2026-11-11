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


## Field expeditions with alternative real outcomes

The optional `expedition` node lets an author offer two to four valid outcomes of an existing mechanism. Players act in the world to produce a resolution, rather than select a success claim on the board. It can precede or follow the existing battle, preparation, visit, split-party and mechanism stages. There is no bundled story, new native executor, reward or automatic NPC enrollment.

A node contains only `expedition`, with `network`, `definition`, `label`, and `resolutions`. The latter maps real phase names to `{ "label": "Readable consequence", "next": ["existing_node"] }`. An empty route list ends the run. Use the exact `campaign_mechanisms` discovery digest. Every phase must exist in that mechanism, every route must exist, and the full immutable graph remains bounded and acyclic. Routes across all resolutions are limited to four distinct next nodes. Authored labels describe the actual mechanism; they do not authorize effects outside its ordinary validated program.

The native campaign board shows the destination, alternative resolutions and next routes. Each trainer explicitly readies. Only when all current party members have readied is a common durable event watermark installed. Players should wait for that readiness count before interacting. This does not lock or reset public objects: an outsider can still act first, and an irreversible early change can require cancelling the run. Readiness is consent to share a later observation with the run, not proof of travel or contribution.

Then use the normal object choices or learned-move interface. Existing cooperative move gates can require distinct participants; NPCs can independently contribute under their ordinary capabilities. Once a genuine admitted transition reaches a resolution, stand beside a member of that mechanism and explicitly witness it on the board. The first valid party witness fixes the run's resolution. Everyone else must separately observe that same current phase; an opposite outcome cannot silently send different players down different routes. If someone reverses the mechanism, restore the chosen state or cancel. No automatic restoration, invented action or inferred victory occurs.

After everyone witnesses it, only that resolution's routes become available. The existing speaker/advice/regroup controls apply. A solo run uses the same fresh-event and nearby-witness rules. No old transition or initial state counts. Stale menus recheck the requested phase, exact definition, save lineage and fresh place. Readiness, resolution and individual receipts survive database restart. Leaving retains the actual public object state and does not alter native saves.

This app-only extension is a child of #452 at `8c9cbbd343767713e1d282db15fbdb0e0c5ce9d6`. It retains native #100 at `bd88c0f08e1eea42297130c34b8e5ffbdb123a6c`; it is not a change to the integration candidate or released RC12. Existing experimental gates still apply. Authority integration tests exercise real object admission and movement of the linked panel, alternative route selection, party readiness, conflicting witnesses, stale board tokens, source-bound author publication, cancellation and SQLite restart. They are not a rendered native or two-controller playtest. Full linked gameplay QA remains required.
