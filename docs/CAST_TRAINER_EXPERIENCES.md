# Actual trainer results informing the living cast

Independent follow-on to app #286 / native #26. This is a generic ordinary-battle observation adapter, not a rematch variant or a fixed character arc. The reviewed native callbacks for trainer and rematch battles capture the actual opponent preset and win/loss before the original return/whiteout logic runs. A generated catalogue covers 805 named presets from the exact Expansion trainers.party; stable semantic keys avoid numeric-ID drift.

## Player journey

1. Play an ordinary single trainer fight normally, including a loss. No battle mechanics, party, EXP, money, items, flags or original scripts change.
2. Once back in the field, `/history battle` previews the last eligible result, opponent name and original map number. `/history battle confirm` shares that one anonymous result with world agents. Cancel leaves it local. Existing campaign milestone opt-in does **not** automatically share battles.
3. The real public event reaches cast agents interested in that map. Wally and Steven also recognize their own exact original preset family. The author may revise goals or relationships, execute an existing supported project action, change a supported opportunity, or do nothing. No fixed response is shipped.
4. Actual authored actions use the existing authority compiler, evidence and action receipts. The regression follows a real native loss packet through production dispatch, then a deterministic author fixture changes an actual player-visible shared project opportunity without a player chore.

The model still decides what the event means. A report is a native **client attestation**, not anti-cheat proof, a permanent trainer victory, evidence of personal attributes, or earned NPC Pokémon growth. Repeated defeats are not automatically a relationship score. No party, player name, save ID, private chat or dialogue is published. Public history remains shared even when another save is loaded; no personal progression is copied.

## Ownership and compatibility

Only an ordinary single trainer battle is captured. Debug, link, cooperative, double/partner and nonstandard battle types are excluded. Wild/facility/custom battle paths are not added. Unsupported named presets are omitted rather than guessed. Only the latest eligible result is retained in volatile local memory. Disconnect, new game or lineage change discards it. A replaced or invalidated capture cancels its old preview. Results are not automatically recovered from flags after restart.

A report requires negotiated CORE, current authenticated save and fresh ready field state. Capture location is retained because a loss can return to another Pokémon Center. Server-side receipt keys are connection-session/save/result-specific and reject changed duplicate payloads. No arbitrary prose is accepted. Old servers refuse BATTLE; there is no public-chat fallback or automatic retry. The client says 'requested', not 'delivered'; uncertain delivery requires inspecting history, not resending a saved packet.

## Pairing and checks

The app's catalogue must match the paired engine trainers.party checksum. Regenerate/check with `python3 tools/cast/trainer_experience_catalog.py --check --app-catalog /path/to/app/world/trainer_experience_catalog.json` in the engine. Both sides use semantic preset identifiers, not numeric trainer constants. If trainer names or source definitions change, update both catalogues.

Tests compile the actual native collector and command code with explicit engine doubles; the authority test dispatches its emitted packet through the production server. These are component tests, not a linked build, rendered battle, real network session, or live-model quality check. Maya must verify ordinary victory and whiteout callbacks, save switching, chat-command display, original story continuity, and real provider behavior on the exact paired build. No merge or release is included.

Paired native draft: #31 at 27672498fcec76574776299af8b9bfb27d0cc768. App builder, gitlink and candidate manifest are pinned together. No dependency on #287-297 or native #27-30.

## Future-results participation

`/history battle on` now previews one standing permission: anonymously share future ordinary trainer wins/losses, opponent preset and original map with world agents for **this trainer and save in this world**. `/history battle confirm` saves that setting. `/history battle status` shows the acknowledged mode; `/history battle off` stops new local automatic sends immediately and requests durable revocation. If saving OFF is blocked by an outstanding request, the UI explicitly asks to retry before reconnecting. A late ON acknowledgement cannot masquerade as saved OFF.

Once acknowledged ON, subsequent eligible battle results flow automatically at safe field idle. No per-battle confirmation or player errand is needed. Original battles still run unchanged. Normal private saves, other trainers and the existing badge-sharing setting remain independent. The host cannot opt players in through this interface. New sessions read the persisted setting using a nonce-bound CORE response; older servers refuse it and no auto sharing starts. Enabling never backfills a pre-existing local result. OFF does not erase already published world history.

This uses one volatile pending result, not a durable replay queue: a newer battle can replace an unsent result, disconnect discards it, and uncertain sends are not automatically retried. A capture made before the saved mode is acknowledged is never automatically backfilled. This favors honest current-session behavior over fabricated catch-up. The existing explicit one-result sharing path remains available when automatic participation is off.

Tests cover mode acknowledgement, automatic send, immediate stop, reconnect, same trainer saves A/B, another trainer, restart and durable revocation. Public results retain their client-attestation boundary and can drive the existing real actor-action pipeline; no scripted reaction or live-model outcome is claimed.
