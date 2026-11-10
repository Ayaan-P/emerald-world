# Voluntary shared-world agreements

Recurring world and canonical characters can propose a concrete shared-world action, independently accept or decline it, and commit the exact agreed operation. This is a general collaboration mechanism, not a named character scenario, mandatory governance rule, physical meeting or new permission. Existing direct capabilities remain available. Player conversations and campaign decisions keep their existing agency; players are not asked to approve routine fictional NPC decisions.

The runtime advertises three capabilities:

- `world.propose_agreement`: a JSON list of one to three other active actors, bounded public purpose, one supported tool with exact literal argument JSON, and expiry in 1–24 hours. The proposer implicitly accepts its own proposal. The immutable terms are visible in `actor_runtime.agreements` and public history.
- `world.decide_agreement`: invited actors independently accept or decline. The proposer can withdraw. Declining or withdrawal closes the proposal, including after an earlier acceptance but before execution. Duplicate acceptance produces no further decision event.
- `world.commit_agreement`: only the proposer can commit, after all participants accepted and before expiry. The original synchronous authority executor runs in the same transaction as the agreement result. A later duplicate commit returns the stored result without repeating the effect.

Initial supported operations are the existing native-backed shared outbreak, fishing population and outdoor weather configuration tools. The proposer retains its original actor kind, location, ownership, species and geometry constraints. Another actor's acceptance grants no extra authority. An active outbreak owned by a third actor still blocks the proposal's execution. Unsupported, asynchronous, arbitrary-code, provider, player-save and nested-agreement operations are excluded.

A real committed operation produces its normal player-visible native configuration plus an agreement receipt containing the actual executor result. It does not establish that the prose purpose was fulfilled, a Pokémon was seen/caught, an NPC performed physical labor, or a client rendered the result. Proposal and decision events can trigger already enrolled character authors through the existing bounded lifecycle; they do not start a model or guarantee a response. Both participants retain independent goals and can wait or decline.

Open proposals are bounded at 32 at a time, not a lifetime limit. Expired proposals stop appearing as actionable; immutable historical rows remain. Acceptance and applied results survive database restart. The executor still treats a failed world action as a blocked plan rather than retrying blindly.

## Verification and ancestry

Tests use real authority character plans to propose, accept, commit and avoid duplicate effects. The resulting outbreak wire runs through the existing native outbreak component where its exact source fixture is available. Tests also cover rejection, third-party ownership, no partial effects, expiry, independent reaction routing and persisted decisions. These are component checks, not live-model behavior, rendered gameplay or multiplayer playtesting.

This branch is based on #378 `6d56d82fabef756643acb89ffbf1ccff133797b3`, retaining native #55 `babbe0e3272120523d509cecf22705f158429586`. It is not based on released RC12 and does not replace Maya's integration. All three denied uploads and the uncertain outdoor-region publication remain untouched. Spectating remains disabled under the inherited mitigation, and live direct-provider sessions remain prohibited pending their separate budget correction.
