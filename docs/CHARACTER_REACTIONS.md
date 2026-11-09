# Result-driven character activity loop

This opt-in host feature closes the gap between an existing character offering
an expedition and choosing what to do after its actual public result. It adds
no predetermined chapters, canonical script replacements, native save writes,
new battle rules or automatic model startup.

## Use

Start with an already registered `world_characters` actor whose current offer
uses the existing explicit native guild-expedition consent path. The first goal
and offer are authored through the existing GM; this feature does not spawn an
actor or choose an initial story. Enroll it from the host:

    python3 -m world.runtime_gm follow-character --state-dir STATE --socket SOCKET \
      --id EXISTING_CHARACTER_ID --purpose 'Respond to field results and choose the next useful activity.'

Then run the existing explicitly configured RuntimeGM using its supported model
and normal author interval. Enrollment alone starts no model. `status` includes
followed actors and durable cursors. `unfollow-character --state-dir STATE --id ID`
stops future reactions and cancels queued actor requests; an already running
author turn can finish. `--no-events` consumes new history without scheduling it,
so re-enabling does not replay disabled-period outcomes.

## Observable behavior

1. A player chooses to accept the character's current offer. Existing leader,
   chronicle opt-in, ownership and native consent checks remain unchanged.
2. Existing authority records a completed goal from authenticated presence and
   awards the existing reward once. Only an opted-in public completion with the
   exact character, offer ID and offer revision schedules a reaction.
3. The configured author sees that exact committed evidence, current character,
   goals and its host-selected purpose. It chooses one typed character action or
   explicitly waits. A next action can change dialogue, supported location,
   team intent or a new offer through existing affordances. It cannot replace
   the whole source, target another actor, invent a victory or write save flags.
4. Normal source compiler, candidate tests, sandbox and atomic authority checks
   still gate changes. A later actual outcome can schedule another decision.
   A wait records the decision without redeploying an old initialization source.

History is paged at an inspected world boundary, including busy-world backlogs.
Only one queued/running reaction per actor exists. Its pending page is retained,
not coalesced into a lossy tail. Enrollment begins at the current boundary.
World swaps, stale versions and changed offer evidence refuse safely. Own
character/mechanic edits, private battle reports and unrelated events cannot
self-trigger an authoring loop. Interrupted turns are never automatically retried.
Existing character-action source/receipt limits remain in force; consolidation
is still required after 32 action publications.

## Canonical cast boundary

Wally, Briney, Steven and Rydel are not automatically enrolled, copied or spawned.
An original cartridge NPC is not the same thing as an authored world actor with
its name. The paired canonical-cast candidate now binds original Rydel supplemental
dialogue through a separate `canonical_cast` record, without an overlay object.
See CANONICAL_CAST.md for the required native pairing and narrower effects.
The current app native pin does not yet include that hook. Wally, Briney and
Steven still require reviewed original-script bindings; they are not replaced
by namesakes. A registered overlay actor continues to use its existing explicit
offer-completion path; a canonical actor observes opted-in public activities
in its declared native places of interest.

## Validation

A deterministic test author (not a live model) drives the production authority:
first offered expedition completes through authenticated visits, one typed
choice changes visible dialogue/team and offers another activity, its actual
completion schedules the next choice, and restart preserves no-replay behavior.
The two goals award 10 existing guild XP each, not simulated rewards. Tests also
cover privacy, exact offer/version evidence, unrelated events, backlog pagination,
world mismatch, queued cancellation, and the GM's explicit no-change response.
This is app authority and author-pipeline validation, not a native rendered run.
Live AF_UNIX admin/sandbox integration tests require a socket-capable environment.
Maya retains integration, gameplay QA and release ownership; this branch is not a
release or deployment and changes no native pin.
