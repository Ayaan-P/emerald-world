# Owner-agent event control (experimental)

An authorized owner agent can set the interaction-graph state for one connected trainer in an active CAVE9 event area:

`python -m world.agent_event_control --admin-socket /path/to/owner.sock --trainer TRAINER --area AREA_SHA256 --state 3`

The authority only queues a command for the named authenticated trainer when that trainer has acknowledged the exact active event-area identity and is currently reported inside that area. The owner-only endpoint rejects invalid state values, wrong identities, absent trainers and queue overflow. The recipient client checks the identity and sequence, defers state assignments while a script, battle, transition or movement is active, and drops a pending assignment on disconnect, replacement or departure. Later interactions use the assigned state; other trainers' states are unaffected. No inventory, saved progress, executable code or arbitrary engine memory is changed by this command.

`ok: true, queued: true` means only that the authority queued a command. The response includes a connection session and sequence. An owner agent can query `python -m world.agent_event_control --admin-socket /path/to/owner.sock --trainer TRAINER --area AREA_SHA256 --status SEQUENCE --session SESSION`. The status is `queued`, `applied`, `rejected` or `unknown`. Applied/rejected is a report from the authenticated game client, not independent proof. A command can remain queued or become unknown after departure, overflow, disconnect or retention eviction. The session disambiguates reused sequence numbers across reconnects. Keep the original response and do not automatically replay an uncertain command. State is temporary per-client state, not durable or synchronized. The feature is experimental, enabled only for CAVE9 event areas, and uses the existing owner-only admin boundary. Tests exercise the authority and actual native bridge in memory; no real socket session, live multiplayer session or third-party agent was exercised. Inspect exact-head CI for native build and offline playthrough status.


## Change a rule while playing

The same owner-agent command can add or replace a rule for one trainer's active instance:

`python -m world.agent_event_control --admin-socket /path/to/owner.sock --trainer TRAINER --area AREA_SHA256 --state 5 --npc 1 --next-state 6 --text "Hello, traveler!"`

The owner authority validates target, state, character and bounded literal text. The recipient independently validates the rule and applies it only when ordinary gameplay is ready. A matching (state, character) rule is replaced; otherwise a new rule is appended if the 24-rule limit has room. This patch affects only the named trainer and is held in a temporary runtime copy, separate from the authenticated published graph and its identity. It survives reconnect to that same area while the player remains inside, but resets on a new visit. It does not modify terrain, run scripts, grant items, write saves or affect other trainers. The immediate response still says only queued; query the returned session and sequence for the client-reported outcome. A full table, leaving or disconnect can prevent application. State and rule assignments share an eight-command FIFO; if it fills, later commands can be dropped and remain queued without an application acknowledgment. No actual socket or two-client session was tested.


The native client sends `APPLIED` only after its state or rule operation returns success, and `REJECTED` if native validation or capacity rejects it. The authority keeps at most 64 recent outcomes per connected trainer. A disconnected, replaced or evicted session reports unknown; a pending status is not proof of eventual delivery. Outcomes are client-reported, not tamper-proof receipts.

## RC6 integration

The combined RC6 candidate retains the RC5 party, chat, display and launcher-continuation fixes and enables the guide, cast and event gates alongside the existing co-op and extended-presence gates. The React local-host area picker exposes guided and cast outdoor generation. Graph publication and live director commands use the owner CLI above, rather than a separate director dashboard.

A focused disposable native journey exercised real owner and player sockets: compile/publish a graph, enter through WORLD, complete its first NPC transition, apply owner state 5, apply a replacement rule, interact again to reach state 9 instead of the original rule's state 6, and leave to the original field position. Both command queries returned applied, and native observations confirmed the changed state transitions. The seed and disposable save were unchanged. The combined WERROR Linux and React builds succeeded. This is one native client with an explicitly authored graph, not a model-generation, two-player, durable-progression or autonomous-GM acceptance claim.

## Paint a walkable tile while playing

An owner agent can change one named trainer's walkable generated-outdoor tile between normal grass and tall grass:

`python -m world.agent_event_control --admin-socket /path/to/owner.sock --trainer TRAINER --area AREA_SHA256 --x 5 --y 5 --terrain grass`

The other terrain value is `tall_grass`. The authority and recipient independently require a walkable tile in the exact active event area. Entrance, exit approach, exit, NPC and blocked tiles cannot be painted. Both supported tiles remain walkable, so this operation cannot create walls or change map connectivity. The engine updates that trainer's current in-memory map and redraws the visible tile; it does not alter the published map identity, another trainer's view or the save, and a new visit resets the change. Tall grass uses normal wild-encounter behavior. It relies on the existing battle engine, including the separate fix for entering a wild encounter without a usable Pokémon; do not treat this as fixing that crash.

This is a single-tile, per-trainer control primitive, not a globally synchronized tilemap editor, full terrain generation, collision editing or durable world change. It uses the same ordered bounded command queue and client-reported outcome status as event state/rule commands. No real two-client session, external agent call or actual local socket was exercised; inspect exact-head CI before integration.


## Paint a patch of walkable terrain

An owner agent can submit a JSON array of one to 64 tile edits using `--tiles-file patch.json` in place of `--x`, `--y` and `--terrain`. Every entry has exactly `x`, `y` and `terrain` (`grass` or `tall_grass`). For example: `[{"x": 5, "y": 5, "terrain": "grass"}, {"x": 6, "y": 5, "terrain": "tall_grass"}]`. The owner authority validates the entire patch, rejects duplicate or protected/unwalkable coordinates, and queues one bounded command for one trainer. The native client validates the entire patch again before changing any tile, so an invalid patch changes none; a valid patch updates the in-memory map and redraws tiles. One client-reported outcome covers the whole patch.

This is still per-trainer and ephemeral, with unchanged collision. It is not globally synchronized or persistent and does not create walls, buildings or new art. Tall grass relies on the normal encounter system, including the separate empty-party crash fix. No live two-client session, actual local socket or external agent was exercised.

## State-driven world opportunities (draft)

The opportunity director is a different narrative structure from a campaign
chain or an NPC chapter sequence. It selects authored scenes by current shared
place qualities and private participant qualities. A player's choice can make
another visitor's available stories change, while personal participation and
choices remain private. It does not award native money, create creatures,
change terrain, or physically open a ferry route.

Research inspiration: Failbetter describes quality-based narrative as short
interactive storylets whose availability depends on state that their choices
also change. The implementation here is original and uses no source content:
https://www.failbettergames.com/news/storynexus-developer-diary-2-fewer-spreadsheets-less-swearing
https://www.failbettergames.com/news/new-narrative-structures

The owner publishes an immutable pack through the existing owner-only admin
endpoint with `command: publish_opportunities` and `pack`. The example is
`examples/river_opportunities.json`. It binds scenes to PetalburgCity and gives
players a persistent flood-relief dilemma: slow repairs preserve nesting reeds;
fast drainage destroys them and exposes a restoration scene; two different
participants can complete relief; shared completion exposes a private welcome
only to contributors. The ferry is narrative state, not a new travel service.

Players already using native chat enter `/story` or `/story river` while ready
on that standard map. The authority replies privately with scene and choice
text plus exact `/story pick ...` lines. Eligibility is rechecked at choice
time against the authenticated player's fresh, validated field report. Location
is client-reported under the existing protocol, not a new anti-cheat guarantee.
Stale place revisions refuse rather than silently choose an altered outcome.
Exact request receipts replay without applying effects twice; conflicting
receipt reuse fails. Each scene is once per player or once for that place.

Pack qualities are bounded integers with `place` or `player` scope, explicit
initial values and maxima. Requirements are inclusive intervals; choices apply
bounded integer changes atomically with participation, shared revision, causal
history and receipt. No executable expressions or model callbacks run on player
input. An out-of-range effect makes that choice unavailable. Packs have bounded
size and immutable identities; different content requires a new pack identity.
Only shared quality deltas enter the place-consequence ledger, not private
player qualities. No story-player table enters the ordinary world inspection.

Tests exercise the real authority's authenticated native CHAT dispatch without
opening sockets: two-player relief, alternate consequences, private replies,
restart persistence, exact replay, stale location/state refusal and transaction
rollback. No live world or rendered native chat client was used. Campaign native
build/play acceptance remains separately blocked by missing build dependencies
and the environment's apt configuration read restriction.

Private-command compatibility boundary: `/story` now requires a client session
that negotiated the `COMMANDS1` HELLO suffix. Its complete snapshots carry the
non-chat `COMMANDS 1 MASK` record (story=1, mystery=2, guild=4). Old sessions
receive no new protocol record and cannot execute story commands. This requires
a paired client update before using the feature. User chat text never grants
capabilities. Reserved slash prefixes are intercepted case-insensitively after
leading spaces; unknown commands and commands addressed to another trainer are
refused privately rather than broadcast. This server change cannot protect an
old client connected to an old server: do not advertise private story commands
until the paired fail-closed client boundary is deployed. No actual disclosure
incident was observed; this corrects a statically reproduced fallback risk.
