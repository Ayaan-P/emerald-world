# Agent-authored XL interaction graphs

This adds bounded declarative interaction graphs to offline 127×127 worlds with agent-placed characters. An agent supplies a blueprint, cast and state/NPC dialogue transitions to `python -m world.xl_wilds_events input.json area.bin`. The compiler writes a new inert file. Native code validates cast positions, walkability, rule structure and literal text before staging. The existing event interpreter tracks the current state locally; no agent-generated code executes.

Tests cover invalid rule rejection and production C rule validation. Native CI attempts an actual offline game interaction across two characters, including one beyond the old map boundary, advancing through three states and preserving the save. Until CI passes this is unverified in game. No model, shared multiplayer state or online sockets are used. This draft builds on #215, #214, #213 and their predecessors; integration with the current release candidate is separate.
