# RC7 current workboard

## Mandate restored from parent history

Finish the EXISTING Expansion-backed RC7 integration as a playable multiplayer
game, with generated areas and privately owned parties/saves. Do not restart the
engine port or bring in newer Dot work. Trading is excluded by the user.

The coordinator reads production producer/consumer/cleanup paths, delegates
independent intelligent outcomes, integrates source and commits/publishes it.
Worker count, review prose and broad test volume are not progress substitutes.
Do not overwrite the donor, RC8 releases, desktop shortcut or human saves.

Historical parent context: session `20261105_201634_d7aae1`; initial native
upgrade request message 160809; explicit ANALYZE/DELEGATE/INTEGRATE message
165331; repeated correction against brute-force testing message 165335.
Recent instructions to exclude newer Dot work and trading remain controlling.

## Source of truth

- App: `worktrees/rc7`, branch `integrate/rc7`, gameplay checkpoint `670d991d`.
- Engine: `engines/expansion-native`, branch `integrate/rc7-world`, `dd4cbc90f9`.
- The app branch tracks `origin/integrate/rc7`, NOT `origin/main`.
- Latest native build: 22. Shared co-op acceptance: FAILED, not complete.
- `docs/RC7_INTEGRATION_STATUS.md`: binary-specific acceptance boundaries.
- `docs/rc7-evidence-summary.json`: extracted actual results readable by Dot.
- `docs/attempt-handoffs/rc7/CURRENT.md`: current source-only reconstruction.
- Local worker routing: `rc7-rescue/LIVE_PEERS.json`; integration queue below.

## Repository handoff

The engine is an existing submodule, not a newly created product. Its upstream
history contains tracked ROM/executable files. The original RC7 source-only
handoff deliberately shipped patches instead of publishing that entire history.

The latest engine delta is now in the SAME app repository, extending the prior
two patches. Applying all three against the pinned public base was verified
using a temporary Git index: the resulting tree is exactly
`0026146184b0eb0fe003742f6d4095aff3dc4fbc`, the engine checkpoint's tree.
No source worktree was reset or replaced to perform that check.

This proves source reconstruction, NOT fresh-clone dependency availability or
ancestry-check compatibility. The local engine commit is still not fetchable
from the upstream submodule URL. No full-history bundle is published.

## Verified checkpoints

- [x] Canonical native build19, mandatory relocation/layout/battle checks.
- [x] Ordinary actual two-client single battle and unlocked return: build16.
- [x] Independent normal save and cold Continue: build18; earlier apparent save
      failure was probe timing, not an established production save defect.
- [x] Generated-area interaction/return: primary build15 evidence previously read.
- [ ] Complete shared wild co-op: build19 advances past stock four-player startup
      but stalls in intro. Host `DoBattleIntro`, guest `BeginBattleIntroDummy`,
      both `BattleMainCB2`. Do NOT say startup remains the build18 four-peer wait.
- [ ] Complete shared actions, faint/switch handling, private rewards and return.
- [ ] Verify owner-only medicine/capture spending and abort/commit lifecycle.
- [ ] Integrate matching species-cohort authoring/authority/native wildlife source.
- [ ] Verify the resulting committed source as one playable build, then package.

## Active ownership and integration queue

Coordinator alone writes the primary tree and owns source commits/combined runs.
Workers write only their own checkouts and export deltas against recorded bases.

1. **Current co-op intro/controller blocker** — controller finisher in
   `coop-controller-finish-app`; original controller worker in
   `coop-dispatch-engine` owns command validation, pending replies and ACK drain.
   Their work must be reconciled, not whole-file-replaced over primary's working
   ordinary-PvP code. Feed them build19's actual intro stall, not the old crash.
2. **Medicine full-six closure** — `expansion-medicine-engine`; coupled tag250/A8
   request/reply ownership and stable-slot/stage-index mapping with dispatcher.
   Existing staged medicine is integrated; full-six correction remains queued.
3. **Capture ownership/transaction** — `coop-actions-engine` only. Prior
   cross-checkout writes were explicitly disallowed. Export actual pending ball
   spend/refund/commit delta and call coverage, not another helper-only proof.
4. **Species cohort** — patch-ready, not integrated. Exact exports:
   `species-cohort-parent.patch` and `species-cohort-native.patch`. Parent patch
   forward-check passed. Native patch has `engines/expansion-native/` prefix and
   needs `git apply -p3` from the engine root. Do not mistake the earlier wrong
   strip-level check failure for a source conflict. Own two-client v11 encounter
   evidence is a worker result, not primary acquisition proof.
5. **Online entry/save** — own cold-load goal delivered; parent build18 also
   passed. No save-specific production patch. Pending app authority/UI delta:
   `online-entry-parent-delta-20261106.patch`; review separately if needed.
6. **Generated journey** — delivered and primary-verified; retained available.
7. **Party/HUD** — earlier lifecycle changes integrated; last observed idle.
8. **Trading** — OUT OF SCOPE; stop/idle message sent, preserve existing work.

## Work discipline

Every accepted source batch gets an honest commit; parent gitlink and source
handoff are updated together before reporting the work accessible to Dot.
Verify remote branch after push. Keep failed and passing gameplay evidence
separate by executable hash. No new system installs, paid model invocations,
human saves, destructive cleanup or unrelated publication during organization.

## Current source after build19 diagnosis

Engine `dd4cbc90f9` fixes the second four-console assumption in
`Task_HandleSendLinkBuffersData` / `SENDTASK_STATE_COUNT_PLAYERS`.
WorldCoop's two transport participants can now release queued intro commands,
replies and DONE packets. Ordinary four-human Multi Battle behavior is unchanged.
Canonical build20 passed before the commit; actual `coop-build20` is pending.
The source-only handoff and verified reconstruction tree are updated with it.

## Original-system contract adaptation

See `docs/RC7_PORT_CONTRACT.md`: explicit original/target source paths and
startup, ownership, party ABI, FIFO request/reply, ACK and private-return contracts.
Build22 restores co-op intro full ACK barriers, owner-only replies and safe
completion padding. It is built, not gameplay-accepted; native dispatcher
validation/pending-request port remains incomplete.
