# Product direction

Emerald World is a growing native-PC multiplayer Pokémon world, not a permanently stock-GBA ruleset or a finished product once the launcher works.

Vanilla remains the working default. Expanded rules/content are opt-in and must not silently replace the default campaign, roster or mechanics. Growing beyond vanilla is a product goal, not permission to stop maintaining it.

## Content and mechanics target

Classic ROM-hack capabilities belong in scope. Explicit priorities include Mega Evolution and a National Dex covering the current species roster, with the associated forms, species data/assets and supporting modern mechanics. The exact upstream revision/configuration and implemented coverage must be stated honestly; importing data is not proof every mechanic works.

Expansion should be treated as a potential coherent modern battle/data foundation, not merely a source of isolated small QoL snippets. Reuse whole feature domains where that avoids rebuilding the same capability. Stock Emerald species IDs, save layouts and protocol limits are migration constraints, not permanent content caps.

Balancing will be iterated through Ayaan's playtests. Do not withhold the expanded roster or modern mechanics until speculative balancing is complete, and do not repeatedly substitute balance/risk audits for implementation.

## Runtime and world growth

Increase native runtime sprite/entity capacity beyond GBA-era budgets. Keep runtime pools distinct from legacy saved-array layouts so existing player progress is not accidentally reinterpreted. Longer-term systems include AI-generated pixel art and tilemaps as real game content.

Preserve private trainer progress through explicit save/schema and multiplayer-version migration. No raw reinterpretation of older saves or unversioned struct payloads. Those compatibility tasks enable the expanded product; they are not arguments against building it.

## Development cadence

Build meaningful feature batches, integrate them, validate the combined candidate once, fix concrete blockers and release. Continue through the roadmap without requiring a user prompt at every checkpoint. Windows play remains friend-owned. Current rally/DexNav/repeat-Repel work continues; larger modern-engine/content work does not retroactively turn those branches into a wholesale rebase.
