# Two ordinary route trainers in co-op (experimental)

Default off: EW_DUAL_TRAINERS=0. Explicit development option:
--experimental-dual-trainers --development. Both peers need the same enabled
cohort; its negotiated version is distinct before private party staging.

Scope: Emerald's existing encounter where two separate ordinary trainers approach
at once. This is not a new generated battle or a duplicate team. The capture gate
requires both trainers to be locally present, ordinary non-boss single trainers,
with direct trainerbattle commands and no special continuation/rematch/rival tail.
Unsupported scenes keep the original solo path. Existing Team up / Face alone and
bilateral preparation options remain independently configurable and unchanged.

The exchange carries two IDs/counts and up to six native Pokémon per trainer.
Staging populates native opponent A and B parties separately. Opponent B retains
its own party indexes, switching, portrait and trainer ID. Flat 0..11 receipt
indexes never become native six-slot party indexes. Reward/completion masks are
16-bit in the new cohort, and full-party rotation records participation against
all twelve potential opponents. Private EXP settlement projects one acknowledged
defeat at a time into native slot zero, preserving that defeat's species, level
and personal participation mask. Stock prize calculation sees TWO_OPPONENTS and
both IDs. No prize amount, Pokémon or story item is invented by this patch.

The original encounter owner retains its stock callback and two approached
trainer contexts. A guest receives ordinary trainer flags only after the existing
committed, valid personal victory receipt; each trainer is independently checked
against that guest's current local objects/scripts. Special story tails are never
run for a guest. Existing Rusturf/Roxanne/Woods one-trainer completion consumers
reject this dual receipt rather than treating it as a single story outcome.
Ordinary flags remain normal in-memory native progression, persisted by the
player's normal save behavior, not a new automatic/durable transaction journal.

Limitations: special story/rematch/Gym pairs and trainer pairs with continuation
scripts remain solo. Dual battles suppress the existing one-trainer living-cast
report rather than falsely describe the pair as one opponent. This patch does
not implement two-character cast reporting. No new region save schema or arbitrary
script execution. No changes to Maya's integration branch or held payloads.

Checks: seven focused tests, including compiled production header/ABI layouts
for eight build configurations, all 36 party-size/index mappings, 12-bit completion
agreement/replay/stale-session checks, private EXP projection and full-party
participation retention for opponent 12. Four app checks cover the explicit
experimental option/default-off build and existing regional/Rusturf contracts.
These are component/integration-boundary tests, NOT an end-to-end engine playtest.

Full native link and rendered two-client QA remain unavailable because the
private native checkout cannot be initialized through shell Git authentication.
Before enabling, verify an actual ordinary pair (Route116 Sarah/Dawson is a
source-grounded candidate), team/solo/cancel/disconnect paths, both AI parties'
switching, trainer portraits, prizes, EXP/evolution after all twelve defeats,
private flags after victory/loss and stock owner scene resumption. Run existing
single-opponent/story/capture/medicine/discovery regressions as well. No actual
user save or live provider was used in development.
