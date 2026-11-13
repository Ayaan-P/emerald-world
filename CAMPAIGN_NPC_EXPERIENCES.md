# Consented campaign experiences for recurring world NPCs

This feature joins existing systems rather than introducing another battle-result
protocol. A player can use #298's existing `/history battle on` preview/confirm
flow once for the current trainer/save/world. Eligible future ordinary single
trainer results then use the existing safe-idle callback. Manual one-result
sharing and OFF remain available. No private result is backfilled or published by
an NPC, host enrollment, or changing an NPC's interests.

Generated recurring characters can retain `campaign_interests`, a list of up to
four existing `native:MapName` locations. It is optional and empty by default.
The configured author may revise it through the ordinary versioned
`character_actions` interface. It is a public-report interest, not physical
presence, knowledge of a player, a prewritten personality, or a predetermined arc.

When an enrolled actor's interest matches an actual committed consented report,
the existing durable reaction queue starts an ordinary author turn. The author
gets the exact anonymous report plus explicit client-attestation limits. It may
revise its intentions, choose any supported capability plan, or wait. Plan
execution and its receipts remain separate from the report. No report awards
NPC XP, changes a party, completes a project, or proves a victory. Existing full
companion-state/ownership gates remain unchanged.

One component journey demonstrates normal report -> real author queue -> validated
fixture action -> real outbreak authority -> WILD_OUTBREAK player snapshot, with
the NPC team unchanged. That response is test content only; no production rule
maps defeat to an outbreak. Another actor or model can choose an entirely different
supported response. No live model response or rendered gameplay is claimed.

## Exact ancestry and conflict resolution

The app is a two-parent feature candidate containing:
- #359 `62892efa3cfde5a59a07b3cf37d63aeecc828599`
- #298 `6fd210f118fa7ed6ac368d761414ab133134f3a2`

The paired engine #51 `5408512d66c2c6903f9d28316e88e6db3ed90447` contains:
- #50 `75719749b0009a585a5803255af3cdf597e0f058`
- #31 `27672498fcec76574776299af8b9bfb27d0cc768`

App conflicts: kept the cumulative CI branch coverage, combined both test suites,
and set gitlink/builder/manifest to the combined engine. Other app source merged
without textual conflicts. Habitat metadata input files are unchanged by the
seven-file native delta; its exact-source provenance carries to the new pin.

Native conflicts: retained both campaign reset and battle-sharing lineage reset;
retained both CAMP and BMODE reply handling and the trainer callback declaration.
The campaign page formatter now has room for a full unsigned value. Test fixtures
include the existing CampaignClose prototype. Neither parent branch is edited.

This is NOT the released RC12 baseline. The released app remains
`f484577b606348d07337387f14f75ab8cf4970b6`, engine
`f7a813317d1b9fec803b48b682f5d74245c79037`. Maya must preserve those release fixes
when integrating. No merge, deployment or release is performed here.

## Verification boundaries

Tests exercise actual anonymous report admission, per-save standing consent,
withdrawal, native callback exclusions, native packet dispatch, queue preparation,
validated character action, plan execution, and player snapshot. Engine tests
compile production collectors/controllers with explicit engine doubles; existing
lineage-store tests use temporary private fixture files, not player saves.
Full linked build, safe-field behavior, rendered multiplayer effects and model
quality remain Maya's QA. Isolated companion training/move features retain their
separate exact-binary QA gate. The unresolved outdoor-region operation is untouched.
