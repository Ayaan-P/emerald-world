# Original cast, public activity, evolving intent

The first reviewed canonical binding is Rydel's original BikeShop script.
Unlike world overlay characters, `canonical_cast.canon_rydel` creates no object
and has no team, item, flag, travel or battle effect. Its bounded supplemental
line runs after the original lock/faceplayer, then original bike choices and
exchanges continue unchanged. Offline, missing authored state, older authority,
refusal or timeout continues the ordinary script.

An agent may return `canonical_actions` and tests through the existing GM. Each
single action identifies `canon_rydel`, an expected version (0 for first authoring)
and changes containing goal, literal ASCII dialogue (200 characters maximum),
1..4 known native places of interest, exact public activity evidence and reason.
There is no predetermined arc. Normal author tests, sandbox and atomic admission
still apply. Evidence must be committed opted-in `guild_goal_completed` history
in those interests, not a private save observation or invented personal victory.
Neither the initial record nor later decisions duplicate the original NPC.

After the initial explicit authoring, the host can use the existing
`runtime_gm follow-character --id canon_rydel` workflow with a purpose. Its
configured runtime then reacts to new real public activities in those interests.
The author can choose a new goal/response or wait; only this actor's typed action
is accepted. Player purposes and party observations are removed from this
public reaction context. Decisions are durable and appear in the existing
world journal as authored interpretations linked to their actual evidence.
They do not claim that Rydel personally completed someone else's expedition.

The native adapter sends `CORE run CAST rydel safe nonce` only at that original
script safe point. The authority checks authenticated CORE1 negotiation and
fresh BikeShop location, then supplies the current immutable response digest.
Existing run/world/nonce validation rejects stale or mismatched replies. CAST
needs no Devon completion or bike entitlement; original scripts alone decide
what the player may receive. No private progress is inferred from public results.

## Pairing and limits

Requires the paired native canonical-cast patch atop native PR25 at 9d4635b0.
Current app gitlink 488796 does not contain that hook. This app branch intentionally
does not change the pin or claim deployed/rendered behavior. Maya owns pairing,
full build, gameplay QA and release. Wally in Wanda's house and Briney in his Route104 house now share the reviewed
lock/faceplayer adapter. Their ordinary speech and sailing scripts are unchanged.
Automatic cutscenes, Wally battles/rematches and Steven are not intercepted.
No namesake actors are spawned as a substitute.

Tests use real guild authority, two actual public completions, persisted actor
revisions and authenticated CAST dispatch; the exact authority packet enters the
compiled production native adapter. Native component tests cover original script
continuation, legacy refusal, nonce/world checks, timeouts, save-lineage storage
and untouched bike script bytes. A full linked/rendered RC12 build has not been
performed in this environment. Reaction author outputs in tests are deterministic
fixtures, not evidence of a live model run. The existing 32-action consolidation
limit applies. No merge or deployment is included.

## Optional field proposals and multiple original actors

`canon_rydel`, `canon_wally` and `canon_briney` use the same bounded action
contract. An action may include `offer: {map: "LittlerootTown", count: 2}`
(or null to stop offering). The destination must be a native place in that
actor's interests. This is a proposal to players, not proof of an NPC journey.

The original actor's supplemental response points to guild chat. At the actor's
native location, `/guild cast wally` privately previews the exact destination,
trainer count and public nature. `/guild cast wally VERSION` explicitly accepts
the previewed version. Existing guild rules enforce leader permission, existing
chronicle consent, membership count and no conflicting expedition. No automatic
warp, publication opt-in or new NPC is created. The native guild-command guard
keeps this command out of public fallback chat on older servers.

Authenticated ready visits complete the existing expedition. Its frozen receipt
records the original actor and proposal version; repeated acceptance cannot
award another reward. While an actor has an offer, only that exact offer's public
completion queues its next author turn. Wally cannot claim Briney's result.
The author then chooses new terms, withdraws the proposal, or waits, based on
the inspected outcome. An older accepted expedition keeps its original terms
even if the actor changes; a stale accept is refused. This does not infer that
Wally fought, Briney sailed, or anyone trained off-screen.

Current checks: 91 app/author tests plus three compiled native component tests.
The new test uses two original actors, explicit private preview/public consent,
real authority visits/rewards, typed next action, actor isolation and replay
protection. No live model, full linked native build or rendered QA claim.
