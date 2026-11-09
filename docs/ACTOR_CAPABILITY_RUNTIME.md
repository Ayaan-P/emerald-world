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

1. Existing author inspection includes `actor_runtime`: registered capability descriptions, argument schemas, actual currently available actor actions, existing actors, current plans and committed receipts.
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

Only local transactional adapters are registered here. An asynchronous native action needs an explicit pending/completion adapter and actual acknowledgement before it can be reported successful. Calling a native request API is not enough. NPC Pokémon training/evolution still requires verified engine semantics and full native validation; no planner can manufacture those results.

Private player memories, questions, party data and per-save progression are not new planner inputs. This public actor runtime consumes existing public evidence. Players are never assigned a task or forced to participate by a plan.

The source-author admission still retains its existing consolidation and model budget constraints. This patch is not a replacement for all existing runtime systems, a complete world simulator or proof that a live model chooses good plans.

## Validation

Production authority tests cover composing real state action -> addressed communication via result reference, restart between steps, no duplicate execution, an independent second actor using the same capability, failed preconditions, transactional rollback on receipt failure, explicit stopping, immutable plan identity, and actual tool-result -> reaction queue -> deterministic new authored plan. No scenario is enabled by default; named actors in tests are fixtures for the existing registry.

Run `PYTHONPATH=.:test/world python3 -m unittest test_actor_runtime -v` and `python3 scripts/check_living_cast.py`. Full native rendering and live-provider quality remain Maya's integration/QA work. No merge or release is included.
