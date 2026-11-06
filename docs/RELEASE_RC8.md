# Emerald World 0.2.0-rc.8 — Larger Worlds, Persistent Stories

RC8 builds on the integrated RC6 mainline. The failed RC4/RC7 full-Expansion attempts are not included. This remains the existing Emerald World game with its private trainer saves, native co-op, chat and ownership systems.

## Play from the launcher

Open an existing local expedition or create a new one. In its generated-area controls, **XL outdoor world (127 × 127)** authors a shared outdoor area using the existing model author. Review the theme and cost, then explicitly confirm. Selecting a saved area does not call a model. Generation is never retried automatically by the launcher.

Choose Play, then outdoors and on foot with a conscious non-Egg Pokémon, use **START → WORLD → Explore generated area**. Matching RC8 clients can enter the same XL terrain. Use **WORLD → Leave generated area** to return to your own original position; save normally afterward. Only one generated area is active; everyone must leave before replacement.

Shared XL terrain uses existing Hoenn art and ordinary wild encounters. It does **not** include the offline XL cast, story graph or mutable XL overlay extension from PR #212. Standard 63×63 interactive areas retain their distinct live-director features. The launcher describes these boundaries rather than offering an unsupported combined mode.

## Director tools: mutable shared terrain

The post-RC6 terrain stack is included: per-trainer ephemeral grass patches, durable shared overlays, connected geometry replacement/reset, observation and client-reported outcomes. The standard shared outdoor overlay supports up to 512 cells; a live walkable grass patch contains at most 64 cells. Collision-changing edits require the area to be empty, preserve connectivity and protect characters/entrance/exit. This is not unlimited world editing or new artwork.

Use `python3 -m world.shared_terrain_control --help` and `python3 -m world.agent_event_control --help` in a trusted extracted release. Owner sockets stay outside the native-game sandbox. A queued result is not an applied result; retain the returned command session/sequence and inspect its outcome. Offline games do not connect to this authority.

## Advanced offline XL stories

The separate offline authoring stack includes agent-authored characters, bounded interaction graphs, painted terrain, world-file reload on re-entry, a private story-progress journal with 64 slots, stable world identity and terrain revisions that preserve unchanged cast/story progress. It does not synchronize this progress between trainers, grant quest rewards or become a shared XL campaign.

These tools ship as Python modules, not an invented automatic director or a new launcher story editor:

1. `python3 -m world.author_cave --help` describes the XL painted-event output options. Calling the model author is explicit and can incur charges.
2. `python3 -m world.xl_versioned_world create painted.bin world.bin` validates and wraps a painted story with a stable identity.
3. Launch the packaged native executable offline using `--save /private/path/game.sav --generated-map /private/path/world.bin --generated-progress on`. Use a separate offline save, not the save of a running online trainer. The journal is adjacent to that save; it is separate from ordinary Pokémon saving.
4. `python3 -m world.xl_revision_author --help` describes opt-in model terrain revision. Replacement is atomic and becomes visible on next entry, not under the player's feet. Stable identity and unchanged story retain progress. Concurrent writers remain last-writer-wins.

Durable story storage is POSIX-only; Windows remains session-only in the imported implementation. This release publishes a Linux x86_64 player archive, not a newly verified Windows binary.

## Integration choices

- Preserved all RC5/RC6 co-op, sprite/object capacity, matched appearances, presence batching and launcher-continuation defaults instead of accepting older branch defaults.
- Combined the offline authored-world stack with the separately developed shared XL protocol without conflating their formats or ownership.
- Preserved the newer entry guard that refuses generated-area entry without a usable Pokémon; updated isolated older fixtures to provide its actual contract rather than deleting the guard.
- Added explicit launcher XL generation, saved-area format labeling and correct outdoor archive classification.
- Fixed the native shared-map coordinate validator to recognize XL format 10. Real two-client acceptance exposed the omission after isolated transfer/admission tests passed.
- `rc8-integrated-prs.json` records exact reviewed PR heads. PR #212 is deliberately deferred. The older #219–221 persistence designs are superseded/reconciled in the newer painted/versioned stack, not asserted as exact Git-ancestor merges.

## Verification and limits

The combined warnings-as-errors native build and production React build succeeded. Focused contracts, launcher actions, UI confirmation, native smoke and offline versioned-story gameplay are checked on the combined candidate. The offline journey uses controlled authored data and mocked model responses; it completes character interactions beyond the old boundary, preserves progress through a terrain revision and process restart, and verifies that trainer-save bytes are unchanged. It is not proof of live model quality.

See `rc8-verification.json` for final test totals, executable identity and the actual shared-client journey outcome. No full-campaign, WAN/load, expanded National Dex, Mega Evolution or new six-party medicine/trade certification is claimed. Existing unverified paths are not silently marked fixed by this release.

## Installation

Extract the Linux player archive, read INSTALL.txt, run its installer check, then install using the existing per-user release installer. Native libraries come from the distribution; the package does not bundle ROM build inputs, saves, credentials, dependencies or development evidence. Existing saves/worlds are never packaged or overwritten. The source-checkout desktop launcher is not automatically switched by publishing this release.
