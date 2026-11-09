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

Paired native draft: #31 at fb23bcd7e9311f873e9048db3b3391f9e1647177. App builder, gitlink and candidate manifest are pinned together. No dependency on #287-297 or native #27-30.
