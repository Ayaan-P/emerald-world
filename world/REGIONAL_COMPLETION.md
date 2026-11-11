# Experimental personal regional championships

Based on native #93 (34a83a9419f18d485ff1b57669ff159f2b927e0c), not Maya's
#72 or the RC12 release. Paired app enables EW_REGIONAL_COMPLETION=1 only with
explicit development/Kanto/regional-state/regional-badges options. Default off.
No server, shared-world progression or other player's save changes.

## Actual player interaction

WORLD > Regions > Personal championships (after separating badges).
Default focus is Back. Choose an attribution for the existing completion bit:
unassigned, Hoenn, Kanto or both. Regional choices only appear if the legacy
bit exists. A second screen describes consequences and again defaults to Cancel.
Back up + separate creates `<save>.pre-regional-completion` exclusively and
syncs the copy before applying the in-memory migration. It is the last disk
save, not unsaved current play. An existing backup is never overwritten.
Save normally to retain migration. Cancel does not change state. A failed or
interrupted backup never starts migration; an existing partial backup requires
operator inspection, not automatic overwrite. Rollback means restoring the
whole backup, including its older gameplay state, with the game closed.

Attribution is explicitly the player's declaration, not verified historical
proof. Unassigned legacy is retained immutably; it keeps game-wide compatibility
but grants neither region's story completion. Future genuine native championship
entrypoints record their own region. No location/trainer-flag inference.

## Progression and record scopes

- After migration FLAG_SYS_GAME_CLEAR queries Hoenn completion, regardless of
  the current map. Original Hoenn story, Match Call, rematch and Frontier-related
  checks retain their regional meaning. In this tree Vs. Seeker uses Hoenn
  milestone/rematch data; it remains Hoenn, not assumed to be a FireRed system.
- Ten existing FireRed map scripts explicitly use FLAG_KANTO_GAME_CLEAR,
  including Oak and League rematch/postgame scenes.
- PC Hall of Fame access, link compatibility, link contests and shared Easy Chat
  vocabulary use FLAG_ANY_GAME_CLEAR (legacy or either region).
- Virtual flags 0x3ff0/0x3ff1 are read-only dispatch IDs, not allocated save bytes.
  They are outside the Kanto 0x1000..0x1fff bank and below special flags. Their
  raw pointer is unavailable. Default builds alias both to the original flag.
- Native GameClear and EnterHallOfFame record Hoenn/Kanto respectively. The raw
  compatibility bit still records any completion; legacy attribution is retained
  in the extension. Generic flag writes cannot create or erase migrated wins.
- Both championship entrypoints attempt to load existing valid shared Hall of
  Fame records after migration, even with no legacy completion bit. Regional
  first-completion cannot erase the other region's records. Existing 50-team
  retention limit and corrupt-record behavior are unchanged. First-HOF time,
  ribbons, Pokédex and Hall of Fame record storage remain game-wide; this does
  not claim complete isolation of every game statistic.

## Persistence

One existing counter-bound payload, schema 0x4B4E5403: original 1024 Kanto bytes,
8 badge bytes, 4 completion bytes (version, legacy, attribution, later-win masks).
Requires explicit prior badge separation. Old schemas restore without automatic
migration. Invalid completion fields fail closed. New PENSAV4/version 4 envelope
prevents old or feature-disabled readers from overwriting the state. Mixed old
and new snapshots retain exact-counter fallback. No competing sidecar journal.

## Verification and limits

Nine focused native tests pass locally (including three existing badge-save
regressions). Compiled extracted flag dispatch covers default/experimental mode;
actual completion prefixes plus both unchanged native Hall of Fame append
functions preserve valid records in both championship orders. Synthetic storage
checks explicit choices, restart/profile isolation, corrupt payload refusal,
prior-counter fallback, failed file replacement, exclusive backup and old/disabled
reader refusal. Older-reader comparisons require their optional audit checkout;
portable tests still cover disabled-reader refusal without it.

Menu ordering/default focus and script scope are source checks, not a rendered
controller playtest. No full native binary link, real script VM, rendered Oak/
championship sequence, native flash-sector power-cut sweep or two-client QA.
No real save used. Host-file atomic replacement tests are not a claim that every
stock Hall of Fame/game-save sector interruption was verified. Remains default
off pending linked integration QA; do not merge as a fully verified campaign.

Paired native draft: https://github.com/Ayaan-P/pokeemerald-expansion-native/pull/94
Pinned head: 348e39b7047f1868b0126f494d4bea91e4e3e7bc
Build: `python scripts/build_expansion.py --development --regional-state --kanto-content --experimental-regional-badges --experimental-regional-completion`
Optional connected Kanto presence still requires `--experimental-combined-presence`.
