# Agent-authored Hoenn fishing grounds

Agents can use `world.configure_fishing` to set rod-specific fishing populations on thirty existing Hoenn routes with native fishing tables. This is a reusable world-authoring action, not a prescribed fishing quest, new inventory, simulated fish stock or a claim that an NPC caught/released anything.

## Actual play

An author chooses a reviewed route, duration (up to 24 hours) and old/good/super rod slots. Players obtain and use their own rods in normal Hoenn. Native fishing availability, timing and water interaction remain unchanged. A matched client with a fresh complete snapshot passes the configured table through the existing native rod selector, level/ability rules, lure behavior, chain-fishing update, ordinary species shuffle and wild battle launch. Catching, ball use, party/PC handling and saving remain the normal native battle path. No Pokémon, rods, balls, levels or money are granted by the authority.

Special Route119 Feebas spot checks run first. A successful special Feebas roll bypasses the authored table. The normal table returns on configuration expiry/closure, disconnect, stale snapshot, incompatible client or map change. This does not rewrite saved personal encounter records, time-of-day configuration, geography or story. It does not enable fishing where the native map cannot fish. Species shuffling can change an authored species, and lures can change the base slot weighting; these existing mechanics deliberately remain active.

Players can inspect current grounds with `/guild fishing`, or rod slots with `/guild fishing Route102`. The author can compose public bulletins or character dialogue using existing tools; this feature does not invent sightings or broadcast automatic claims of ecology. There is no new native fishing information menu.

## Authoring and transport

`map` comes from `actor_runtime.fishing.maps`. `rods` is JSON with `old`, `good`, `super` lists of exactly 2, 3, 5 slots, each `[species, min_level, max_level]`. Enabled Expansion species only, levels 1–100. Base weights are 70/30, 60/20/20, 40/40/15/4/1, directly from the pinned engine fishing data. `minutes=0` closes the author's own active configuration. Active configurations are owned until expiry; another actor cannot overwrite them. Durable SQLite state and history describe configured populations, never observed catches or migration. Authors can revisit/renew using ordinary plans, not an implicit perpetual task.

FISHING1 is the outermost negotiated suffix and first compatibility fallback. A scoped WILD_FISHERY row is followed by all ten FISH_SLOT rows. Native staging rejects duplicates, invalid ranges and disabled species; the getter requires a whole admitted table and fresh map-matching snapshot. No partial table is used. Legacy clients receive no rows and keep original fishing.

## Verification and ancestry

App follows #366 5ca848f186fc56cd9469487a99fc1ff4fd860c79. Native draft #54 738c775502604fa2c68fa87aeaa0762c236a1fc2 follows #53, preserving its complete base tree. Builder, gitlink and candidate manifest match #54. Encounter-trait metadata is repinned because native species/evolution inputs are unchanged.

This is not based on released RC12 (app f484577b606348d07337387f14f75ab8cf4970b6, engine f7a813317d1b9fec803b48b682f5d74245c79037). Maya's integration/release and the unresolved outdoor-region publication are untouched.

The component fixture sends an actual authored authority snapshot into compiled current C parser/getter/rod-selector/fishing-dispatcher functions. Engine doubles stand in for mon creation, level resolution, RNG and battle launch; tests do not claim a live catch or rendered game. Tests cover all rods, special Feebas priority, ordinary fallback, missing/duplicate slots, disabled species, stale/disconnected/map guards, authenticated negotiation, ownership, restart and expiry. Full linked native validation, rendered fishing, catch/save/reload and multiplayer QA remain Maya's responsibility before release.
