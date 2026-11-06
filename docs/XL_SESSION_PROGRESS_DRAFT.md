# XL event progress within a session

Offline generated XL interaction graphs remember their current state when the trainer leaves and re-enters the same area during one game process. Progress is keyed by the trainer's native ID and exact map, cast and event bytes, so replacing content or switching trainers starts a separate entry. A bounded four-entry FIFO cache holds the state in memory; older entries can be evicted, and all entries disappear when the game exits. This does not change the trainer save or provide durable or shared multiplayer progress.

Tests exercise the production C cache against different trainer IDs, changed content and online mode. Native CI attempts to play a three-state XL interaction graph, leave, re-enter and verify the state remains at three while preserving the save. Until CI passes the actual in-game behavior is unverified. This draft stacks #217 and its predecessors, and needs separate integration into the current candidate.
