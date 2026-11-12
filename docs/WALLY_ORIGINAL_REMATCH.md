# Agent-offered original Wally rematch

Independent paired follow-on to the living-cast candidate. This reuses Wally's
existing postgame rematch machinery instead of creating another battle system
or importing a flattened dynamic team. Original map scripts and trainer parties
are not edited. Maya owns full build, rendered multiplayer/story QA and release.

## Connected player experience

An author may set `rematch: wally_native` on canon_wally after considering real
public events or existing relationships. It may withdraw that future invitation
on a later decision. No fixed rivalry arc or default invitation is installed.

Talk to original Victory Road Wally after the Hall of Fame and his first exit
battle. The existing supplemental response identifies the optional rematch.
`/history rematch wally` previews the local effect; `confirm` requests the current
authored invitation. `/history rematch` reports whether native readiness was
applied. The next normal conversation executes the unchanged original script,
which chooses Wally's proper rematch team from that trainer's own fought flags.
Nothing automatically starts a fight or moves either player or Wally.

The only native write is existing rematch readiness, using
UpdateRematchIfDefeated / SetRematchIdForTrainer. Already-ready rematches are
unchanged. In FREE_MATCH_CALL builds no readiness write is necessary. The
original ladder, money, EXP, items, defeat/whiteout and rematch cleanup stay in
ordinary engine code. This is native scripted progression, not agent-earned
training, persistent Pokémon simulation, or proof of a new victory.

## Boundaries

Authority requires current authenticated save lineage, exact Wally authored
version and recent original Victory Road conversation. Native independently
requires postgame, original Victory Road completion, first exit-team victory,
correct current map and idle field state. Script, battle, link/co-op battle or
activity ownership refuses the operation. Remote phone calls and early Wanda's
House conversations do not grant it. Preview/reply nonce, reconnect, new game
and lineage reset fences remain intact; late replies after cancel are ignored.

Readiness belongs only to the accepting player's save and persists through the
normal save process. No server copies flags between players, grants money,
records victory or publishes personal progression. Cancel stops pending work;
it does not undo an already applied ordinary readiness flag. Withdrawing the
authored offer does not retroactively revoke existing vanilla rematches.

## Verification

Actual C readiness helper and the existing native ladder selection functions
are compiled against explicit engine doubles. Tests show unearned teams cannot
be selected, the next index follows actual fought flags, and unrelated readiness
and flags remain untouched. The production native command requires preview and
exact reply, rechecks current eligibility, and rejects late/cancelled/disconnected
responses. Its emitted CORE packet is dispatched through the real app authority.
Original Wally script/preset preservation checks also remain in the suite.

Component checks do not prove a full linked game or rendered battle. Maya must
verify pre/post-Hall-of-Fame states, original first exit fight, subsequent teams,
normal victory/loss cleanup, save/reload and independent co-op trainers. No live
model was used; author responses in fixtures are deterministic validation input.
