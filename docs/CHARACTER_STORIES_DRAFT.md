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

Characters in two logical places can share engine map coordinates without leaking across regions. History records the actual logical place, not merely the engine's GeneratedWorld map name. Snapshot rendering, interaction, battle admission and offer acceptance all enforce the same scope. Offered expedition destinations still use native map names; generated-region visit goals are not implemented here.

Current #254 region admission opens format1 (31x31) immutable caves. Object validation also understands format16 geometry, but that format requires the separate region admission support before it can be used. This does not silently enable other cast/event/rotating cave formats. App tests cover authenticated selection/transfer/ACK, place isolation, scoped battle/offer commands, private guild opt-in, invalid geometry rollback, logical-place history and restart. Native fixtures separately test parser/render/admission paths. A full linked gameplay playthrough is still required.


## Active shared XL destinations

An independently supported path now lets persistent NPCs inhabit archived format16 shared destinations without opening a REGION1 outdoor region. Objects remain bound to the exact archive digest. The currently active shared template, acknowledged digest and actual generated-map position must all match. Replacing the shared destination makes the older NPC dormant; its record survives restart and reappears only when that exact archived destination is activated again. Neither region-selection nor the uncertain outdoor-region admission patch is used.

The CHARREG1 capability may accompany CAVE16 without REGION1. Placement coordinates support the full 127x127 map and are checked against actual archived floor geometry, not the engine placeholder layout dimensions. All NPC collision tiles are checked together: actors cannot collectively seal a passage or isolate any remaining walkable map tile. Entry, exit and exit approach stay clear. Mutable terrain/cast formats remain excluded.

Authority tests use actual XL transfer/ACK/state admission, high coordinates, battle requests, replacement, stale scope rejection, restart, and reactivation. Shared-slot admission still refuses replacement while players are inside. This adds NPC presence to the existing route-map publication path; it does not implement generated-region guild goals, automatic route generation or a linked rendered playthrough.
