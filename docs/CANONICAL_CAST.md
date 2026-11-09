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
full build, gameplay QA and release. Wally, Briney and Steven are not bound yet:
each needs its own reviewed original-script safe points and progression guards.
No namesake actors are spawned as a substitute.

Tests use real guild authority, two actual public completions, persisted actor
revisions and authenticated CAST dispatch; the exact authority packet enters the
compiled production native adapter. Native component tests cover original script
continuation, legacy refusal, nonce/world checks, timeouts, save-lineage storage
and untouched bike script bytes. A full linked/rendered RC12 build has not been
performed in this environment. Reaction author outputs in tests are deterministic
fixtures, not evidence of a live model run. The existing 32-action consolidation
limit applies. No merge or deployment is included.
