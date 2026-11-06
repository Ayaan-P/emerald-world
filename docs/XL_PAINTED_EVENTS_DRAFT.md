# Agent-painted XL story worlds

An agent can compile an offline 127×127 area with bounded water, grass and tall-grass paint, up to three positioned characters, and state-dependent dialogue. `python -m world.xl_painted_events input.json area.bin` writes an inert file; adding `--replace-output` explicitly atomically replaces an existing regular file so the running offline game can pick it up on re-entry. Python and native validators check protected entry/exit, walkability and connectivity, character positions, literal text and bounded graph rules. The game executes a fixed interpreter, not generated code. No model is called by this compiler.

Native CI attempts a graph across two characters on painted terrain and a second test that replaces a world while the game is running, then re-enters and advances the new story. Until CI passes these are unverified. No real model, visual or multiplayer test is implied. Tall grass depends on the separate empty-party fix.

This draft stacks #222 and predecessors, but is independent of #219–#221. This branch includes offline story persistence that keys painted worlds by their full canonical palette identity. Integration and combined-candidate checks remain separate.
