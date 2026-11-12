# Remembering actual partner encounters

Separate app follow-on to #286, paired with native #27 at fc563ef178903b781f4812c32001b5892ecdd73f. Builder pin, gitlink and candidate manifest agree. Neither consolidated branch is changed.

## Connected path

A player with existing private encounter memory enabled meets the original Steven and accepts his supported one-wild-battle invitation. The existing native partner-battle cleanup receives the real engine outcome after restoring the prior partner party. This adapter retains that outcome and reports it privately once after returning to the idle overworld, bound to the invitation's save lineage.

Authority accepts only a matching connection/save invitation within 30 minutes, consumes it once, and stores at most 16 recent reports per trainer/actor. It neither publishes history nor changes the actor, party, inventory or battle rewards. Outcome names match the paired Expansion battle constants. They remain client reports, not authenticated simulation results or evidence of individual performance.

The existing memory view shows that save's recent results. The existing one-time reflection preview includes them explicitly; a player may request an interpretation and receive the resulting private response in a later original-character conversation. No live model is automatically called. Existing standing conversation-only grants deliberately exclude partner results, so their scope does not silently expand.

## Privacy and recovery

Remember-off, forget, save mismatch, connection loss and expired invitation prevent new storage. Forget removes stored reports. Different trainers and save lineages never share them. Reports lost on disconnect or restart are not retried or invented. An older server can refuse the optional CORE action; it is never sent as public chat. No full party, caught species or item details are transmitted.

## Verification

309 app/component tests passed against the paired native source, plus four native adapter component tests. The paired regression compiles the actual C adapter, triggers its cleanup and field update, and sends its emitted packet through authenticated authority dispatch. Tests cover one-shot emission, in-battle deferral, disconnect, ownership/save isolation, opt-out/re-enable, replay, restart/forget and exclusion from standing grants.

The native battle launch, rendering, real save/reload and live-model interpretation still require Maya's integration QA. This report cannot grant NPC experience, establish a training result, unlock public rewards or replace canonical teams.
