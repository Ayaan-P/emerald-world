# Experimental Route 5 custody

Separate stack on native #95 c9af08f3ec11930b9617d4a40fdf1df5ad910ef8, not Maya #72 or RC12. Default EW_ROUTE5_CUSTODY=0. Requires EW_REGIONAL_COMPLETION and its combined native prerequisites. Not release-ready before linked and controller QA.

## Player flow

The existing Route 5 Day Care NPC becomes a guarded service in the combined build. Disabled/unmigrated cohorts show an unavailable message instead of falsely accepting custody. After completing personal badge/championship setup, the player explicitly opts in. An exclusive `.pre-route5-custody` backup preserves the last on-disk save, not current unsaved play. Existing or failed backup blocks activation and requires operator review, never overwrites it. Normal native SAVE is still required to persist activation and transactions.

The player selects an owned non-egg Pokémon and must retain another usable Pokémon. Native deposit preserves the full BoxPokemon, mail, form handling and steps. Hoenn's two-mon breeding daycare is untouched. Existing native daycare experience/move-learning and withdrawal helpers are reused. Withdrawal rechecks occupied custody, party capacity and current native fee, then returns the Pokémon and subtracts payment in one synchronous call. Failure restores party, mail and money; scripts announce success only after success. No shared-world Pokémon, automatic saving/sharing or world ownership is introduced.

## Persistence and rollback

Custody joins the existing regional state in schema 0x4B4E5404, not a competing extension capture. PENSAV5/version5 wraps the combined flash image and extension. Disabled and old readers refuse load/store. The record is bounded, versioned, zero-tail validated and size-checked; it remains versioned even when empty. Existing badge/championship data and older exact-counter fallback snapshots are retained. Profile switches/new games clear working custody. Native saveblock layout is unchanged.

A native SAVE persists the party/mail/money state and custody under its selected counter. Unsaved changes roll back together on restart; this does not promise immediate durability. Whole-file copied-save/rollback restores that trainer's entire personal history. No external ownership ledger or rewards exist, so this is not a solution for world-owned capture uniqueness. Backups are rollback copies, not an authorization to load them concurrently as independent world individuals.

## Validation and limits

Four new tests: (1) actual HandleWriteSector, HandleReplaceSector, signature commit and GetSaveValidStatus with synthetic flash, testing 672 deposit/withdrawal sector/signature-boundary cuts across all rotations and full/same-counter replacements; (2) actual new transaction wrappers with synthetic Pokémon primitive mocks for admission, rollback, mail and payment; (3) fresh-process disk restart, exclusive backup, failed atomic replacement, typed record size mismatch, profile isolation and both disabled/current and exact #94 reader refusal; (4) script success/payment source checks. Existing nine badge/completion tests remain applicable.

These are NOT a full native link or playthrough. Sector tests use reduced synthetic sectors/checksums and boundary cuts, not every byte-program failure, actual engine party structs or controller scripts. Transaction tests mock native Pokémon growth/form/mail primitives; those original implementations are unchanged. UI rendering, real DaycareMon ABI/capacity, level/move learning, mail exhaustion, repeated controller cancellation, incremental save variants, byte-level power failures, filesystem directory-sync uncertainty and complete end-to-end game recovery remain linked QA requirements. No real player save was read or modified. Keep this feature experimental and off by default.

App parent #447 513f7d35515c96306dc43f07e4b110aa1089ea64; native pin 14f3ba17b8b19eabf841f7f2ed1789e17b657b93. Build opt-in --experimental-route5-custody requires --experimental-regional-completion and all its development/combined-region prerequisites. Defaults stay off.
