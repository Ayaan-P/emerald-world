# Persistent Secret Base neighborhood (experimental)

A separate draft on app #401 / native #63, not RC12. Frozen #384/#56 untouched.
Reuses the existing own-base exporter and recipient importer; no bridge/activity edits.
The unchanged importer is still gated by `--development --experimental-secret-bases`.
Linked native save/visit/battle QA remains pending. Do not enable for release yet.

## Player journey

1. Establish your own Secret Base through normal Hoenn gameplay. In ordinary field
   play outside a base, `/neighborhood` discloses the public snapshot contents.
2. `/neighborhood publish yes` sends your game trainer name/ID, location,
   decorations/positions and recorded current non-egg party to ALL world players
   and agents. This is a one-time snapshot, not automatic tracking. The directory
   persists after logout/restart; one entry per authenticated trainer/save lineage.
3. A visitor uses `/guild bases page 0` (three entries/page), which gives actual
   stock route/tile coordinates and exact `/neighborhood get ID REVISION` commands.
   Coordinates derive from 75 pinned native map bg_events, with source blob hashes.
4. Downloading does not change a save. `/neighborhood status` explains
   `/neighborhood install yes`: explicit acceptance installs into the CURRENT
   personal save in memory. Use ordinary Save to persist. Downloads expire after
   3,600 native pumps and clear on disconnect/stop. Never an automatic import.
5. Travel normally to the listed route/entrance. Leave/re-enter the route if it
   was already loaded so native entrance metatiles refresh. Stock Secret Base
   interiors, decorations and recorded-owner party battles remain native, including
   their normal prerequisites/daily restrictions. No teleport, generated NPC
   ownership, shared victory or visit receipt is inferred.
6. `/neighborhood remove yes` withdraws the CURRENT save's listing. Existing
   downloaded/imported copies cannot be retracted. `/neighborhood stop` only clears
   the local request/download, not a publication already received by the server.

## Boundaries and recovery

- Requests are one-shot, sequence-bound on authenticated native link channel B.
  No automatic publication retries. Timeout/disconnect is an unknown outcome;
  inspect directory before trying again. Stale replies cannot trigger an import.
- Exact snapshot revision required on download, so updating/revoking a listing
  invalidates previously copied directory commands. A download already received
  is retained briefly for explicit confirmation, not remotely revocable.
- Original importer refuses own-owner import, occupied locations belonging to
  another owner, duplicate owner conflicts, full save slots, bad format/species/
  moves/items, and importing while inside a Secret Base. Existing same-owner
  registration, daily battle and visit counters survive updates.
- Does not overwrite the player's own base, remove occupied slots, save to disk,
  rewrite parties, transfer Pokemon, or grant rewards. Imports are native recorded
  party representations, not full individual Pokemon identities.
- Published snapshots are owner-submitted client data, not authority-verified
  achievements, legitimate catches, or guaranteed unmodified teams. Engine validates
  before admission. No raw payload or private save lineage is inserted into public
  world history or the default agent context; the public directory exposes owner,
  route/tile, identity and revision only. Directory has 256 active entries, removal
  frees capacity. Native personal slot limit remains unchanged.
- Agents may inspect the directory to use real public locations, but cannot publish
  on behalf of players or silently import into their saves.

## Verification

64 app tests: 62 passed, two existing provider sandbox skips. Two new compiled
native protocol/component tests passed; two existing compiled importer tests passed
against the exact unchanged parent source. These are component checks, not a full
linked build, rendered playtest, two-client session, disk-save/reload or native
battle verification. No live provider calls. Integration/QA/release remains Maya's.
