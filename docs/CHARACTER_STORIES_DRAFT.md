# Branching recurring characters (draft)

An agent may return `character_plan` and normal mechanic tests. The chapter compiler wraps the exact previous mechanic source and uses the existing staging, sandbox and authority validation. It does not activate a story by itself.

## Playable consequences

Each chapter supplies a native-map object, authored dialogue, goals, team and active/away/retired presence. Optional expedition offers use explicit native player consent and existing public guild goals. The same stable identity can therefore return with a changed team, move to another supported map, or offer a new expedition. Battle admission freezes the current chapter's actual species/levels through CHAR1.

## Choosing a future

A chapter may supply `next`, an ordered list of up to eight later chapter IDs. Without it, the next chapter in the array is used, preserving linear stories. An empty list ends that route. All chapters must be reachable from arrival; backward edges and duplicate targets are rejected.

For example, arrival can set `next: ["explorer", "mentor"]`. The explorer chapter can wait for a public `guild_goal_completed` expedition in LittlerootTown; the mentor chapter can wait for a public meetup there. Set both terminal chapters' `next` to an empty list. The first qualifying committed event determines whether the researcher develops a field team or stays to teach. Their dialogue and battle team change together. A later event cannot revive the discarded route. If one event matches both alternatives, the author's declared order decides. Each event advances at most one chapter.

The ordered durable public-history feed supplies evidence. Old events from before author inspection, private outcomes, and native battle-result reports cannot drive these branches. Restart restores the selected route and team. This is a shared-world character: the event can come from any opted-in guild matching the condition, not a private per-player choice. A guild name is a literal label, not stable guild identity.

## Offered expeditions

When a chapter offers an expedition, any outgoing guild-completion chapter must match the exact `character_id`, `character_offer_id` and `character_offer_revision`. An unrelated expedition to the same place cannot advance that story. Accepted offers reuse guild goal progress and rewards; no second objective or reward engine exists. Turning chronicle off preserves private guild play without publishing new story evidence.

## Verification and limits

Tests exercise both real guild outcomes, the authority commit, changed native object dialogue, changed authenticated battle response, restart persistence, and replay immunity. Native UI and bridge components have separate paired fixtures. Full linked-game playthrough and actual model-generated sandbox candidate execution remain separate checks, not claimed by these reducer tests. Character presence and offer destinations currently use supported native catalog maps, not REGION1 generated maps. No save party decoding, automatic player participation, deployment, or campaign trainer modification is involved.

## Agent actions after publication

An author can now return `character_actions` plus normal tests instead of predicting every future chapter. Each action names an existing character, its inspected `expected_version`, nonempty public-history `evidence`, an authored `reason`, `changes`, and its complete replacement `object` (or null when away/retired). Allowed changes are goals, NPC relationships, team, status and offer; null offer removes it. Identity and version cannot be rewritten by the author.

This deliberately takes control of that actor from its older story: subsequent outputs from older scripts for that character are superseded, while unrelated world effects still run. Durable control records hold the most recent character/object projection. Later action wrappers see and preserve that latest projection, not their own old copy. Up to 32 action publications can be stacked before source consolidation is required. This avoids unbounded source/receipt growth and makes the ownership change explicit.

The action compiler requires the exact current source hash, validates the inspected expected version and public evidence, and emits source only. Runtime admission rechecks the version, while existing authority validation checks character transitions, objects and committed public history atomically. A stale action fails rather than silently overwriting newer character development.

The tested example completes an actual public expedition, then authors a new decision: the researcher establishes a Route101 post, changes dialogue and uses a stronger field team. The character disappears from the old map; battle admission there rejects it, while fresh adjacent presence on Route101 receives the revised native team. Restart and older-script ticks preserve the new location. This is relocation between supported native maps, not simulated walking/pathfinding, generated-region support, or proof of a model having independently decided anything. No additional native protocol is required.

## Characters inside immutable generated places

The CHARREG1 draft extends objects with `region_revision`, the exact opened archived revision digest. The authority verifies persistent character identity, pinned immutable geometry, generated map type and a walkable interaction tile outside entrance/exit. Native objects omit this field. Plain mutable shared-cave NPCs remain unsupported.

The server sends `REGION_OBJECT revision id group num x y gfx hextext` only after the client is inside the matching selected region and has acknowledged that exact template. CHARREG1 is negotiated after CHARQUEST1. Legacy clients receive no region-character objects. Generated interaction requests are explicitly scoped: `INTERACT_REGION seq id revision`, `CHARACTER_CHALLENGE_REGION seq id version revision`, and `CHARACTER_ACCEPT_REGION seq id version offer_id offer_revision revision`. Existing direct replies remain nonce-bound. Plain native-map requests do not gain access to generated objects.

Characters in two logical places can share engine map coordinates without leaking across regions. History records the actual logical place, not merely the engine's GeneratedWorld map name. Snapshot rendering, interaction, battle admission and offer acceptance all enforce the same scope. Generated destinations use the separately negotiated PLACEQUEST1 offer contract below.

Current #254 region admission opens format1 (31x31) immutable caves. Object validation also understands format16 geometry, but that format requires the separate region admission support before it can be used. This does not silently enable other cast/event/rotating cave formats. App tests cover authenticated selection/transfer/ACK, place isolation, scoped battle/offer commands, private guild opt-in, invalid geometry rollback, logical-place history and restart. Native fixtures separately test parser/render/admission paths. A full linked gameplay playthrough is still required.


## Active shared XL destinations

An independently supported path now lets persistent NPCs inhabit archived format16 shared destinations without opening a REGION1 outdoor region. Objects remain bound to the exact archive digest. The currently active shared template, acknowledged digest and actual generated-map position must all match. Replacing the shared destination makes the older NPC dormant; its record survives restart and reappears only when that exact archived destination is activated again. Neither region-selection nor the uncertain outdoor-region admission patch is used.

The CHARREG1 capability may accompany CAVE16 without REGION1. Placement coordinates support the full 127x127 map and are checked against actual archived floor geometry, not the engine placeholder layout dimensions. All NPC collision tiles are checked together: actors cannot collectively seal a passage or isolate any remaining walkable map tile. Entry, exit and exit approach stay clear. Mutable terrain/cast formats remain excluded.

Authority tests use actual XL transfer/ACK/state admission, high coordinates, battle requests, replacement, stale scope rejection, restart, and reactivation. Shared-slot admission still refuses replacement while players are inside. This adds NPC presence to the existing route-map publication path; it does not implement generated-region guild goals, automatic route generation or a linked rendered playthrough.

## Player expeditions to generated destinations

A guild leader standing ready inside an admitted immutable cave region or archived shared XL destination can now use `/guild expedition start here COUNT`. This uses the existing expedition progress, distinct-member counting and guild XP rules. The goal persists both the stable logical place and the exact template revision. Fresh authenticated presence must match the acknowledged template and actual generated map. Another area at identical coordinates does not count; a newer revision of the same logical place does not count either. A paused old destination can complete after its exact archived revision is activated again.

The existing leader permission, active-goal protection, cancellation and chronicle privacy remain unchanged. Private completion awards existing guild XP without creating public character evidence. Opted-in completion atomically publishes the logical place and `region_revision`; chapter conditions can match that exact revision. Repeated visits and reconnects do not award the goal twice. Generated meetups remain unsupported.

Bare engine aliases `GeneratedWorld_Cave` and `GeneratedWorld_Wilds` now reject rather than starting goals that cannot complete. Old persisted goals using those aliases show instructions to cancel and restart inside the intended destination. They are not silently cancelled.

The generated-place player command is independent of native offer support. Never encode a generated destination in CHARACTER_OFFER; use the separately negotiated PLACEQUEST1 contract below.

## Visible, authority-paced character walking

A character action may include `walk`, two through six unique cardinal `[x,y]` points including the current position and the replacement object's endpoint. The path must remain within one exact generated revision. The authority validates every point against actual immutable geometry and other NPC placements, including route connectivity. A new walking action increments the character version once. It starts at the old position, then commits at most one point per mechanic tick, yielding when a reported ready player occupies the next tile. Mid-walk state survives restart; replay/nested action wrappers do not double-step.

CHARWALK1 follows CHARREG1 in capability negotiation. After CHARACTER, `CHARACTER_WALK id version movement_id index count x0 y0 ...` supplies the full bounded route and current authoritative index. The ordinary scoped object's position equals that indexed point. The complete path remains after completion so a client missing snapshots can catch up. Older clients hide the moving actor and can see it again when finished.

Authority interaction, battle admission and expedition acceptance reject while the logical route is unfinished. The native counterpart also gates interaction until its visible actor actually reaches the endpoint, and uses ordinary held walking actions with read-only local collision checks. A player or moving object can delay native animation even after the authority reaches the logical endpoint; no reward, arrival proof or forged battle result comes from that local playback. Off-path retargeting safely waits rather than teleporting.

This is short, explicit same-map walking, not automatic navigation, a cross-map journey or guaranteed synchronization with unreported local obstacles. Existing teleport-style authored relocation remains a separate action. Source/component fixtures exercise the real authority path and native playback routines, but a rendered playthrough is still a separate acceptance step.

## Reacting to voluntarily shared discoveries

With the landmark survey integration, a chapter may wait for `landmark_discovery_shared`. It must name the exact `place_id`, immutable `revision`, and registered `landmark` identifier. The character history feed includes only the already committed public event and its bounded destination/coordinate/publication fields. It never queries private survey sessions or visit trails.

Private arrivals, survey completion, and the first share-confirmation prompt do not trigger characters. Only the player's explicit confirmed publication can do so. The tested example moves a scholar from camp to the publicly reported lookout, changes dialogue and battle team, and records that public sequence as evidence. Duplicate shares do not advance twice, another revision with the same landmark name does not match, and restart preserves the change.

This uses an authored chapter and the existing authority commit, scoped NPC and battle-admission paths. It does not invoke a model on each arrival, reveal who shared the discovery, or prove travel/battle outcomes beyond the existing acknowledged client-presence rules. The two-source integration fixture requires the survey branch in addition to this compiler/feed support; it does not activate anything in a live world.


## NPC-offered generated-place expeditions

An offer may name `place_id: area:UUID` with a required `region_revision` digest. The authority resolves the archived label and validates the exact destination. Native destinations must omit that extra field. Changes of destination/revision require a new offer revision under the existing immutable-offer rule.

PLACEQUEST1 is appended last in capability negotiation. Capable clients receive `CHARACTER_PLACE_OFFER id character_version offer_id offer_revision count place_id region_revision hexlabel`. It is a separate nine-token row, never an overloaded native-map name. The native UI displays the label, destination/revision identifiers and explicit public guild participation count. Acceptance uses the existing nonce-correlated CHARACTER_ACCEPT (or CHARACTER_ACCEPT_REGION when talking inside a generated place). Full destination identity, revision, label and count are frozen and checked during native consent.

The player need not have visited the destination to accept. The NPC must still be adjacent and available, the player must lead the guild, and public guild chronicle must already be ON. No privacy toggle, warp, map activation or reward occurs on acceptance. The destination must currently be accessible to that client: an active shared XL revision with CAVE16, or an opened immutable region with REGION1. Unsupported clients and unavailable destinations receive no generated offer row and cannot start it through direct acceptance.

Actual goal progress uses the existing exact-place/revision, fresh acknowledged presence rules. Replacement pauses that goal until its exact revision returns. Completion and XP are committed through existing guild rules before public character history. Turning chronicle OFF after acceptance preserves private completion without advancing the public character story. Goal, offer receipt and destination binding share one transaction; a failed binding leaves no partial accepted goal.

Tests cover real acceptance, two authenticated destination arrivals, authoritative completion/XP, character team change, private completion, incompatible clients, inactive destinations and transaction rollback. The paired native component tests exercise actual offer parsing and explicit consent. This is not a linked rendered playthrough or deployment claim.

## Relationships with playable consequences

Existing authored actions can change a character's relationships with other registered fictional NPCs. A chapter can now respond to a committed `character_changed` event using `character_id`, `relationship_target`, and the exact `relationship` label. The bounded public history feed supplies only relationship deltas. Retaining an alliance while later changing a team is not another alliance event. Other NPC targets and self-relations cannot accidentally match the condition.

This lets one recurring character's history-grounded decision affect another character that players encounter. The tested example completes an actual public expedition, authors the researcher's alliance with a trail mentor using that goal as evidence, and waits until the relationship change is committed. The mentor then changes visible dialogue/team and offers a new Route101 expedition through the existing native consent UI. Two authenticated guild members complete it through existing goal accounting and rewards; restart preserves the resulting characters.

Relationships here are authored fictional-world facts, not personality scores for human players or inferred private friendships. No model is called automatically and no relationship is asserted before its authority transaction commits. This extends the existing character action/chapter framework without another social ledger or native protocol.
