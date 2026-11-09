# Owned companion practice capability

Stacked on agent trainer lineups (#312). Native pin unchanged.

An autonomous world-owned NPC can choose `world.practice` with an `individual`
from its own on-team roster. The capability creates a durable request, not XP.
The existing host dispatcher discovers it alongside retained intentions. Only
its separately enabled `--validated-native` exact-binary runner may execute the
exercise; authors cannot choose a binary, grant growth, or enable the runner.
Host steps/cap and existing dispatcher limits still apply. This is not battle
simulation, an encounter, a victory, evolution, or a player-save operation.

The request binds world, actor, plan step, current version and exact companion
source token. Withdrawal/change removes it from dispatch. Reconciliation checks
that same binding and stores the tool result atomically with full native state.
The plan waits without model calls until that actual result; a later optional
challenge uses the existing CHARPK2 full-state transport. Identity stays fixed.

## Host and QA boundary

The existing `python -m world.cast_practice_worker` one-shot host workflow remains
necessary. This PR does not start it in the launcher or attest native QA. Without
a validated runner the request stays pending, never successful. Existing dispatch
limits (eight lifetime intentions per actor) remain; an exhausted or failed host
job needs host inspection, not automatic replay. Failed/uncertain execution does
not fabricate a tool completion. Withdraw/revise the plan to stop waiting; no
already committed practice is undone. This limitation is explicit rather than a
claim of unlimited autonomous training.

Component tests use the actual C practice/battle adapters with fixture Pokemon
storage/stat APIs. They cover request -> restart -> actual subprocess receipt ->
reconciliation -> full-state challenge, disabled runner, withdrawal, unknown
individual and duplicate dispatch. Full linked-engine isolated-entry QA and
rendered gameplay remain Maya's responsibility before enabling the worker.
