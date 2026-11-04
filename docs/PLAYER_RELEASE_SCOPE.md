# Player release scope

## Supported starting point

This release candidate is a Linux x86-64 native player client with a local browser launcher and a persistent hosted-world service. The browser is a launcher, not a replacement game engine. The game opens in a separate native window. Windows native play acceptance belongs to friends and must be recorded separately; Linux checks do not stand in for it.

Players can create a hosted world with private owner access, share a player invitation, rejoin saved connections, start an independent trainer and save normally. The service does not end when its owner leaves the game. Each trainer's local save is private and is not stored on the hosting service.

## Co-op contract

- Meet on the same map near one another, finish dialogue and close menus, then face the other trainer and choose **Tag up (first 3 mons)**. The other trainer must explicitly accept.
- `Nearby` is local game presence, not a global online-user count. `Busy` means the game is not ready for interaction; it does not mean simply tagged.
- Supported activities are two-person activities. Larger world populations do not mean a four-human battle.
- Shared encounters use each trainer's eligible first three Pokémon. Reserves remain private. Wild catches, balls, party and PC ownership remain private; a catch is not duplicated to both players.
- Continue through result, EXP, nickname and reward prompts on **both** clients. A player still reading results may be busy after the other has returned to the field. Save normally after both return.
- Ordinary trainer defeat credit is implemented, but not every story continuation is shared. Your own rival/story scripts may still need your own completion. This is a stock campaign with private story progression, not global mirroring of all flags.
- The co-op bag is restricted. Do not assume every stock item, Safari/special encounter or optional mechanic is supported.

## Disconnect and restart recovery

A world connection and a temporary battle/trade link are different channels. A normal battle can finish and close the link while private result prompts are still running. Do not reset solely because the temporary link is gone.

An actual interrupted battle or trade cannot be resumed from network messages. Keep the launcher available. Its explicit close/reconnect flow returns to the last ordinary save; unsaved progress may be lost. There is no promise of automatic rollback, a two-disk atomic transaction, or safe continuation at every possible interruption phase. Never overwrite a save with a forced battle state. A confirmed reset requirement is distinct from merely needing to advance normal reward prompts.

## Protecting progress

- Save in the native menu before closing or updating.
- Export trainer saves while the game is stopped. A save backup contains one trainer save, not the owner's account or the hosted service state.
- Back up the owner account separately; it is a private credential. Never send it as a friend invitation or publish it in a bug report.
- Hosted authority backup/restore is an operator operation, distinct from both player exports. The service must not be stopped under active players merely to demonstrate a backup.
- Updates must keep `~/.local/share/emerald-world/worlds` intact. Do not create a new world or overwrite another trainer's save to recover an existing adventure.

## Evidence and release gates

Observed before this release-readiness patch: four fresh Linux clients on an API-created WAN world completed ordinary opening progression, private saves/reloads, tags, and owner leave/return. A later human plus Hermes WAN session completed a shared wild battle and both returned to the overworld with Tag still active after reward prompts. That session revealed misleading completion status and short invitation timing; the release patches address those seams with focused regressions.

A disposable native-QA save was exported, imported into a fresh offline profile and compared byte-for-byte, retaining private backup permissions and leaving its source unchanged. This is a byte-level backup/import rehearsal, not a new native Continue acceptance.

The release notes must state the actual build/package/recovery checks performed on the final artifact. Earlier checks do not automatically prove later native changes. Remaining external acceptance: Windows friend play, broader campaign coverage and Internet/network interruption cases beyond the specifically recorded evidence.

## Not required for this release candidate

Additional regions, expanded species, an AI GM, in-browser rendering and unbounded player population are not included release promises. The browser-input backend remains an opt-in prototype, not accepted browser gameplay.
