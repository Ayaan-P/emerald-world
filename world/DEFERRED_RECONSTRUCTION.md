# Deferred reconstruction

Independent app continuation of #413. Native pin remains #74
c727376a85d9a5dedc5207e435d66417d46a01f5. Maya's #410/#72 and released RC12
are unchanged. No native edits, denied operation retries or live providers.

## Actual player journey
An agent inspects the current public 63x63 event-outdoor map with
`world.inspect_environment`, then plans `world.reconstruct_environment` using that
own inspection receipt and a bounded list of terrain cells. Players already inside
keep playing: they are neither moved nor disconnected by this plan. `/guild
reconstruction` shows the latest planned/finished work. It does not let players cancel
someone else's plan.

The durable actor runtime waits until the existing authority reports the area vacant,
then uses the unchanged `set_shared_geometry` transaction. Returning clients receive
the actual committed CAVE TERRAIN payload. Grass, tall grass and water retain their
existing native field/encounter/Surf semantics. This is not live construction under
players, actor labor, an item economy or proof that a client rendered the change.
Original Hoenn and private parties/saves are not edited.

## Lifecycle and control
- Own inspection and actor plan identify the job, destination, terrain revision and
  exact cells. Validation checks supported kinds, duplicates, protected cells and
  connected geometry before queueing.
- One pending plan receipt survives restart. At most16 pending jobs per actor and128
  globally; completed history does not consume pending capacity.
- Occupants leave naturally. Both generated-area state and last map position are
  checked exactly as in the existing geometry transaction; a busy/menu player does
  not count as vacancy. Existing native compatibility/empty-area rules stay intact.
- Intervening world/destination/terrain changes produce `reconstruction_conflict`,
  changed=false. No automatic rebase or overwrite. A dependent agent step must inspect
  the outcome, not assume a succeeded tool receipt means construction happened.
- Completion result is persisted in the same transaction as terrain. A repeat poll
  after lost runtime-receipt delivery returns that result without another edit.
- Execution depends on the actual actor plan remaining scheduled. Replacing/stopping
  a plan does not start a detached constructor. Its stored pending job can be cancelled.
- `world.cancel_reconstruction` cancels the actor's own pending job. The existing local
  authenticated admin endpoint accepts `{"command":"reconstruction"}` to list, or
  `{"command":"reconstruction","cancel":"exact job ID"}` to cancel as host.
  Cancellation never rolls back completed terrain.

The metadata retains place identity, observed revision and real history evidence.
Planned/cancelled/conflicted/finished events distinguish intention from authority
commit. No NPC growth, catches or player consent to unrelated data sharing inferred.

## Supported scope and verification
Only existing archived format9 outdoor terrain, not selectable outdoor format16,
original maps or generic cave topology. No negotiated live geometry path is claimed:
its revision/ACK owner is the unchanged native bridge.

Tests exercise occupied wait, restart, actual terrain/connectivity change, atomic result
recovery/no replay, conflicting revision, actor/host cancellation, public command,
last-position occupancy and returning-client native terrain transfer. Existing
immediate reshape tests remain passing. Full linked/native rendered gameplay, save
and multi-client QA remain with Maya; these tests are authority/component verification.
