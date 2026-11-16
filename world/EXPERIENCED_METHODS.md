# Experience-grounded NPC methods (experimental)

This is a plan compiler, not a second action executor or arbitrary-code skill
library. A generated recurring NPC can retain its own completed public actions,
choose new literal bindings, and execute the resulting ordinary plan. Other NPCs
do not automatically acquire the method. No method runs merely because it exists.

## Connected player journey

An autonomous author first chooses an ordinary plan: observe the local map,
navigate to a tile, inspect an adjacent authored object, and use an advertised
action. Actual authority arrival and committed object receipts must finish.
The actor then chooses `world.remember_method(name, plan, parameters)`. Parameters
are JSON entries such as `{"target":{"step":"target","argument":"object"}}`.
These are references to literal argument slots in that actual completed plan,
not invented successful examples or generated code.

The discovered `actor_runtime.methods` catalog contains exact method digest,
source steps, parameter slots and source evidence. To reuse it, the author chooses
a new plan containing only `world.perform_method(method,digest,bindings)`. The
compiler persists the exact expanded plan and the normal scheduler executes each
fresh step. Fresh observation supplies geometry revision; `world.inspect_object`
supplies current adjacent object identity and revision. Stale/blocked work yields
normal blocked receipts, not a method-level success. Runtime inspection shows
both original invocation and expanded steps. Players can see actual existing
NPC movement and changed object snapshots, and `/guild methods [actor]` lists
retained experience and evidence. No new native animation is claimed.

## Supported and intentionally excluded

- Generated actors only; 2..6 sequential steps, each depending on all earlier
  steps. A method begins with `world.observe` and contains at least one completed
  effect. No conditional/skipped or partially completed examples.
- Reviewed tools: `world.observe`, `world.navigate`, `world.inspect_object`,
  `world.use_object`, `world.set_weather`. Weather remains existing environmental
  authoring, not a Pokemon power or verified client-rendered weather.
- Only radius, destination x/y, inspected object ID, advertised action, and weather
  mode can be parameterized, with original scalar types. Identity/revision inputs
  for actual effects must reference fresh in-method observations.
- Source effect outcomes must be the exact supported arrival/object/weather
  outcome, not merely a generic succeeded receipt or prose claim.
- Methods are actor-owned and immutable under their name; changed methods need a
  new name. Evidence and versions are retained. Discovery is bounded to 128
  methods and player display to eight; this is not a lifetime execution limit.
- No arbitrary code, nested methods, foreign/private knowledge, player bag/save
  mutations, canonical relocation, teaching, automatic proficiency or guaranteed
  future success. New native operations are not enabled.

## Recovery and permission boundaries

Invocation ID and expanded plan are stored durably. Existing per-step receipts
prevent replay after restart; a pending navigation resumes the existing journey.
Withdrawal settles pending receipts as blocked without manufacturing arrival.
Compilation does not change the actor's stored plan, bypass ordinary plan
admission, or relax any native geometry, occupancy, ownership or object guard.
New bindings are intent, not authority to bypass a guard.

## Branch and verification

Separate app child of #414 `df874120f485e3fe3479a672a5502cd74a7e4259`.
Native stays #74 `c727376a85d9a5dedc5207e435d66417d46a01f5`.
This is not based on RC12 or Maya's #410/#72 reconciliation. No frozen branches,
denied/uncertain operations, assets, native files or live providers are touched.

Component tests exercise real authority journey/object reducers, different
actors/targets, interruption, restart, no replay, failed outcomes, ownership,
strict binding types and both fake provider transports. Full linked native build,
rendered two-client playtest, provider behavior and release QA remain unverified.

Design inspiration: Voyager's reusable experience library
(https://github.com/MineDojo/Voyager). This implementation uses typed guarded plans,
not donor code, embeddings or executable model-generated programs.
