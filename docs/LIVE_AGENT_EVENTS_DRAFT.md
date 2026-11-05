# Owner-agent event control (experimental)

An authorized owner agent can set the interaction-graph state for one connected trainer in an active CAVE9 event area:

`python -m world.agent_event_control --admin-socket /path/to/owner.sock --trainer TRAINER --area AREA_SHA256 --state 3`

The authority only queues a command for the named authenticated trainer when that trainer has acknowledged the exact active event-area identity and is currently reported inside that area. The owner-only endpoint rejects invalid state values, wrong identities, absent trainers and queue overflow. The recipient client checks the identity and sequence, defers state assignments while a script, battle, transition or movement is active, and drops a pending assignment on disconnect, replacement or departure. Later interactions use the assigned state; other trainers' states are unaffected. No inventory, saved progress, executable code or arbitrary engine memory is changed by this command.

`ok: true, queued: true` means only that the authority queued a command. The response includes a connection session and sequence. An owner agent can query `python -m world.agent_event_control --admin-socket /path/to/owner.sock --trainer TRAINER --area AREA_SHA256 --status SEQUENCE --session SESSION`. The status is `queued`, `applied`, `rejected` or `unknown`. Applied/rejected is a report from the authenticated game client, not independent proof. A command can remain queued or become unknown after departure, overflow, disconnect or retention eviction. The session disambiguates reused sequence numbers across reconnects. Keep the original response and do not automatically replay an uncertain command. State is temporary per-client state, not durable or synchronized. The feature is experimental, enabled only for CAVE9 event areas, and uses the existing owner-only admin boundary. Tests exercise the authority and actual native bridge in memory; no real socket session, live multiplayer session or third-party agent was exercised. Inspect exact-head CI for native build and offline playthrough status.


## Change a rule while playing

The same owner-agent command can add or replace a rule for one trainer's active instance:

`python -m world.agent_event_control --admin-socket /path/to/owner.sock --trainer TRAINER --area AREA_SHA256 --state 5 --npc 1 --next-state 6 --text "Hello, traveler!"`

The owner authority validates target, state, character and bounded literal text. The recipient independently validates the rule and applies it only when ordinary gameplay is ready. A matching (state, character) rule is replaced; otherwise a new rule is appended if the 24-rule limit has room. This patch affects only the named trainer and is held in a temporary runtime copy, separate from the authenticated published graph and its identity. It survives reconnect to that same area while the player remains inside, but resets on a new visit. It does not modify terrain, run scripts, grant items, write saves or affect other trainers. The immediate response still says only queued; query the returned session and sequence for the client-reported outcome. A full table, leaving or disconnect can prevent application. State and rule assignments share an eight-command FIFO; if it fills, later commands can be dropped and remain queued without an application acknowledgment. No actual socket or two-client session was tested.


The native client sends `APPLIED` only after its state or rule operation returns success, and `REJECTED` if native validation or capacity rejects it. The authority keeps at most 64 recent outcomes per connected trainer. A disconnected, replaced or evicted session reports unknown; a pending status is not proof of eventual delivery. Outcomes are client-reported, not tamper-proof receipts. No socket or live multiplayer end-to-end test has been run.
