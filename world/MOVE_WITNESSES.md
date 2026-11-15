# Local move witnesses

Independent app-only work after `dot/passage-lifecycle` at
`e6229adb57387edc4775a62e7f4c483d9d9fb7c1`, itself on #421. Not Maya's
#410/#72 or RC12. Native #79 remains unchanged. No new native transport.

## Playable consequence

An independently enrolled generated character can use `world.attend_moves`
with `mode=local`, connected radius 1..4, and notice cooldown 30..3600 seconds.
When a player explicitly uses an existing WORLD MOVE action on a nearby shared
object, successful admission records a causal local observation. This includes
cooperative contributions that leave appearance unchanged, which sampled local
attention cannot notice. No scripted reaction is installed.

The ordinary character author receives the exact notice as evidence and can
choose existing capabilities: freshly observe, speak, approach, contribute an
actually inspected owned move, or do nothing. The test fixture demonstrates a
real move admission through the existing object executor, enrolled author queue,
context validation, and normal action compiler producing visible NPC dialogue.
That response is fixture-authored, not a live model result or a mandated reply.
The existing author enrollment, provider configuration and host budgets apply.
No provider is started by registration.

`world.attend_moves` with `mode=off` removes registration and pending notices.
Reconfiguring starts fresh. Capability discovery reports registered observers
and bounded pending counts. This supplements, rather than changes,
`world.attend_local` and its sampled entity/weather behavior.

## Evidence and durable behavior

- Locality is the connected authoritative geometry at successful admission,
  before the effect moves any target. The target must be within the observer's
  own radius and exact generated revision. Walking/in-battle/inactive observers
  are excluded. It is not rendered sight or proof of player proximity.
- Player provenance stays `client_reported_learned_move`. NPC provenance stays
  `matching_native_move_inspection`. Only already-public move, performer and
  target identifiers are copied, not private party slots, individual state or
  native blobs. Private weather, sensing, encounters and healing are excluded.
- Capture runs in the existing object admission transaction. Failed admissions
  create no notice. The existing unique committed move receipt prevents replay.
- Pending observations survive restart. The notice and draining of its pending
  batch are one transaction; a clock rollback rebases the cooldown.
- At most eight causal records per observer per batch are retained, with an
  explicit omitted count. Original public receipts are never deleted. No
  invented summary fills omissions. There is no lifetime observation ceiling.
- Historical position/version accompany each record. Moving later does not
  make the historical observation current. Authors must freshly observe and
  use ordinary capability/version/ownership validation before effects.
- Own moves do not wake the same actor again: its existing action receipt is
  already available. No reaction, affection, assistance, PP, growth, or success
  is inferred from noticing.

## Verification boundary

Component coverage includes unchanged-object contributions, actual admission,
failed deployment, exact source receipts, local radius, multiple independent
observers, restart/replay, bounded batching/clock rollback, native-inspection
fixture provenance, real capability registration, author enqueue/context and
normal visible-action admission. No live provider, rendered two-client or full
current native build/playtest is claimed. Existing native UI and shared-object
transport are reused without changes. Shared object move actions still do not
consume battle PP.
