# RC7 integration checkpoint — unfinished

## What this repository builds

The pinned Expansion native engine combined with RC7's world authority/client,
native peer activities, generated-area integration and independent private saves.
This is NOT a finished multiplayer release. No newer Dot branch is merged.

## Source checkpoint

- App branch: `integrate/rc7`; the app checkpoint is the commit containing this ledger.
- Engine branch: `integrate/rc7-world`.
- Engine checkpoint: `4ae9756faf18a9540758a95b8cec72bc7c808ceb`.
- Canonical build 19 and mandatory build checks passed before this checkpoint.
- Build-19 executable SHA-256: `fef6228ce3c6af8d23697a92b8b255cc6bc38144f4a60ddc28dac43c9b07a73e`.
- Build log: `/home/ayaan/projects/emerald-world-research/rc7-rescue/integrated-rebuild-19.log`.
- Earlier gameplay runs below were built from then-uncommitted working trees.
  Their binary hashes identify the tested artifacts, NOT exact historical source
  commits. This checkpoint does not retroactively repair that provenance gap.

## Observed gameplay, with exact boundaries

### Ordinary native single battle — build 16: PASS

- Report: `/home/ayaan/projects/emerald-world-research/rc7-rescue/single-build16/acceptance.json`.
- Executable: `ea9f37affc08f6124f4076a73d30d7609e2507b8ad34df03f454173636adf0d1`.
- Two actual native clients connected, moved, rendered one another, used peer
  menus and bilateral consent, entered an ordinary battle and returned with
  controls unlocked.
- Does NOT verify co-op, capture, private rewards or build-19 gameplay.

### Independent saves and cold Continue — build 18: PASS

- Report: `/home/ayaan/projects/emerald-world-research/rc7-rescue/save-build18/acceptance.json`.
- Executable: `f0a891dea01d63a39242fff82597cf0c060e514e7df45568ca0df427b8285732`.
- Each normal in-game save wrote only its own separate private file.
- Both clients cold-Continued at their own distinct locations with matching
  party counts.
- The probe needed neutral-frame waits after save completion. Earlier probe
  failures do not establish a production save defect.
- Does NOT verify persistence of co-op rewards or every party field.

### Actual tagged grass co-op — build 18: FAIL

- Report: `/home/ayaan/projects/emerald-world-research/rc7-rescue/coop-build18/acceptance.json`.
- Same build-18 executable hash as above.
- Actual tag invitation/consent, walking into Route101, a genuine grass encounter
  and both native co-op entries were observed.
- Failure: `TimeoutError: tagged wild battle field return`.
- Both clients remained at `CB2_HandleStartMultiBattle` / `BeginBattleIntroDummy`.

## Latest integrated change: built, NOT gameplay-verified

`engines/expansion-native/src/battle_main.c` now has a PORTABLE,
WorldCoop-specific startup branch. The stock startup waits for four humans,
elects a PvP master and replaces parties. RC7 co-op has two human owners and
already exchanged its allies and NPCs in WorldCoop's authenticated exchange.

The new branch validates two berry headers, preserves the staged parties,
NPCs and existing master assignment, initializes controllers and proceeds to
sprite setup. The ordinary non-co-op startup is retained. Build 19 includes
this change. No completed co-op gameplay run of this source is claimed.

## What remains unproven

- Complete shared co-op battle, actions, private rewards and safe field return.
- Owner-only medicine/capture spending and delivery; disconnect/cancel lifecycle.
- Complete species-cohort authoring-to-acquisition integration.
- Gameplay regression of the exact build-19 checkpoint.

Worker reports, source integration, compilation and gameplay acceptance are
separate evidence levels. No publication or installed desktop replacement is
claimed by this checkpoint.
