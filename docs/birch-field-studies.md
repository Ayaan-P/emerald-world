# Birch's retained field studies

This is an optional original-Hoenn exploration → return → useful Pokémon move loop, not a new region, automatic quest arc or public catch counter. An agent may independently author a Birch study based on inspected public world history. No study, encounter change or model call is installed by default.

## Play

Talk to Professor Birch in his original Littleroot lab after receiving the Pokédex. His original rating or declined-rating dialogue runs first. During the optional supplemental greeting, L opens the field study. SELECT browses the terms, each required species and the available actions; B returns to the original conversation.

An offered study asks for caught knowledge of one to three species from a verified 42-species stock-Hoenn land-encounter catalog. It offers one of the existing reviewed native tutor moves. Existing caught records, including previously traded Pokémon, count. No new catch, particular location, Pokémon surrender, group vote or forced battle is required. The displayed species and caught status come from the player's own native Pokédex. Caught flags are only read, never set by this feature. A friend's catch is not copied. Players choose their own routes, native battles/capture risks and whether to pursue the opportunity at all.

Acceptance saves a private invitation on this world's server for the displayed 1–7 days. The world host can inspect the invitation, but this system does not send the player's caught flags, party, names or capture outcomes. Accepted requirements and offered move remain fixed even if the agent later changes or removes its proposal. The player can return after restarting; changing saves does not inherit another save's invitation. Leaving the study or expiry never removes Pokémon or Pokédex knowledge. There is no fabricated completion, public participation record, leaderboard or currency reward.

Return to Birch when the local caught records qualify. A separately requests the free tutor service. After the original conversation releases its lock, the native client rechecks context and caught knowledge, then opens the existing party and learn/replace-move flow. The player chooses an eligible owned Pokémon and may cancel. No automatic save, party editing on the server or guaranteed teaching result. This is repeatable free tutoring until invitation expiry, an intentional optional balance change, not a one-time consumable prize or original tutor flag. A legitimately admitted native tutoring attempt may finish after expiry/offline just like the existing tutor service.

## Authoring

Use Birch's existing typed canonical `tutor` field:

- `move`: an existing reviewed tutor move ID.
- `appearances`: exactly `["birch"]`.
- `research`: `{ "species": [one to three names from field_study_species], "days": 1..7 }`.

The original canonical compiler's inspected-history requirements still apply. `field_study_species` exposes actual baseline route habitats from native `src/data/wild_encounters.json`, blob `ac4c8a1f56063f1d4f284fe43e3b3297a0eee767`, checked at native #129 `15618acb311c7cd5ee1c60bf84596eaafefd5dca`. These are baseline tables, not sightings or a promise that a particular player can already reach a route. Private progression, Repel, native conditions, optional species shuffle and other encounter rules remain in effect. Arbitrary enabled-but-unobtainable Expansion species are not valid study requirements. The verified habitat reference is in Python source so packaged runtimes need no new external JSON catalog.

No authored narrative says that catching happened or that the tutor move was learned. Agents receive no automatic private completion notification. Existing separately consented public research sharing remains a different feature.

## Boundaries

- Default `EW_BIRCH_STUDIES=0`. Build with `--development --experimental-birch-studies`, which also enables the existing original Birch hook. No other experiment, including mandatory turn planning, is enabled by this option.
- Matching app/native pair required. Older clients cannot bypass the local check through `/history tutor`; the ordinary tutor handler refuses research-conditioned offers.
- Authority verifies current authenticated connection, save context, fresh actual lab position and original conversation. New acceptance is version-bound; accepted terms are retained independently. Each action consumes a five-minute connection-local preview token. Duplicate/late tokens cannot repeat acceptance or cancellation. There is at most one active study per trainer/save lineage, with 32 active lineages per trainer as a defensive bound.
- Pending UI/teaching handoffs are RAM-only and tied to save, world, map and tile. Cancellation, movement, context loss, disconnect and expiry discard them. No automatic request retries. If a network reply is lost after acceptance/leave, reopening reads the actual stored invitation; closing a pending menu does not claim that an already committed server action was undone.
- Native reply validation checks reviewed move, species bounds, distinct national Pokédex identities, exact nonce/context and unchanged tutoring terms. It rechecks caught flags both before the request and before the local party menu. Server admission is a frozen service offer, not server verification of caught/learned/completed gameplay.
- No changes to original encounter tables, Birch starter/gifts/story flags, native tutor compatibility, normal two-player choices or Maya's integration/deployment. No real saves or live providers were used.

## Validation and remaining QA

Eight focused tests pass: actual CORE handler authentication; real study authority persistence/restart, immutable versioned terms and unknown-schema refusal, withdrawal before acceptance, expiry, token replay, leave and per-save/player isolation; original tutor bypass refusal; source-derived habitat bounds; actual native included implementation compiled on/off with UBSan, missing/caught knowledge, malformed/aliased species, wrong move/requirements, cancellation, context changes and deferred tutor handoff; production wiring assertions. Full C source syntax passes against recovered headers using the same test-only shim for three inherited missing declarations. Python syntax checks pass.

These are synthetic/component checks, not a rendered playtest or full linked native build. Exact-binary text paging and button timing, original Birch script assembly/release, actual encrypted Pokémon tutor compatibility and move replacement, save/reload, native caught records and two independent clients still require Maya's QA. No complete playthrough or earned reward is claimed.
