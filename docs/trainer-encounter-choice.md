# Trainer encounter choice (experimental, default off)

Built on native #112 / app #474, not Maya's integration branch. Enable only in a matching development cohort with `--experimental-trainer-choice`. This does not enable guest story continuation or change rewards.

## Player flow

A tagged player's ordinary supported trainer encounter is captured at the existing battle hook. Before an encounter offer is sent, an ordered authority HOLD acknowledges that the local encounter cannot be admitted as someone else's guest. The native screen then offers **Team up** or **Face alone** (default; B also selects solo). The standing tag remains active.

Team up waits for the existing range/readiness gate, with **B for solo**. After sending, B first withdraws the request through the authority; only the corresponding HOLD acknowledgement permits the original solo callback to resume. Once native linking begins, no instant-cancel promise is shown. Connection failure before native play uses the existing fallback. Failures after native play retain existing no-automatic-save/rollback semantics.

If both players independently trigger trainers, neither may borrow the other's trainer script. Those requests safely fall back to each player's own trainer; this is not a battle-selection or shared-credit system. An ordinary tagged peer without its own captured encounter still uses existing standing tag consent.

During solo play the authority holds only co-op admission, not tag membership. Once the player returns to a ready field, RELEASE is acknowledged and normal tagged play resumes. Disconnect clears ephemeral holds and tag consent. A missing cancellation acknowledgement closes the link channel after ten seconds (600 frames) before solo fallback; reconnect/re-tag is then necessary. A server that lacks this protocol must not be used with the experiment enabled.

## Boundaries

No changes to battle mechanics, trainer eligibility, items, flags, receipt schemas, save files, or history-sharing consent. No fabricated participation. No world bridge, character worker, Blender payload, or Maya branch changes. Not an implementation of shared Gym/story rewards. No durable holds survive connection loss.

The authority keeps a bounded per-tag local encounter token. HOLD closes only that tag's existing co-op reservation before its acknowledgement. TEAM uses the existing real coordinator and requires an unheld target; RELEASE cannot release an active co-op session. Native transport rejects guest admission while a local trainer is captured, including crossing OFFER/ADMIT reads. Matching token/tag checks reject stale acknowledgements.

## Verification and remaining QA

- Nine real broker/session tests: unsent choice, solo/tag retention, ordered cancellation, both crossing orderings, stale tag/token, disconnect and release checks.
- Server method test preserves connected-peer and same-region checks for TEAM.
- Seven existing link protocol regressions.
- Three focused native tests: production transport parser/API compiled with doubles; cancellation waits before exact solo callback; source UI/default-off contract checks.
- Two build-option/cohort checks.

These are component tests, not a rendered playtest. Full private native checkout is unavailable through current shell Git authentication, and the connector does not provide a repository archive. Full engine linking, task/window allocation, actual controller interaction, simultaneous two-client trainer encounters, field readiness refresh, connection interruption during link exchange, and normal return/re-tag require Maya's linked QA. Test only disposable synthetic saves until that review. No real save was opened or changed.
