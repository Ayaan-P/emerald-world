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

The native campaign board shows the destination, alternative resolutions and next routes. Players can opt into **Follow field stages** once for their current save-bound run. This authorizes sharing their fresh nearby observations with that run, including later field stages, until they stop or end the run. It is not consent to claim action credit, proximity while absent, or outcomes from another save. The board offers a stop control even while waiting for other participants.

Following uses the ordinary authenticated STATE path. When a player is fresh, ready, idle and beside the exact revision-bound mechanism, an actual current resolution with a durable admitted transition records an observation automatically. An earlier transition is valid: a later arrival can see its current result without making anyone reverse and repeat it. Initial declarations and phases without a real committed transition do not qualify. A private chat confirmation announces the observation; repeated STATE messages do not duplicate it. No further manual witness button is required.

The first participant's accepted resolution selects the party's route. Other participants who observe that same current resolution can follow automatically at different times. If the world has since changed, or someone cannot visit, the board offers an explicit **Continue via recorded outcome** alternative for the selected resolution. Before any party resolution is selected, it offers only authored resolutions backed by real admitted transitions. This is voluntary route agreement based on an earlier record, not a claim of visiting, witnessing or contributing. Its history uses `voluntary_recorded_outcome_continuation`, `presence=not_asserted`, `current_state_observed=false`. It never substitutes a fabricated battle win. The actual shared mechanism remains untouched, even when the selected historical outcome is no longer current.

Automatic observations instead use `observed_committed_current_state`, client-reported nearby presence, and no personal action credit. These distinct records survive restart. Both paths revalidate the exact current mechanism definition and save/run membership; neither accepts an initial state, missing receipt or arbitrary phase. All current participants must independently observe or agree before the shared route advances. This does not silently remove an absent player or waive their consent. Existing speaker/advice/regroup and explicit cancellation remain available. Removed/redefined mechanisms fail closed rather than inventing a continuation.

The older `expedition-ready` / `expedition-check` commands retain their original strict post-watermark semantics for compatibility, but the board no longer requires that workflow. Existing single-outcome `mechanism` stages and battle/visit stages are unchanged. The broader free-play mode from #461 remains available without any campaign enrollment.

This app-only extension is a child of #452 at `8c9cbbd343767713e1d282db15fbdb0e0c5ce9d6`. It retains native #100 at `bd88c0f08e1eea42297130c34b8e5ffbdb123a6c`; it is not a change to the integration candidate or released RC12. Existing experimental gates still apply. Authority integration tests exercise real object admission and movement of the linked panel, alternative route selection, party readiness, conflicting witnesses, stale board tokens, source-bound author publication, cancellation and SQLite restart. They are not a rendered native or two-controller playtest. Full linked gameplay QA remains required.


## Review and install through the local launcher

Local worlds → Author content → Authored adventure accepts a complete campaign JSON graph from the player or an author. It does not call a model. Current adventure building blocks expose only existing public world opponents and mechanism definition digests. The review shows each stage, actual map/tile destinations, routes and original JSON, including public team/preparation and exact region data. No canned campaign is inserted.

The preview uses the same pure graph validator as agent publication. Apply requires explicit review confirmation and all games closed. It revalidates dependencies and the world snapshot, installs the immutable graph under the distinct local workshop author identity, and reads it back. Another author's ID cannot be adopted or overwritten. Exact repeat installation preserves current runs. Uncertain responses are not automatically retried; reloading lists installed adventures.

After installation the launcher gives the correct solo or shared `/guild campaign` entry. Split-party graphs require a shared run. Each trainer starts or joins independently. Installation does not move players, create opponents, repair/reset mechanisms, execute agent plans, invent receipts, award items or change a native save. Travel, battle results and field interactions remain subject to the normal game and authority checks. This is local-host authoring only, not remote hosted management. Durable generated-world hosting is required by the existing workshop.

This app-only workshop follows #453 at `e897a38ef1e45e9ef9719af01dbc61eedf8813f2` and retains native #100. Launcher production build and browser-component tests are separate from a native gameplay playtest. Native linking and rendered two-player QA remain outstanding.

## Continuity validation

The app-only continuity change follows #462 and retains native #101. Tests exercise actual admitted changes before readiness, a later player's fresh STATE observation, once-only reporting, differing current states with explicit historical-route agreement, no initial/missing-receipt completion, opt-out, stale definition and SQLite recovery. Ordinary legacy readiness, battle/visit and run validation regressions remain covered. No rendered/native two-controller playtest or live model behavior is claimed. No shared reset, native-save changes, public player identity linking or provider calls are introduced.


## Optional challenges with honest exits

Battle nodes may add `decline: [next_node, ...]` alongside `opponent`, `win`, and `loss`. The adventure composer accepts this same form for its new residents. The alternatives use existing validated, immutable, acyclic routes; an empty list ends the run. Authors can place a difficult optional opponent beside a low-pressure field interaction and route declining players onward, without pretending they fought. This does not create items, unlock native story flags, or confer battle rewards.

At such a stage, the campaign board explains that ordinary trainer defeat may cause whiteout and money loss, shows the win/loss routes, and offers an explicit decline action. There is no harmless instant retry or automatic transport back. Players may prepare and heal through ordinary gameplay, leave the encounter prompt, or decline through the board before a battle starts. A live pending battle prevents decline. Older campaigns with no alternative retain their existing behavior.

Each shared participant makes their own decision. A decline is retained as `voluntary_challenge_declined` with `no_battle_participation`, not a win, loss, or native result. Other participants may still choose to battle. Once everyone has reported or declined, any decline selects the advertised decline routes; otherwise the existing all-wins/any-loss rule applies. Actual participants retain only their own client-attested battle reports. Nobody silently inherits another player's victory. Waiting for an absent participant is still possible; this change does not force their consent or remove them.

The private decision and selected routes survive server restart under the existing player/save-lineage binding. Shared world state is not reset. Cancellation, missing reports and disconnection are not converted into defeats or victories. A native result lost before acknowledgment remains a separate recovery limitation, not grounds to invent an outcome.

This app-only slice is based on #463, retaining native #101 unchanged. Tests cover the real campaign-board token path, mixed actual protocol reports and voluntary declines, both players declining, restart, wrong lineage, non-optional rejection, pending-battle rejection, immutable graph validation and ordinary campaign regression. It is not a rendered playtest, new native failure mode, persistent reward economy, or complete authored reference place.
