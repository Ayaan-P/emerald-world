# Optional Battle Tower record exchange

This is asynchronous stock record-mixing gameplay, not a live remote trainer or a new
battle simulator. An owner voluntarily publishes the actual `frontier.towerPlayer`
record saved by the native Battle Tower. A second player downloads an exact revision
and explicitly installs it into a completely empty personal Tower record slot.
The stock `ChooseSpecialBattleTowerTrainer` and Multi Battle partner selection then
apply their existing streak, level-mode, team-size and species rules. Appearance is
not guaranteed on the next admission. No victory or growth is inferred by the server.

## Player journey

Build with `scripts/build_expansion.py --development --experimental-tower-records`.
The feature is disabled by default until linked/save/appearance QA.

1. Play the normal Battle Tower sufficiently for its own save routine to produce a
   valid English record with a nonzero streak and at least two recorded Pokemon.
   This feature does not manufacture a record or bypass admission/progression.
2. In an ordinary public Hoenn town/route, `/towerrecord` explains publication.
   `/towerrecord publish yes` shares game trainer name/ID, reported streak, class,
   level mode, recorded species, moves, held items, EVs/IVs, OT IDs, personality,
   friendship and PP bonuses with all authenticated world players. No player bag,
   full save, other trainers' imported records, nicknames or easy-chat phrases.
3. A recipient uses `/guild tower page 0`, then the displayed `/towerrecord get ID
   REVISION`. `/towerrecord status` distinguishes pending/downloaded/acknowledged.
   Downloading does not alter a save.
4. `/towerrecord install yes` explicitly targets the currently loaded save, outside
   facilities/battle. It fills only an all-zero record slot; identical records are
   a no-op, conflicting owner records and full capacity refuse without replacement.
   The recipient uses normal Save to persist. Native Tower scripts and rewards remain
   unchanged, and the player's own party is never replaced.
5. `/towerrecord remove yes` withdraws this authenticated owner's active-save-lineage
   listing. It cannot retract already downloaded/imported copies. `/towerrecord stop`
   clears local pending/downloaded data only. Disconnect and timeout also clear it.

## Boundaries

Fixed little-endian version-1 transport is 149 bytes, not raw native memory/padding.
Native import validates bounded species/moves/items/class/level/EVs, safe trainer-name
characters, nonempty team and canonical encoding, then calculates the engine's own
record checksum. Imported nicknames use native species names and phrases are blank.
Unsupported name characters/non-English source records refuse rather than corrupt text.
A checksummed source is still a client report, not anti-cheat proof of achievement.

The separate `TR` channel does not intercept existing `T` trade traffic. Requests are
sequence-bound, one-shot, no automatic retry, with a 3,600-pump timeout. Publication is
one current snapshot per authenticated trainer/save lineage, with a 256-listing bound;
withdrawal frees directory capacity. It does not consume player items, grant Pokemon,
replace occupied slots, force an autosave or create a new save structure. In-memory
imports have ordinary native Save/crash semantics, not a claimed disk transaction.

## Source, ancestry and QA

Separate draft on app #404 c974b057fd936605b64cc8be9f4a4ac72d49bf4e and native #66
783746b54dd3ccfe50943c116a3e43240f7c6eaf. Not RC12-based; frozen #384/#56 and Maya's
integration are untouched. Existing native Tower/partner code and declarations were
blob-checked against the source manifest and are unchanged by subsequent parents.
No denied files or uncertain publications are retried.

76 selected app tests: 74 pass, two existing provider-sandbox skips. Native tests compile
actual command/codec/import sources with engine fixtures: explicit import, sequence,
timeout/reset, disabled gate, checksum/encoding rejection, own-ID refusal, occupied
slot preservation, duplicates/conflicts, species/individual fields and public-field
checks. These are component tests, not a linked build or rendered playtest. Full native
save/reload and actual opponent/Multi partner appearances remain integration QA. No
live provider calls or donor assets.
