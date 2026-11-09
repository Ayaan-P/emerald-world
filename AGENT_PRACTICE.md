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

The launcher Living Cast panel offers an advanced validated practice worker. Host
must attest the exact configured binary SHA256 passed isolated-entry QA; authors
cannot enable it. Defaults are eight exercises per actor per 24 hours, configurable
1..64 per 1..168 hours. A durable budget resets on the next eligible claim after
its period, with no catch-up credits or reset on restart/backward clock. Legacy
dispatch history remains deduplicated; it does not permanently exhaust new windows.
One session-owned worker polls every five seconds and stops on disconnect/close.
It halts on blocked/failed execution for host inspection, never retries uncertain
work. No persisted auto-start or QA attestation: reopening requires explicit enable.
The existing CLI one-shot workflow also remains available. Neither workflow
fabricates completion when absent or halted; withdraw a plan to stop waiting.

Component tests use the actual C practice/battle adapters with fixture Pokemon
storage/stat APIs. They cover request -> restart -> actual subprocess receipt ->
reconciliation -> full-state challenge, disabled runner, withdrawal, unknown
individual and duplicate dispatch. Full linked-engine isolated-entry QA and
rendered gameplay remain Maya's responsibility before enabling the worker.
