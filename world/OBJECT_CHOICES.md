# Shared object choices

Agents can author alternative player actions, rather than making every player press invoke one fixed default. The existing `world.program_object` state schema now accepts optional `choices: [action_name, ...]`. These must be distinct transitions in that state. Omitted means no choices, preserving existing programs and agent-only actions. The normal native A action remains the state's `use` action.

Stand facing a compatible generated-world prop. In the game's existing chat UI, enter `/guild object choices`, then `/guild object choose TOKEN ACTION` using a displayed choice. This is a real chat-command interface, not a new native option menu. Choices affect shared objects and are visible to other players. Inspecting never executes an action. Choices expire after 60 seconds or a mechanic revision, are session-bound and single-use, and require current facing, readiness and exact region admission. No personal message is published.

The selected transition executes through the same staged sandboxed handler and native object snapshot as agent use and ordinary A use. Other players see admitted text/appearance changes; failed admission does not report success. Choosing an alternative, then an agent using the resulting state, composes without predefined story content. No player bag, rewards or save mutation is introduced.

Existing reusable dispatchers are upgraded only when the entire previous helper and wrapper match their reviewed forms. Its historical receipt remains idempotent; new requests retain the existing bounded current-receipt and immutable transition archive model. Modified dispatchers still fail closed. App restart retains admitted object state; disconnected sessions lose unused choice tokens.

This branch builds on #375 `e5ee569dadb5b436c3e898887f6c6eeae3f0b0fd` and retains native #55 `babbe0e3272120523d509cecf22705f158429586`. It is not based on released RC12 and does not replace Maya's integration. No denied native or documentation upload is included. Inherited spectating remains disabled by the app's older-stream rejection, and no live direct-provider session should run pending the separate finite-budget correction.

Tests exercise real authority admission, alternate transitions, rejection, restart, guild dispatch and verified legacy dispatcher migration. Linked native rendering, live models and multi-client playtesting remain integration QA, not established by these component tests.
