# One-shot goal review for generated NPCs

Independent draft on #424 (`8a15e97ee93dad053973d5bbf16b78522e9a6d92`), not Maya #410 or RC12. Native #79 unchanged. No held worker/bridge, save transaction or provider invocation.

## Why this is missing

The existing `canonical_routines` supports quiet-world decisions only for original canonical characters. Generated characters have goals, conditional plans, historical search, receipt-backed methods and event-driven author subscriptions, but can stop receiving author turns after choosing to wait in a quiet world. Population authors already have replenishing host-configured budgets; no replacement lifecycle is needed.

[Generative Agents](https://arxiv.org/abs/2304.03442) separates experience, reflection and planning. The useful transfer is the ability to reconsider an intention without inventing an event. [Voyager](https://github.com/MineDojo/Voyager) combines an automatic curriculum, reusable skills and execution feedback; receipt-backed methods and result replanning already cover much of that here. Neither paper's narrated achievements are imported as game facts. No external code/assets copied.

## Authoring and execution

An already host-enrolled generated NPC may set the optional typed field:

`goal_review: {"id":"consider_route","goal":"Explore Cedar","after_seconds":3600}`

`goal` must exactly match one of its current goals; delay is 60..86400 seconds. This is a single opportunity to reconsider, not a recurring schedule, action script, task completion or fictional activity. The author can choose an actual guarded plan, change its goal, wait, or set the field to null. Another future review requires a new ID. A consumed/cancelled ID cannot replay; redefining an ID does not schedule another turn.

The existing author queue waits until caught up with public history and other author turns. Reviews defer while a normal/method plan is unstarted or pending, or a character is walking. Terminal/blocked plans may be reconsidered, without silently replaying them. `prepare` checks current actor version, review, goal and absence of unfinished work again, and fetches the exact existing public evidence cited by that character. No timer event is inserted into world history. Fresh inspection and existing action validators still govern any eventual effect.

The queue persists chosen IDs and due times. Restart causes at most one due turn, no catch-up burst. Clock rollback rebases a waiting window conservatively. There are at most eight queued reviews per actor per UTC day, with the budget surviving review removal/replacement and conservative rollback handling. Existing host enrollment, cancellation, population attempt budgets, author rate limits and worker configuration remain required. This is not a dollar budget or a guarantee that the model makes progress. No automatic enrollment or provider launch.

A host with multiple independent queues should not interpret this queue-local limit as a world-global spending cap. No live provider execution was performed.

## Demonstrated scope

Tests exercise real queue/reaction preparation, typed action compilation and authority admission of a changed NPC goal and native-visible greeting. The response is a hand-written author fixture, not a claimed model decision. Ordinary existing capabilities remain available for movement, interaction and construction, but this test does not establish an autonomous long-running playthrough or rendered native QA.

Also covered: quiet history remains unchanged by time, one-shot behavior, restart, no catch-up, clock rollback, stale withdrawal, unfinished plan checks, daily replenishment, bounds and no enrollment. Canonical routines remain unchanged.

Verification: `test_npc_goal_reviews test_canonical_routines test_population_agents test_character_reactions test_characters test_character_actions test_author_capability_loop test_actor_methods`: 54 tests, 52 passed and 2 existing sandbox/provider skips. `git diff --check` clean.
