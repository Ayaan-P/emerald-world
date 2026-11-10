# Party egg-move practice (experimental)

Build with `--development --experimental-party-practice`. Default is off.

In ordinary Hoenn outdoor fields, open the existing chat input:

1. `/practice preview 1 2`: party slot 1 learns from slot 2. This changes nothing.
2. `/practice show 1` (and subsequent numbers): inspect the actual new move names and destination slots.
3. `/practice apply TOKEN yes`: explicitly apply the complete displayed preview, using its token.
4. `/practice cancel`: discard a preview.

The native engine's existing daycare transfer function determines eligibility and moves. Under Gen 9 configuration the receiver needs a held Mirror Herb; under Gen 8 both must share the same base species. Eggs and bad eggs are rejected, existing moves are not replaced, and empty slots are required. The donor remains unchanged. The herb is not consumed, matching the native transfer rule. No egg is created, no XP or friendship gained, and no breeding outcome inferred.

Everything is local. Party data and commands never go to the server or models. A preview expires after 3,600 native frames, or if the party or trainer ID changes. Battles, scripts, active native link sessions and non-Hoenn-outdoor locations cannot apply it. A successful action is one native in-memory party-member assignment; save normally to persist it. No custom save marker, autosave, recovery journal, item minting or remote party mutation is introduced. Restart before normal saving follows ordinary unsaved-game behavior, not a transaction guarantee.

This standalone convenience is player-directed, not an autonomous NPC capability. Existing NPC move learning remains separate and untouched. Native two-test suite compiles the actual transfer function and command code with fixture engine state, checks both flag values, species/item/egg constraints, real preview/apply/cancel/staleness behavior, and verifies the chat hook. Fixtures do not replace a full linked build or rendered party/save QA, which remain pending.

Ancestry: separate app draft after #407 and native #69, not RC12. Maya's frozen #384/#56 and denied/uncertain operations remain untouched.
