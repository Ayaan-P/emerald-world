# Birch and voluntary public field research

This connects original Hoenn exploration to a recurring original character and existing world actions. It does not install a fixed research quest or automatically spawn a particular outbreak.

1. A player can use the existing native `/research` command to review the audience, then `/research publish yes` to publish the current personal seen/caught Pokédex snapshot to all world players and configured agents. This includes older entries, is permanent, and is anonymous: no trainer, save lineage, location, party or individual Pokémon is published. Unshared flags stay private. `/research status` checks the receipt; `/guild research` reads the aggregate.
2. The reconciled app now actually accepts that native sender's authenticated D protocol. The parent app lacked its handler/module even though the native sender was present. It requires fresh ready field presence and no active link activity. Already-known flags create no new event. Publication and aggregate delta commit together.
3. Host-enrolled Professor Birch can independently respond to that exact public event through the existing bounded character author queue. His seed describes a researcher, not a mandatory story arc. Reports are client attestations, not verified sightings, current ownership, locations, player identity or Birch having witnessed an event.
4. Birch can use the existing actor capabilities to choose a real supported opportunity, for example a temporary original-route encounter configuration, or choose to wait. That operation retains its normal validation and committed receipt. An authored population is a world change, not a discovered natural migration or a guaranteed encounter/catch. No model/provider was run in testing and no automatic example population is installed.
5. Return to Birch's actual lab. After his **complete original Pokédex rating**, or after declining that rating, the existing native cast conversation can show his current authored response and existing conversational options. His ordinary rating/registration, starter gifts, National Dex and Johto-starter scenes remain original. The supplemental hook only admits the lab and a save that has actually received his Pokédex. It does not grant flags, items, rewards or another player's progress.

## Boundaries and usability

The sharing UI is the existing in-game research chat command, not a new lab upload button. Merely speaking to Birch never publishes a Pokédex. The public aggregate remains after disconnect or stopping a pending sender. Research reports do not identify their contributor and cannot support personal friendship credit. Existing private memory controls retain their own semantics.

Birch joins the existing canonical registry rather than spawning a second NPC. Host initialization/follow enrollment and configured author service are required; no provider starts automatically. Existing enrollment cursors are not rewound. The eight-followed-character bound remains; a full host roster may need an explicit slot change before adding Birch. He does not gain incoming/outgoing Match Calls, companion battles or an invented team. Existing optional native tutoring can be authored at his local appearance with the same frozen offer and per-player party selection, but no tutor is installed by default.

The existing native outbreak path and its personal-outbreak precedence remain unchanged. Different saves may see different encounters for legitimate native reasons. No claim of shared catch ownership, native migration simulation, natural ecology or complete rendered loop.

## Build, ancestry and verification

Separate stack on app #486/native #124. Native lab hook defaults off with `EW_BIRCH_RESEARCH=0`; enable with `--development --experimental-birch-research`. Shared-report ingestion still requires the existing explicit one-shot command. Maya's #410/#72 and all held operations remain untouched.

Six focused tests pass: real public snapshot ingestion, anonymous event/dedup, fresh/busy/malformed rejection, SQLite restart, strict Birch-only research evidence, actual original-route outbreak configuration and existing native wire output after a deterministic author choice, and source/preprocessor checks that the default-off Birch script is unchanged and on-mode calls follow original rating/decline. These are component tests, not a full actor-model or graphical playtest.

Full native syntax/link is not verified: the recovered headers lack the pre-existing generated `gSpecialVar_ItemId` declaration used by this file's tutor code. Full exact-head build, script linking, rendered lab conversations, native encounters, two-client play and save/reload QA remain outstanding. No real saves or live providers were used. Maya owns integration and release.

Paired native #125: https://github.com/Ayaan-P/pokeemerald-expansion-native/pull/125 at `286f62c04d1fe736a2d7d1f76b198c40c7525053`. Focused test command with this submodule checked out: `python3 -m unittest discover -s test -p test_birch_research.py -v`.
