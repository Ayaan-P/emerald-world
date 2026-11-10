# Ongoing local attention for world characters

A generated recurring character can choose `world.attend_local` through the existing configured author and capability runtime. It keeps sampling nearby public entities and weather while the character pursues other plans. A newly present character, changed sign, moved object or changed weather can become an actual source event for the character's next independent decision. No named scene or response is prescribed.

This closes a gap between a one-time observation and the existing one-target pending watch: the character need not know a future visitor's identity, block its whole plan waiting, or repeatedly call a model to inspect unchanged surroundings.

## What actually runs

The agent selects local/off, a connected cardinal radius of one to four tiles, and a minimum notification interval of 30 to 3600 seconds. Enabling records a baseline, not an encounter. The authority's existing capability tick samples exact archived geometry and current public objects. Meaningful differences produce `character_surroundings_changed`, with original before/after entity records and an explicit observation boundary. The existing enrolled author queue can then consider that evidence under its existing host controls and model budget.

The observation capability now includes public sprite, text and object kind. Attention compares those public properties and advertised interactions, rather than merely another character's internal version or a new source hash. A thought-only version change does not generate a visible-change loop. The character can re-inspect current state and choose existing actions such as a local address, a new route, changed public dialogue or an object interaction. None is automatically performed by the notice. There are no forced player interruptions.

## Boundaries and persistence

Only world-owned generated characters can register. Canonical Hoenn actors are not moved or given invented perception. Local connectivity, exact map revision and range bound every sample. No player names, positions, party, save, private speech or other player data enter the attention event. This is authority-state sampling, not rendered eyesight or a claim that every intermediate change was observed.

Walking or a pending player battle pauses sampling. When the observing character moves or its map revision changes, the baseline is rebased silently. That does not claim everyone at the old location departed or everyone at the new location arrived. Clock rollback also rebases. Restart retains the committed baseline and last event, preventing duplicate notices of unchanged surroundings. Retired or removed actors lose active attention registrations. An actor can stop its attention without deleting history; the maximum of 32 registrations is simultaneous, not a lifetime limit.

An entity no longer in a bounded sample is reported as no longer observed, not globally absent. A notice is not a meeting, agreement, achievement or guarantee that a model will respond. The author must already be enrolled and running; this feature neither starts a provider nor changes cost limits.

## Integration and checks

App-only child of #370 at 953b10e55397720797509b1fa8f2a04fe1fad8c5. Native #55 pin remains babbe0e3272120523d509cecf22705f158429586. Both pending native uploads remain excluded and untouched. The inherited app spectating mitigation still refuses the old stream.

The branch stack is not based on released RC12 (app f484577b606348d07337387f14f75ab8cf4970b6 / native f7a813317d1b9fec803b48b682f5d74245c79037). Maya's release and integration are unchanged.

Component tests use real authority admission, observation, history, capability registration and the enrolled author queue. They cover independent actors, new and changed public objects, range/revision separation, cooldown, restart, movement rebasing, clock rollback, stopping, and suppression of thought-only changes. They do not demonstrate live model decisions, rendered reactions or linked multiplayer gameplay. Maya owns integration and final QA.
