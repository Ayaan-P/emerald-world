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
