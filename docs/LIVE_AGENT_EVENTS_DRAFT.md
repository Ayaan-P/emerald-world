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


## Private short-form campaign director

`world.campaigns` is a separate persistent director for scene, choice, recruit,
battle and ending stages. It does not alter the shared-world character framework.
An owner publishes an inert definition through `campaign_publish`; its content
hash freezes the version for every run. `examples/emerald_sprint_campaign.json`
illustrates thirteen gym/League battle stages with a branching ally choice and
an additional recruit. Its level-50 opponents are authored examples, not the
canonical Emerald trainer rosters or a measured few-hour playthrough.

Players use `world.client.CampaignClient` over the existing authenticated CONTROL
channel. `campaigns`, `start_campaign`, `campaign_runs`, `campaign_status` and
`campaign_action` expose only the caller's runs. Actions are `continue`, `choose`,
`recruit`, `squad`, `battle`, `finish` and `abandon`. Every mutation has a caller
request ID; existing runs additionally require the observed run revision.
Replaying an identical request returns its original receipt, not another recruit
or battle. Reusing an ID for different content and acting on stale revisions
are refused. A run can keep twelve named recruits and select one to three for
a battle. Declining a recruit is explicit. Scenes and choices run now through
this authority API, rather than existing only as a schema.

Battle requests freeze the selected squad and opponent in a durable ticket.
They **do not launch a battle**. The current response explicitly reports
`native_adapter: not_connected` and `battle_requested_not_started`. Only the
owner adapter endpoint `campaign_report` can report win, loss or abort. Player
controls cannot publish definitions or submit victories. Wins advance one stage;
loss and abort return to that battle for a fresh retry. Duplicate results are
idempotent, conflicting results fail, and unresolved battles block squad changes
or abandonment until an adapter abort resolves ownership. Pending tickets
survive restart. Reports remain owner-adapter reports, not independent proof.
No campaign actions, teams or decisions are put in public world history or the
agent inspection snapshot. This code never writes a native trainer save.

### Frontier reuse research and remaining native contract

The existing Expansion sources already contain the appropriate building blocks:

- `battle_factory.c` has initial rental selection, rental swaps and challenge
  save/pause functions. `BattleFactoryLobby/scripts.inc` backs up the party,
  explicitly saves, and enters the facility.
- `frontier_util.c` handles selected-party persistence and Battle Point awards.
  `BattleFrontier` in `global.h` owns challenge status, battle index, rental
  records, streaks and rewards in the trainer's save.
- The separate character-battle adapter builds the opponent but uses the real
  current player party. It does not supply a disposable campaign roster.

Primary source references: [rental facility implementation](https://github.com/rh-hideout/pokeemerald-expansion/blob/master/src/battle_factory.c)
and [Frontier utilities](https://github.com/rh-hideout/pokeemerald-expansion/blob/master/src/frontier_util.c).
The inspected local Expansion baseline's facility files were unmodified; no
integration checkout was edited. The design reuses the three-member rental
squad model and leaves native battle resolution, rental selection/swap UI and
party backup/restore to those existing engine facilities instead of inventing
another battle simulator. Calling the full Factory script unchanged would also
write Frontier status/rewards into the ordinary save, so it is not a safe adapter.

The remaining adapter must run in a dedicated private run profile, materialize
validated rental squads/opponents, preserve normal-profile ownership, exclude
ordinary Frontier BP/streak writes, and durably associate the native result with
the exact outstanding ticket across crash/reconnect. It must demonstrate entry,
loss, win, cancellation and exit restoration before the system is called a
playable native campaign. Recruitment currently changes the private director
roster only, not native Pokemon. No permadeath, moveset customization, native XP,
normal-save import, campaign UI or automatic battle launch is claimed.

Tests exercise the real authenticated control/admin dispatch through the entire
example graph, using explicitly simulated adapter reports for battles. They
cover per-player privacy, frozen definitions, recruitment/squad validation,
restart while pending, loss/abort/retry, duplicate/conflicting results, and
transaction rollback if a final receipt or result write fails. A sentinel normal
save stays unchanged. This proves director behavior, not actual engine battles.


### Per-run profile and handoff boundary

`world.campaign_profiles.campaign_profile` holds the existing world-lifetime and
profile locks around a distinct run directory. A frozen manifest binds that run
to its authenticated trainer, campaign definition and Expansion engine. One run
lock covers even callers supplying a different trainer name. Reusing a run with
another owner, definition or changed ticket is refused. An explicit starter save
can be copied once; no normal save is inferred, automatically imported or merged
back. Resume reuses only the campaign profile. The caller must retain this
context for the entire native process lifetime.

`adapter_command` probes `--campaign-protocol` through the existing network-isolated
sandbox and requires the exact `EW_CAMPAIGN 1` response before constructing a
campaign launch. There is no ordinary-game or unsandboxed fallback. The native
process receives only its run-profile writable mount, an immutable read-only
battle-ticket file, system runtime files and the selected binary. It receives no
world transport, admin socket, credentials or normal trainer profile mount.
The command uses `--campaign-ticket` and `--campaign-result`; current binaries
without those capabilities are refused. This module does not implement those
native flags or launch a campaign automatically.

The result reader accepts only a bounded private regular file matching the exact
ticket, a win/loss/abort outcome, and an explicit `party_restored: true` report.
It produces the owner-adapter report payload, never silently advances the run.
Wrong-ticket, missing-restore, symlink, shared-permission and malformed results
fail closed. Restoration is still a native adapter claim, not independent proof.

Further native inspection found `LoadPlayerParty` updates boxed HP/status fields
while restoring the party (`load_save.c:200-218` in the inspected RC10 family).
Therefore a byte-exact in-memory rental restore cannot simply assume that
`SavePlayerParty`/`LoadPlayerParty` are inverse byte copies. The adapter must use
a complete party/count snapshot for battle exit and keep its own run-profile
save lifecycle separate from ordinary trainer files. Native launch, rental swap
and crash recovery are still required before playable-campaign acceptance.

Profile tests use real files and locks, but mock the native capability probe.
They verify resume, concurrent-use refusal, owner/ticket conflicts, isolation of
normal saves, exact sandbox mount construction, unsupported-engine refusal and
result validation. They do not exercise a native battle or bypass sandbox limits.

Campaign experimental native launch: `world.campaign_profiles.run_battle` now
holds the existing per-run profile ownership through a foreground native
process, then returns a validated owner-report payload (it does not send it).
`experimental=True` explicitly accepts EW_CAMPAIGN_EXPERIMENTAL 1; defaults
still require the released protocol. The separate native campaign draft has
file ingestion, field callbacks and restored-result emission, but full build
and actual battle acceptance are not yet verified. An explicit compatible
field-ready seed and player title/load input are required. Closing/resetting
without a valid receipt leaves the ticket unresolved. Existing valid receipts
are recovered without launching the same battle again. No normal save is
copied implicitly or merged back. Tests mock process execution and do not claim
that the native game has been played.
