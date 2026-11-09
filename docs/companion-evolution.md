# Isolated earned level evolution candidate

This is a host-only experimental path, disabled until the exact native executable
passes linked QA. It does not yet expose autonomous evolution to the model author.
The author cannot invent a new species or claim a victory. The host chooses an
actual completed practice receipt for an owned benched individual. The native
engine determines whether ordinary unconditional level evolution applies.

The isolated EVOLVE1 entry consumes full Pokemon state and the verified previous
level. It calls GetEvolutionTargetSpecies, CalculateMonStats, EvolutionRenameMon
and the native evolution move learner. Conditional, trade/item and split evolution
are outside this slice. Empty move slots can learn; full sets decline replacements.
Held-item restrictions remain native. No player party, Pokedex, save or story
trainer party is modified. Practice itself is bounded native experience exercise,
not a battle victory or encounter.

The dispatcher requires the exact completed local practice job and reconciled
world receipt, matching executable digest and full state. It claims the job before
running, retains the result before authority reconciliation and can safely retry
a lost authority reply without rerunning evolution. A running/failed native job
requires host inspection. No automatic uncertain execution retry occurs.

Authority imports the full result only for a currently owned benched companion.
Personality, original trainer, level and experience must remain unchanged. Every
historical ownership alias changes species together, and custody tombstones remain
so the old species cannot reappear as a second owned Pokemon. Existing voluntary
lineup preparation subsequently makes the evolved individual available to optional
native trainer battles. Canonical Wally story teams remain untouched.

Host command after linked QA, using the existing practice ledger and admin socket:

    python -m world.companion_evolution --db NPC_LEDGER --engine NATIVE_BINARY \
      --sha256 EXACT_BINARY_DIGEST --socket WORLD_ADMIN_SOCKET \
      --actor ACTOR --individual INDIVIDUAL --practice COMPLETED_JOB \
      --validated-evolution

Compile native with WORLD_CHARACTER_EVOLUTION_EXPERIMENT=1 only for QA. This is
not enabled by the ordinary launcher. Full native linking, actual species-table
resolution, moves/stat behavior and subsequent rendered challenge need Maya's QA.
Tests use explicitly fake native state for reconciliation and mocked Pokemon APIs
around the actual C adapter; they do not prove a real evolution happened.

This independent candidate is based on our #339 draft stack, not released RC12
(app f484577b606348d07337387f14f75ab8cf4970b6, native
f7a813317d1b9fec803b48b682f5d74245c79037). Maya must reconcile release fixes. No merge,
release or live save access is part of this work.

## Paired draft

Native #42 at 00985f9f56baf57b988943e3ff26ad2c0eef1a24 is now published after
specific approval. The app builder, gitlink and candidate manifest match it.
EVOLVE1 remains compile-time disabled by default; the published source is not a
linked-QA attestation. No normal launcher option enables the experiment.
