# Isolated capture experiment (disabled)

This candidate adds a trusted-host, one-first-throw native experiment. It is not autonomous live capture, a complete battle simulator, or a release-ready feature.

The native process owns a fresh private save, bag, parties and battle context. It chooses a weighted wild slot from the frozen format-10 habitat, creates the wild Pokemon through native code, removes one ordinary ball, uses the actual native catch formula/RNG/finalization, and stores a successful catch through GiveCapturedMonToPlayer. A failed throw is unresolved, not a victory or escape. No enemy turn, damage plan, badge history or ongoing battle is simulated.

Build the paired native experiment with WORLD_CHARACTER_CAPTURE_EXPERIMENT=1 only for QA. The default is 0. The host must validate the exact executable hash before opting into ledger execution. Native met-location, storage, battle context and linked startup need Maya's review. No live saves or live provider calls were used.

`world.capture_attempt_worker` provides an offline CLI and a durable ledger with explicitly provisioned finite ball stock, frozen input and at-most-once execution. A timeout reserves/spends the ball and requires host review; it never automatically retries. It does not trust a client result packet.

For authority integration, `world.character_capture.queue(server, ledger, actor, individual, engine_hash, ball, fictional_name)` freezes the actual existing full owned companion, world identity and actual generated habitat placement. `reconcile(server, ledger, job)` imports only a completed caught result onto the NPC bench, preserving full native bytes, personality and OT. Source/location changes refuse import. World-local receipts make retries idempotent. Existing prepare-challenge and trained-party transport can select the benched individual later. It never rewrites a current team or any player bag/save. Call these in the authority thread, not concurrently against a live SQLite connection. They are host APIs, not exposed agent/client commands.

Tests: native extracted-C decision differential covers 38,528 cases, plus private context/storage call-flow fixtures. App ledger/import tests use a fake native transport, with actual authority cave traversal, persistence and ownership reconciliation. These are not a linked native capture playtest. Full component suite passed before import addition; focused import checks pass. Keep disabled until linked native and two-client QA.

Paired native draft: Ayaan-P/pokeemerald-expansion-native#36, commit 570a0c3547de7eeb64b8d5373e959370fb486984. App remains default-disabled.
