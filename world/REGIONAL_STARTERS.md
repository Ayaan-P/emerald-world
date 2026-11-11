# Experimental regional starter choice

Independent native stack on #97 a35c854620c97acc66ddfc49091252baba948389, not RC12 or Maya #72. EW_REGIONAL_STARTERS defaults off. The experimental cohort requires all existing regional payload readers compiled, but does not require their gameplay/migrations to be enabled first.

Source-confirmed problem: Oak's choice and 30 Kanto rival branches used Hoenn's VAR_STARTER_MON (0x4023). This feature uses the already-reserved KANTO_SCENE_VAR(0x4031) with a tagged 0..2 Kanto choice. It does not allocate a new save field or overwrite Hoenn's variable.

New Oak choices require explicit local upgrade confirmation before the ball is removed, flags change or the Pokémon is given. Failure/cancel leaves that sequence untouched. The exclusive .pre-regional-starters backup contains the last disk save, not unsaved progress. Native choice and ordinary party/script progression remain unsaved until the normal SAVE operation. The existing givemon delivery rules are unchanged.

Legacy saves retain the old shared-variable behavior until explicitly migrated. Oak's first aide offers an opt-in after the starter scene, followed by Bulbasaur/Squirtle/Charmander confirmations; declining all leaves state unchanged. Attribution is the player's declaration, not inferred history. It gives no Pokémon, does not repair an already-overwritten Hoenn choice, and cannot be reassigned by repeating the flow. No retroactive guessing from party contents or rival flags.

All thirty Kanto rival branches invoke a native comparison which preserves VAR_RESULT and caller temporary variables. Stock branch labels, battle parties, scripts and outcomes remain native-owned. Default-off preprocessing retains original scripts.

Schema 0x4B4E5406 wraps the exact prior regional schema and payload together under PENSAV7. It supports ordinary regional state and all existing badge/completion/custody/rematch combinations, retaining counter-based fallback snapshots. An old or feature-disabled reader refuses the new envelope. Whole-file rollback restores the whole personal history; no cross-player state changes or uniqueness claims.

Verification: 21 native host tests (including existing regression suite), actual callback tests for all nine Hoenn/Kanto choices, all thirty branch source checks, failed exclusive backup/atomic replacement, fresh-process reload, previous-counter recovery, coexistence with custody/rematches and exact prior-reader downgrade refusal. Synthetic fixtures only, no real saves.

Not verified: full linked native build, rendered confirmation/monpic flow, script VM/controller playthrough, exhaustive flash-write interruptions or linked multiplayer sessions. The helper tests stub script operand reading; source checks do not execute the entire story VM. Keep disabled pending those checks. No full Kanto campaign claim.

## Existing-party delivery correction

Native #99 requires room in the party before Oak records a new choice, removes its ball, or advances gift flags in combined-region builds. Full parties may make room and retry. Naming uses the existing gift-recipient helper instead of assuming slot zero, preserving an arriving Hoenn party's lead. This correction also applies with the isolated-starter option off when combined Kanto content is built; it does not change standalone FRLG or Hoenn behavior, schemas, or migration decisions.

Native pin: `19ce99fe5a097b085e752e7ab1bed267f1cb6931`, stacked on #98. 23 native host tests pass, including the production gift function with synthetic compact parties of sizes zero through six. Full script VM, rendered/controller nickname and cancel/retry QA, and full native linking remain unverified. No real saves were used.
