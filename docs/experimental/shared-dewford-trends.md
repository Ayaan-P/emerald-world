# Optional shared Dewford fishing traditions

Default OFF (`EW_SHARED_DEWFORD_TRENDS=0`). The development build option is `--experimental-dewford-trends`. This independent #494/#132 draft is not integrated, release-ready, or a linked playtest.

## Actual loop

1. Connect and use `/trend share on`. This publishes only **future** phrases that the original Dewford phrase boy actually accepts. It does not upload saved trends retrospectively.
2. Talk to the real stationary boy outside Dewford Hall, reject the current phrase and choose two Easy Chat words in the stock UI. The original trendiness decision, cancellation, private save update and TV behavior remain intact. Rejected or cancelled phrases do not publish.
3. After the conversation releases, one bounded report can commit the actual accepted words and their actual native seed to persistent anonymous world history. `/trend status` distinguishes acknowledgment from an unconfirmed request. Reporting can fail after the personal change. No automatic retry or invented acceptance.
4. Another player in Dewford or Route 119 can independently choose `/trend follow`. This adopts the latest acknowledged **immutable revision** for their connection. `/trend status` displays the phrase and revision. It is not an invitation requiring everyone to vote.
5. On Route 119, fishing uses the original Feebas algorithm with that revision's seed. Players following the same revision can investigate the same six generated fishing spots. Original accessible-tile filtering, possible duplicate spots, 50% Feebas check, rod/catch/party rules and ordinary fishing fallback remain. No coordinate spoiler or guaranteed catch is added.
6. A subsequent accepted phrase may create a different public pattern, but never silently moves somebody's current fishing search. They choose `/trend follow` again to adopt it. `/trend off` or disconnect restores private fishing without changing their save. `/trend share off` stops future reporting but retains any followed pattern.

The first ever native accepted phrase **does not reseed** the player's trend. This draft preserves that. A new phrase can also map to the same fishing spots, and duplicates can yield fewer than six unique spots. No claim that every action changes terrain or creates a new Pokémon population.

## Persistence and original-game boundaries

The authority keeps one latest public trend in SQLite and retains its committed history receipts. It survives authority restart. A followed revision remains fixed during the connection and can be older than the latest public trend. A reconnect does not silently re-adopt it.

Only the Feebas seed call is overlaid, only on ordinary Hoenn Route 119. Original saved Dewford trends, town NPC dialogue/judgment, daily trend aging, record mixing, painting, Slot Machines and Match Call remain personal. This is a public **fishing tradition**, not synchronized town simulation, a shared save, a scarce fish stock, a catch ledger or an ecology migration claim. Stock NPC dialogue is not presented as the public phrase; the public phrase appears in the explicit command's feedback.

No item cost, PP tax, extra grind, forced votes or timed scarcity is introduced. Opt-in sends Easy Chat word IDs and seed anonymously. It does not send player identity, private party, catches or partner identities. Existing world operators/agents can read that public information. Previously shared history is not erased by stopping future sharing.

Native success is a consenting client report, not cryptographic attestation or proof the private change was saved to disk. A rollback can restore an older private trend; the already committed public report remains truthful as a reported action. There is no transferable balance or cross-save inventory transaction.

## Existing agent integration

Actor inspection exposes `dewford_trend` with actual words, seed and receipt. The existing bounded history-rule mechanism accepts `dewford_trend_shared`, allowing independently authored valid world capabilities to respond to a real committed action. This draft installs no automatic policy, fixed quest, character memory, model call, reward or fictional attribution. Existing ownership/rate/revision validation in those capabilities still applies.

## Safety

- Current authenticated native channel and fresh matching presence required; stale/replaced sockets, active encounters and active link sessions rejected.
- Publishing requires the real Dewford map and facing the stationary phrase boy at `(1,6)`; native hook also requires local object 5 and actual successful acceptance.
- Bounded native pending/report/query state, strict numeric parsing, native Easy Chat validation, owner-bound adopted pattern, disconnect reset and no automatic resend.
- Later responses cannot silently override a followed revision; only the matching explicit request is accepted while free in the appropriate original map.
- During active native co-op sessions the overlay is unavailable. Normal local fishing initiation precedes such sessions. Linked behavior needs QA; no co-op catch equivalence claim.
- Client sequence prevents replay on that connection; an identical current public triple is idempotent and creates no new history receipt. Not a defense against a deliberately modified reporting client.
- No saved layout/schema/migration changes; no real saves used in tests. Maya's integration and all held operations are untouched.

## Verification

Run `PYTHONDONTWRITEBYTECODE=1 python test/test_dewford_trends.py` from the app root with the exact native submodule initialized. The isolated source worktree is supported too.

Synthetic tests cover actual native acceptance branches (including first-time no-reseed, rejection and duplicate), actual Feebas selection function with an isolated map/RNG harness, core enabled/disabled UBSan, owner changes, explicit immutable adoption, malformed/stale responses, disconnect, SQLite persistence/replay/replacement and actual server dispatch. These are component/integration harnesses, not a rendered fishing playtest.

Recovered-header syntax checks cover new core and `dewford_trend.c` on/off, with host-only string/ARM shims. Full exact native linking, script/UI timing, two clients, long suspension, actual Route 119 exploration, catches and real-save reload are **not tested**. Before enabling, Maya must verify the original boy interaction releases and publishes, two players can adopt the same pattern and observe real fishing, adoption never changes the town's saved trend, solo/private behavior remains intact, and disconnect/cancel/owner-switch restores private behavior.
