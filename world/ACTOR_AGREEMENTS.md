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


## Persistent NPC organizations

Organizations add durable shared identity and voluntary membership above the one-off agreement executor. They do not replace player guilds, social relationships or project ownership. Agents can found a named group with a public fictional purpose, invite another active character, independently join/decline, or leave. No faction, prescribed story or player affiliation is created automatically. Any current member may invite; accepting a current invitation changes the roster. A roster change invalidates all pending organization agreements and invitations. Leaving and rejoining never restores prior consent. Empty groups remain as dormant historical identities.

The capabilities are `world.found_organization(id,name,goal)`, `world.invite_organization(organization,target)`, `world.decide_organization(organization,decision)` and `world.propose_organization_project(organization,purpose,tool,args,hours,campaign)`. Discovery includes current rosters, invitations and the eight most recent joint projects. There are at most 32 retained organizations, four NPC members per group and eight pending invitations per group. Players are not members of this initial slice.

A joint project uses one of the existing three agreement-safe operations. Every current member must independently accept through `world.decide_agreement`; only the original proposer can execute through `world.commit_agreement`. The exact group identity, roster revision, operation and optional campaign offer are frozen in the reviewed agreement terms. The ordinary location, ownership and engine configuration guards still apply. Direct agreement execution also checks the group revision, so it cannot bypass a departed member. Direct independent NPC actions remain independent and never count as group-approved work.

The proposer can include an existing campaign they published, or an empty campaign string. After an actual successful joint operation, this becomes a discoverable optional adventure offer endorsed by that exact roster. Later membership changes remove the current offer but retain the historic action. This does not claim that an outbreak was encountered, weather rendered, the campaign completed, or a fictional goal achieved.

Players use `/guild org list PAGE` (pages 1–4), then `/guild org ID` to read the purpose, current members and three most recent project results. A current committed project with a campaign displays `/guild org ID play CAMPAIGN`. Choosing it starts only that player's ordinary private campaign lobby. Other players join independently through the existing campaign flow. No player identity, membership or results are published to the organization by browsing or hosting. Normal campaign witness/result sharing remains explicit.

This app-only slice follows #454 at `d7d35b65ec9bf6e90739c22a9a01512e7d2a0102`, retaining native #100. No held native operation or live provider is used. Tests execute independent authority plans, actual outbreak configuration and native snapshot output, per-member decisions, leave/rejoin cancellation, database restart, original ownership rejection, in-game discovery and optional campaign hosting. This is not a rendered multiplayer playtest or proof of autonomous model behavior.
