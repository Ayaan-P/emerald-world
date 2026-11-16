# Experimental Kanto Vs. Seeker

Based on native #96 (14f3ba17b8b19eabf841f7f2ed1789e17b657b93), not Maya #72 or RC12. Default EW_KANTO_REMATCHES=0. Requires compiled regional completion and custody readers; custody itself need not be enabled. Do not release until linked gameplay QA.

The Vermilion Pokémon Center Vs. Seeker giver offers a personal enable confirmation on a repeat conversation, after explicit regional completion migration. An exclusive .pre-kanto-rematches backup preserves the last disk save, not unsaved progress. Existing backups refuse replacement. Normal SAVE is required to retain the upgrade.

The existing item animation and nearby trainer scan feed separate typed readiness. Frozen full tagged trainer IDs use 221 explicit FireRed rows verified against pret/pokefirered ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/vs_seeker.c. Existing target trainer teams are used, with skipped stages and personal defeat history. Milestones: item receipt, Celadon, Fuchsia, separated Kanto championship and completed Celio Network Machine. Target FLAG_IS_CHAMPION is the last milestone's name, not the Hall of Fame bit. Scan response policy remains Expansion's deterministic eligible response, not FireRed's random refusal odds.

Recharge and readiness last 100 steps; changing maps clears readiness while retaining charge. Scan writes no Hoenn readiness/counter. Ordinary stock trainer scripts, rematch dispatch and battle-end cleanup use the frozen offer. There are no shared-world victories, rewards or cross-player save changes.

Combined schema 0x4B4E5405 appends rematches to flags/vars/badges/completion/optional custody. PENSAV6 refuses downgrade. Counter recovery retains prior snapshots. No SaveBlock layout edits. Whole-file rollback restores the whole personal history; this is not a uniqueness or anti-cheat system.

Verification: 18 host tests cover native selection/enable helpers, source routing, synthetic counter/map/expiry state, custody retention, fresh-process file load, failed atomic replacement and exact prior-reader refusal; previous regression tests included. The separately retained policy comparison covers 452,608 combinations against pinned FireRed functions. No real saves were used.

Limitations: no full native link or rendered/controller gameplay QA; a syntax-check attempt using the older local full checkout stopped at missing generated map_groups.h and is not a compile pass. No exhaustive flash byte-failure sweep or multiplayer session test. Before release, test item cancellation, nearby/hidden/maximum trainer scans, every regional rematch script kind, stage selection, wins/losses/doubles, expired movement restoration, map changes, save/restart and both region transitions in the exact linked cohort. Keep disabled meanwhile.

Follow-up correction restores the unchanged Hoenn charging expression and adds a compile/run regression for that production function. Native pin: a35c854620c97acc66ddfc49091252baba948389.
