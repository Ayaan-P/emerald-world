# Experimental tagged co-op against dynamic NPC trainers

This candidate lets two already-tagged players use the existing co-op encounter
invitation to fight an agent-created trainer. The initiating player still chooses
the optional NPC challenge. Existing tag range, readiness, consent, private-party
staging, reward reconciliation and rollback remain responsible for co-op admission.
There is no new forced encounter, authored story or AI-generated victory.

## Entry and scope

Build both clients from the matching native candidate with
`python scripts/build_expansion.py --development --experimental-npc-coop`.
The switch defaults off and requires explicit development mode. Both clients must
use the same experimental wire; an old wire is rejected before mixed-party staging.
Enroll/tag two players using the existing co-op controls, stand near an existing
registered dynamic NPC with a valid team, and let one player choose Battle.
Without an available tagged partner, the existing solo fallback remains available.
A canceled asynchronous exchange reports cancellation, never a battle victory.

The guest receives the exact prepared individual Pokémon through existing checked
full-mon exchange blocks. A small versioned header binds the NPC identity/version,
gender and team count. The guest creates temporary trainer metadata so trainer-0
lookups are valid during the battle; it never reports the owner's pending challenge.
Only the initiating player's existing challenge receipt is completed. This does not
add guest campaign progress, NPC training, canonical trainer flags, badges or an
extra reward system. Player parties use the existing co-op ownership machinery.

## Verification and integration

Component tests compile actual native metadata, capture and header-validation
functions in both default and experimental configurations. They exercise malformed
headers, guest adoption, owner-only completion and canceled exchange results. Static
seam checks cover admission before mixed-party staging and cleanup callbacks.
These are not a linked native battle or rendered two-client playtest.

Maya must verify full compilation, two-client invitations and solo fallback, party
identity/HP/PP/XP/item ownership, defeat/whiteout, disconnect at each exchange phase,
return callbacks, saving/reloading, and default-cohort behavior before enabling it.
The candidate is based on app #350 / native #46, not released RC12. The released
pair f484577b606348d07337387f14f75ab8cf4970b6 /
f7a813317d1b9fec803b48b682f5d74245c79037 has diverged and its fixes must be preserved
by integration. No release branch or user save is modified here.
