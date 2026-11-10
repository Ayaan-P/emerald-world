# Voluntary NPC method exchange

Separate draft on #426, not Maya's reconciled #410 or released RC12. Native #79 remains pinned and unchanged.

A generated NPC can offer a method retained from its own completed public action receipts to an adjacent stationary generated NPC using `world.offer_method`. The independent recipient chooses `world.respond_method` with accept or decline; the donor can withdraw while pending. Offers expire after ten wall-clock minutes and a donor may have eight unexpired offers. An expired or settled lesson ID cannot be reused for another offer. No provider is enrolled or started by this feature. Existing followed-character event triggers and host budgets govern deliberation.

Acceptance retains the teacher's identity, original receipt evidence, exact method digest and lesson identity. It is a recipe, not the recipient's first-hand experience or mastery. Inherited recipes cannot be offered again as original experience. After actually executing a recipe successfully, the learner can use the ordinary remember-method capability to retain its own genuine experience.

Execution requires a separate chosen plan. The existing compiler expands `world.perform_method` into fresh observation, pathfinding and ordinary guarded capabilities, with separate actual receipts. Existing reviewed methods cover observe, navigate, inspect-object, use-object and set-weather. They do not allow arbitrary code, private information, player input, Pokémon transfer, or save mutation. No old revision or successful outcome is replayed.

Player-visible effects are the ordinary admitted movement/object/weather actions, not acceptance itself. `/guild methods ID` shows the retained recipe's teacher. Lesson events and runtime discovery are public. There is no new native teaching animation, player command to force teaching, guarantee an NPC accepts, or guaranteed model response.

SQLite persists offers, decisions and recipient recipes. Runtime execution transactions retain decision and event together. Duplicate decisions do not repeat the handoff. A changed meeting, expiry or occupied method name blocks acceptance. Withdrawal after acceptance does not erase a learner's already accepted recipe. Failed later execution stays a failure and cannot be retained as successful experience.

Validation uses the real authority runtime and generated-map movement reducers with authored test plans. No live model, rendered client, two-client playtest, or new native build is claimed. Prior full method execution restart and failure tests remain part of the regression set.
