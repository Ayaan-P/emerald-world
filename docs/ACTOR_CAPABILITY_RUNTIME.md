# Composable actor capability runtime

This is a separate app-only follow-on to #286, retaining native #26. It does not add a named-character scenario, a route, a race, a new rematch or a new native hook. Existing actor identities remain content; the execution layer has no Wally/Rydel/Briney/Steven branches.

## Why change the approach

The prior API grew a separate record field and executor for each feature. That made it too easy to build more preset workflows rather than a world actors can operate. The new layer separates **capability implementation** from **agent-authored composition**. It reuses existing provider authoring, public evidence, transactional authority, project state and correspondence instead of installing a second agent framework.

Sources reviewed:
- [Anthropic: Building effective agents](https://www.anthropic.com/research/building-effective-agents) distinguishes predefined workflows from model-directed tool usage and recommends simple composable patterns.
- [BehaviorTree.CPP](https://www.behaviortree.dev/docs/intro/) provides the useful precedent of composable reusable action nodes. This implementation is not a behavior-tree library and does not pretend to execute arbitrary asynchronous actions.
- [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence) distinguishes execution checkpoints from long-lived memory. Here, existing SQLite transactions and per-step receipts provide the necessary durable boundary without another storage/runtime dependency.

No framework was installed, no live model was called, and no third-party service receives new data from this patch.

## The actual loop

1. Existing author inspection includes `actor_runtime`: registered capability descriptions, argument schemas, actual currently available actor actions, scoped generated-map geometry lookup requests, actor kinds, current plans and committed receipts.
2. An agent chooses its goal and writes an optional `plan` through the existing typed canonical action admission. No default plan or future arc is installed.
3. A plan has an identity, purpose and up to six steps. Each step selects a registered tool, arguments and earlier-step dependencies. Scalar arguments can reference actual committed results using `{result: step_id, key: result_field}`.
4. The existing authority idle loop executes one ready step at a time. Preconditions and ownership are checked by the actual tool adapter at execution, not inferred from plan prose. Effects and success receipts commit together.
5. A refusal rolls back the step, publishes a bounded blocked observation and stops that plan. The normal agent reaction queue receives the actual outcome and can choose a new plan, wait, change a goal or stop. It does not blindly retry a failed action.
6. Removing the plan stops future steps. Replanning uses a new plan identity; committed effects are not undone or relabeled. Restart resumes from actual receipts without replaying succeeded steps.

Plans are bounded for workload control, not because characters have fixed six-step lives. The agent can author another plan from real outcomes. A plan's purpose is not proof of accomplishment.

## Initial registered adapters

- `world.act`: executes an available shared-state action already assigned to the actor by the existing opportunity authority. Exact pack, scene, choice, map and revision remain validated. The result contains actual state revision, changed qualities and result text. This changes real player-facing opportunities but does not claim physical labor, travel, native inventory or XP.
- `actor.message`: delivers bounded public speech to another existing actor through the existing correspondence implementation. The returned receipt proves delivery only. It never makes the recipient accept, agree or act. Existing public evidence and reply-chain restrictions remain.

These are real adapters, not a claim that every desired game action already exists. Add a capability by implementing and registering its schema, effect and executor in host code. Agents cannot register arbitrary code, call shell commands, write save flags or acquire another actor's authority. No new character-specific switch is needed in the plan runner.

Legacy fields remain compatible, but an actor cannot simultaneously assign the old `world_action` executor and a new plan. Migration should use the plan for that work rather than run both dispatchers.

## Runtime boundaries and next extensions

The initial actor source is the existing canonical actor registry. Existing generated-character movement has different geometry/occupancy and completion machinery; it is not silently exposed as canonical travel. A future route capability should discover real reachable destinations, invoke that runtime only for supported actor/map types, and deliver arrival/interruption receipts. Original actors still only have their reviewed safe bindings.

Local actions remain transactional. The registered generated-map navigation adapter now supports pending execution and resolves only from the existing authority journey receipt. Other asynchronous native actions still need their own real completion adapters. Calling a native request API is not enough. NPC Pokémon training/evolution still requires verified engine semantics and full native validation; no planner can manufacture those results.

Private player memories, questions, party data and per-save progression are not new planner inputs. This public actor runtime consumes existing public evidence. Players are never assigned a task or forced to participate by a plan.

The source-author admission still retains its existing consolidation and model budget constraints. This patch is not a replacement for all existing runtime systems, a complete world simulator or proof that a live model chooses good plans.

## Validation

Production authority tests cover composing real state action -> addressed communication via result reference, restart between steps, no duplicate execution, an independent second actor using the same capability, failed preconditions, transactional rollback on receipt failure, explicit stopping, immutable plan identity, and actual tool-result -> reaction queue -> deterministic new authored plan. No scenario is enabled by default; named actors in tests are fixtures for the existing registry.

Run `PYTHONPATH=.:test/world python3 -m unittest test_actor_runtime -v` and `python3 scripts/check_living_cast.py`. Full native rendering and live-provider quality remain Maya's integration/QA work. No merge or release is included.

## Destination navigation through the same runtime

`world.navigate` is registered for active **world-owned generated characters**, not canonical original NPCs. An agent selects that actor by authoring its own plan and supplies only exact revision plus destination x/y. Discovery advertises actor kinds and an `inspect_saved_place` request for actual immutable geometry; the existing inspection endpoint can provide the map before the agent picks a destination. The adapter independently recomputes a bounded cardinal route using archived geometry, other NPCs and current reported ready-player occupancy. It rejects walls, unreachable destinations, entry/exit blockers and paths that violate existing joint route connectivity. It does not accept an authored route or cross-map coordinate.

The route goes through the existing trusted character-action compiler and ordinary sandbox staging/admission. Pending tool state is committed before staging is queued. Issuing a route is not success. The existing movement reducer advances actual authority coordinates, yields for occupancy, segments the route for native playback, persists movement and publishes its normal arrival receipt. Only that exact actor/journey receipt resolves the pending capability as succeeded. Restart resumes the already admitted source/state; an unadmitted or replaced journey resolves blocked/interrupted, not arrived. No unsafe automatic resubmission of uncertain work occurs.

One pending capability owns an actor's execution at a time; dependent steps wait for real results. Removing/replacing a plan stops tracking future work and records that completion was not asserted. It does not magically undo committed motion: cancellation still uses a normal versioned character action, whose control replacement is validated by the existing movement authority.

Current limits are existing 31/127 immutable supported generated maps and at most 64 cardinal steps, never original Hoenn geometry, original cast relocation, cross-map travel or client-rendered proof. Other actors choose their own plans. No canonical actor can invoke navigation on an unrelated world actor through a target parameter.

Additional authority tests choose destinations without path input, route around another NPC, run a second actor to a different destination, pause for a newly occupied next tile, restart mid-journey, and check unreachable/interrupted staging produces no arrival. They execute the compiled existing reducer through real authority commit validation; sandbox subprocess execution and rendered motion remain integration QA, not claimed by these fixtures.

## Local observation after actions

`world.observe(radius)` is a world-owned actor capability with radius 1..4. It reads the actor's actual committed position and exact archived geometry at execution, rather than accepting a caller-supplied location or revision. It reports connected nearby floor, boundary obstacles and public objects on that same map/revision. Walls stop expansion. The result includes its authority revision, actor version and coordinates; it is a historical snapshot, not a guarantee that the scene remains unchanged.

Compose navigation followed by observation using `after`, then let the existing outcome reaction author choose a new plan from the returned facts. No handcrafted route or canned observation is needed. Results persist across restart and can supply scalar references (such as revision/x/y) to later steps. This primitive does not report player identities, occupancy, private relationships, object dialogue, encounters or Pokémon sightings. It does not infer physical eyesight, canonical actor locations or cross-map presence. Other existing author context remains available; this adapter is local sensing, not a global fog-of-war rewrite.

Tests cover two actors' different neighborhoods, an unseen wall hiding the area behind it, exact revision separation, actual navigation-to-observation composition and durable snapshots after restart. No live provider or rendered game validation is implied.

## Observation-bound ground modification

`world.open_ground(observation, x, y, width, height)` opens an agent-chosen rectangle of previously observed ground, up to 5 by 5 cells. Supply the own observation step's durable sequence via `{result: "look", key: "tool_receipt"}`. This reference is supplied by the runtime, not invented by the model. All patch cells must lie in that bounded observation; at least one must actually change. Actor position/version and exact map revision must still match.

Supported scope is deliberately the existing plain 127x127 shared XL format. Only additive floor is allowed: no removal of existing paths, border/portal changes, wildlife-format conversion, native Hoenn edits or rewriting opened immutable region destinations. The existing SharedCave connectivity validator, occupied-map refusal, pending-interaction guards and character-rebinding transaction remain in force. No player is moved, no tools or materials are invented, and no animated labor is claimed. This is an authority-executed fictional world modification.

Geometry, stable place continuation, persistent character bindings and the successful tool receipt commit in the same database transaction. A receipt failure rolls back the edit. Positions stay unchanged; only exact revision bindings advance. A restart cannot replay the action. A stale or occupied map produces a blocked result and requires an explicit new plan, not an automatic retry. The resulting revision can feed another observation or navigation step, enabling open-ended composition rather than a predefined courtyard or character scene.

Regression coverage includes observation-to-edit on two actors, a changed map requiring a fresh observation, occupied-map refusal, unobserved terrain refusal, rollback on receipt failure and restart. Native presentation and live author behavior remain integration QA.
