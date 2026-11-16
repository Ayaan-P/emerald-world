# Private NPC partner execution boundary

This slice provides a private participant context and action boundary, not a new public actor capability or an automatically running model. Public actor plans, reasons, receipts and general inspection must never receive a private clue. A private solver cannot call general world tools or place private text into public actions.

## Player-visible path

An ordinary two-role mystery can use a generated world NPC as its second participant if that NPC already occupies the exact second station on a normal map. `/mystery npc` explains the scope. The initiating player uses `/mystery npc ACTOR` to reserve the role, reads their own clue normally, and uses `/mystery npc-send FICTIONAL MESSAGE` to explicitly share only that message with the private NPC solver. Reserving a role is not agent acceptance; the solver can wait or leave.

The NPC's own clue is read through the existing mystery command only when the authoritative actor is actually at its station. The initiating player must also be freshly present to claim or apply a turn. No NPC movement, canonical original-object relocation, player warp, save write, inventory or reward is added. Generated-region aliases are excluded because this mystery engine does not carry exact region revisions. A later stage at another location waits for actual supported movement; no travel is invented.

`/mystery npc-status` privately shows the latest solver outcome, including after completion. `/mystery leave` cancels and erases the pending private message/lease/fingerprint/result. Existing ordinary two-player mysteries retain their behavior. Puzzle completion still uses the real existing answer, clue-read and station checks and its normal private completion record; it is not Pokémon training or a native battle result.

## Scoped private host seam

Trusted local administration may use:

- `private_mystery_claim` with exact `actor` and `run`.
- `private_mystery_finish` with exact `actor`, returned `lease` and `decision`.

The claim returns only that actor's public name/role, the current stage and puzzle title, its own station clue, the initiating player's explicitly sent message, and a fixed output contract. It excludes trainer/run/save identity, the other clue, the solution, other actors' private context, public author source and general world inspection. Local host storage/administration remains trusted and can access private records, as with existing private game state.

The decision has exactly `action` and `answer`: `wait` or `leave` with an empty answer, or `solve` with a bounded uppercase answer. No arbitrary text, dialogue, code, tool calls, public state or general agent plans can be returned. The existing mystery executor applies the action. A guessed incorrect answer does not complete anything. Provider output is not trusted as a success report.

`process_one(server, actor, run, responder)` demonstrates a trusted adapter with a supplied isolated responder. It passes only the scoped context and never starts a provider itself. Exceptions are sanitized, the claimed turn stays unresolved, and no retry occurs. No configured Claude/OpenAI/general-author integration, launcher worker or live model session is enabled by this PR. A production private provider worker still needs a separately reviewed explicit configuration, appropriate disclosure/authorization, finite cost limits and lifecycle wiring; existing private-reflection grants do not silently cover it. Do not feed this packet to the general public author pipeline.

Each player message permits one claim. An interrupted claimed turn cannot be reclaimed automatically, including after restart. A stale character version, position, player presence, cancelled run or used lease prevents application. Existing action and the private result commit together. Player cancellation clears the outstanding data; no private output is exported to public history, ordinary actor inspection or unrelated providers. This does not retroactively make already-public authored puzzle content secret.

## Verification and limits

Component tests exercise actual authenticated CHAT commands, actual NPC position, private claim/finish admin routes, a fake scoped responder completing a real mystery, private status delivery, no unrelated-player response, no public-history/general-inspection leakage, wrong-actor rejection, unsupported action rejection, no lease replay, stale/cancelled turns, restart and transaction rollback. No canonical travel, rendered session, native full-game or live-model behavior is claimed.

Based on draft #382 `cf58fb463328ca1932dc2c2b52aa66a520681a2f`, retaining native #55 `babbe0e3272120523d509cecf22705f158429586`. Not based on released RC12. Maya owns integration/QA/release; no integration or release branch changes. Denied uploads and the separate unpublished provider-budget work remain untouched; no live provider sessions. The old spectating stream remains app-disabled.
