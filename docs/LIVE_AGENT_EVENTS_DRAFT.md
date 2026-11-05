# Owner-agent event control (experimental)

An authorized owner agent can set the interaction-graph state for one connected trainer in an active CAVE9 event area:

`python -m world.agent_event_control --admin-socket /path/to/owner.sock --trainer TRAINER --area AREA_SHA256 --state 3`

The authority only queues a command for the named authenticated trainer when that trainer has acknowledged the exact active event-area identity and is currently reported inside that area. The owner-only endpoint rejects invalid state values, wrong identities, absent trainers and queue overflow. The recipient client checks the identity and sequence, defers state assignments while a script, battle, transition or movement is active, and drops a pending assignment on disconnect, replacement or departure. Later interactions use the assigned state; other trainers' states are unaffected. No inventory, saved progress, executable code or arbitrary engine memory is changed by this command.

`ok: true, queued: true` means only that the authority queued a command. It is not proof that the trainer received or applied it. A late command can be dropped after the trainer leaves or disconnects, and the client holds at most eight pending commands, and an overflow can drop later commands. The agent should observe the player's own client before deciding whether another command is needed; do not automatically replay an uncertain command. State is temporary per-client state, not durable or synchronized. The feature is experimental, enabled only for CAVE9 event areas, and uses the existing owner-only admin boundary. Tests exercise the authority and actual native bridge in memory; no real socket session, live multiplayer session or third-party agent was exercised. Inspect exact-head CI for native build and offline playthrough status.


## Change a rule while playing

The same owner-agent command can add or replace a rule for one trainer's active instance:

`python -m world.agent_event_control --admin-socket /path/to/owner.sock --trainer TRAINER --area AREA_SHA256 --state 5 --npc 1 --next-state 6 --text "Hello, traveler!"`

The owner authority validates target, state, character and bounded literal text. The recipient independently validates the rule and applies it only when ordinary gameplay is ready. A matching (state, character) rule is replaced; otherwise a new rule is appended if the 24-rule limit has room. This patch affects only the named trainer and is held in a temporary runtime copy, separate from the authenticated published graph and its identity. It survives reconnect to that same area while the player remains inside, but resets on a new visit. It does not modify terrain, run scripts, grant items, write saves or affect other trainers. The response still says only queued, not applied; a full table, leaving or disconnect can prevent application. State and rule assignments share an eight-command FIFO; if it fills, later commands can be dropped without an application acknowledgment. No actual socket or two-client session was tested.
