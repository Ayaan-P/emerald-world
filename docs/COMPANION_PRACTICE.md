# Recurring NPC practice and persistent battle state

This candidate connects agent-authored **world-owned recurring NPCs** to bounded isolated practice, durable full Pokémon state, public result history, another author turn, and the existing native trainer-battle adapter. It does not replace canonical story parties or claim unobserved victories. Maya owns integration, full native QA and release.

## Execution and authority

A recurring character may retain up to three intentions with fields `id`, `kind: "practice"`, `target` (an identified member of its own team), and `reason`. The typed character-action compiler admits them through normal state/version/evidence validation. The host dispatcher reads a minimal admin endpoint containing world ID, actor versions and practice intentions, never player parties, save paths or private conversations.

The operator must first validate the exact complete native executable. The one-shot command is:

`python -m world.cast_practice_worker --db NPC_ONLY_DB --engine VERIFIED_BINARY --sha256 EXACT_BINARY_HASH --socket ADMIN_SOCKET --validated-native --steps 256 --cap 20`

The validation flag is an operator deployment gate, not an additional player prompt. No binary, process or scheduler starts automatically. At most one intention runs per invocation, with eight attempts per actor/world. Failed or interrupted intentions do not silently rerun. The database must be a separate NPC-only ledger, never a player save or the live server database.

For a new world-owned companion, the host reads its exact durable species/personality/fictional owner/authored-level identity from authority and initializes the isolated native snapshot. Existing full state is never recreated by level. The dispatcher pins executable SHA256 and checks the exact intention/version before and after evaluation. Withdrawn or changed intentions discard results. Different builds or divergent local/world snapshots require explicit recovery, not silent migration.

The native `--character-practice` entry runs before normal player/save/window startup. It accepts one bounded stdin request and exits. INIT1 creates only a fictional Pokémon under a private zeroed creation context. STEP1 evaluates 1..1024 simulated daycare-style steps on an independent copy, one EXP per step. It uses actual Expansion growth tables, level calculation, move learning and stat routines, with an NPC cap independent of player badges. It does not simulate walking, battles, catches or species evolution. Source/result cannot alias live parties.

## Full-state reconciliation and battles

The isolated ledger retains every byte of the native Pokémon, including partial EXP, moves/PP, identity and other persistent attributes. Jobs freeze source state/revision, executable and exercise terms and apply locally once. A trusted local admin receipt reconciles to the same world-owned companion using a source token. Wrong identities, changed sources, excess EXP, different native build, replay with changed contents, and authored level resets are refused. Repeating the identical receipt is idempotent.

This is the local host trust boundary, not cryptographic proof of a battle. Public player/client result packets and model assertions cannot submit these admin receipts or grant training. The host must actually execute the validated native evaluator; its admin access is already authority-level access.

Successful reconciliation appends `character_practice_completed`, explicitly identifying simulated practice and a trusted local-host native receipt. It schedules another bounded author turn for an enrolled recurring character, allowing a new goal based on the actual recorded result. The effective companion snapshot is authority-owned outside authored module state, so later script ticks cannot overwrite earned state. Authored team levels can remain at the initial baseline or adopt the trained level; arbitrary resets are refused.

CHARPK2 negotiates `CHARACTER_BATTLE_V3` full-state descriptors. It uses the same 100-byte Expansion Pokémon schema as existing native co-op, not a vanilla save format. Native code validates encrypted checksums, enabled species, EXP/level, identity, item/move/PP bounds and stats before copying into the enemy party. The next battle preserves the complete trained snapshot instead of regenerating moves from level. Untrained members still use the existing fixed-identity factory. Existing explicit challenge, player readiness, region/ownership checks and frozen pending descriptors remain. Old clients refuse trained teams rather than lose state. Neither story trainer flags nor player parties/saves change.

The full host ledger remains pinned to an exact executable hash. CHARPK2 is a versioned reviewed wire schema; incompatible future native schema/configuration changes must bump negotiation rather than reuse it. Current full-state ABI and initialization still need complete native build verification.

## Canonical cast boundary

Original Wally, Briney and Rydel scripts/parties remain untouched. Their optional retained practice intentions still require separately registered, verified fictional companions and yield local-host-only receipts. They are not automatically reconciled into story teams, duplicated as dynamic NPCs or publicly marked fulfilled. INIT1's IV15 defaults are not Wally's original scripted IV/move presets. Steven's original party is likewise not intercepted.

## Failure and recovery

A native crash, timeout, withdrawal or malformed response produces no world growth. If local execution completes but authority reconciliation is refused or its outcome is uncertain, the dispatcher retains the exact authority payload in its local receipt. It does not rerun native practice or automatically resubmit. The operator must inspect/reconcile that payload; the server's identical-receipt handling prevents duplicate growth. A divergent/new host ledger must recover the full trusted snapshot, never initialize from a higher level alone.

## Validation and remaining gate

140 app tests and 10 native component tests pass. The paired regression exercises actual typed NPC state, authority admin dispatch, retained intention, pinned subprocess, complete snapshot persistence, world reconciliation, production C battle parser/factory, restart, legacy refusal and another history-driven goal update. A six-member V3 packet is also exercised.

These tests compile production protocol/evaluator/party code and actual growth tables/level calculation with **explicit test doubles for native Pokémon storage, move learning and stat APIs**. They do not prove full linked/rendered gameplay. Complete native TEST cases are supplied but have not run here; this workspace has a partial current paired tree and lacks SDL2. Full linked early-entry initialization, real move/stat behavior, cross-platform schema compatibility and rendered battle QA are mandatory before enabling the worker or releasing this feature. No live model, live player save, merge or deployment was used.
