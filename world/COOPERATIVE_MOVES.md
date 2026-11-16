# Cooperative learned-move composition

Independent app work on #420 (`0ed32de6b43cdf6f77d554d584cbb9ff6e0c3aaf`).
Native stays pinned to #79 (`d1075e135c443e4e2cf1940fffa9657c3ed371ec`).
This does not change Maya #410/#72 or constitute an RC12 integration.

Existing `world.program_network` already defines a reusable state graph over two
to four real anchored props. States select appearance, nearby position, advertised
choices and learned-move requirements. This adds cooperative prerequisites to
that same executor, rather than another quest runner or new kind of move profile.

## Authoring

A state may contain `cooperate`, mapping member ID to completion action to a list
of two to four `{ "object": "member_id", "action": "contribution_action" }`
requirements. Repeating a requirement means distinct identities must perform that
same contribution. Different requirements can select different move families or
specific moves using the existing `moves` definitions.

Each contribution action must be a learned-move action and remain in the current
phase. A gated completion action must change phase and cannot be an implicit A
button default. At most four gates and four contribution-action types are allowed
per phase. Existing graph/JSON, geometry, ownership, action and collision limits
remain unchanged. No named character, move, story or puzzle is built in.

Example fragment inside an otherwise valid existing network state:

```json
"cooperate": {
  "control": {
    "complete": [
      {"object": "conduit_a", "action": "energize"},
      {"object": "conduit_b", "action": "cool"}
    ]
  }
}
```

The author supplies the real objects, graph and move selectors. This fragment is
not a shipped preset and does not create missing objects. Use a learned-move
completion action to expose completion naturally in the existing WORLD MOVE UI.
Other explicit actions retain the existing player-choice interface.

## Player and NPC behavior

- Players choose actual learned moves through existing WORLD MOVE negotiation.
  Only available actions are offered. Contributions produce their existing
  committed shared feedback; the completion action appears once requirements
  are met. `/guild object moves` also describes outstanding co-op requirements.
- NPCs independently choose `world.use_move`, with an actual owned individual
  and matching current native move-inspection receipt. No NPC is auto-enrolled,
  moved or assumed to have participated. Nearby observation exposes current
  gates, readiness and contributed identities.
- Distinctness means authenticated player identities or persistent NPC identities,
  not verified different humans. One identity cannot satisfy two required slots,
  even by using multiple Pokémon or repeating an action. Matching is per required
  action, not just a global count.
- Completion uses the ordinary mechanic admission and native object transport.
  Text, graphics and supported one-tile movement of linked props are real shared
  consequences. Occupancy/collision checks still apply. No terrain, bag rewards,
  battle results or unsupported animation is introduced.

## Evidence, restart and privacy

Only successful admitted object actions add contributions. Prepared requests are
recorded separately and do not count. Authority checks the precise network,
previous state, request identity and proposed state against that prepared intent;
mechanic source cannot manufacture contributor names or completed state.
The ledger and object receipt commit together. Replaying an admitted request does
not add a participant. Failed admission adds none. Phase changes clear the active
ledger, while existing history retains the actual action receipts.

The active ledger is bounded by four identities per contribution type, sufficient
for all four-slot matchings. It is not a lifetime interaction limit. Existing
reusable dispatcher compaction retains state/history and upgrades only the exact
recognized old dispatcher; arbitrary edited dispatchers still fail closed.

Shared object actions retain their existing **no battle PP consumption** rule.
Private sensing, encounter filtering, weather and healing still require their own
native selection/PP consent. They have no authoritative public completion receipt
and cannot be used to satisfy this system. Do not infer private results from an
authored profile or configuration event. This is not an automatic cross-system
macro, a shared-climate feature, or permission to spend another player's PP.

## Verification

43 app component tests: 41 passed, two existing sandbox/provider skips. Tests
execute actual actor-authored network admission, two player contributions,
duplicate-identity rejection, visible multi-object movement, failed admission,
forged ledger rejection, restart with partial progress, native-inspection-fixture
NPC contribution, dispatcher upgrade and existing 40-operation history/compaction.
Native inspection in that NPC test is an explicit reconciled-state fixture, not a
live native worker run. Existing native UI and transport are reused unchanged.
Rendered two-client and live native/NPC QA remain outstanding. No live provider
calls were made. Vanilla defaults and independent saves are unchanged.
