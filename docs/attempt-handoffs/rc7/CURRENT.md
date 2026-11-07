# Current RC7 source handoff

This extends the original source-only handoff. It does not replace RC7 with a
new engine, create a new repository, or incorporate newer Dot branches.

## Current source

- App gameplay checkpoint: `670d991d4c1eebe421139e2d73a83885416a80be` on `integrate/rc7`.
- Engine checkpoint: `fb9e7bde1a6895b4a1a9dfe9ff47f94a7e67e212` on local `integrate/rc7-world`.
- Engine is a submodule; the recorded local engine commit is not fetchable from
  the upstream URL in `.gitmodules`. Do not mistake a parent push for publishing
  that object. The engine's complete current source deltas are supplied here.
- No full upstream-history bundle is published: upstream includes tracked ROM
  and executable paths, which the original handoff deliberately excluded.

## Source reconstruction / review

For an engine checkout already at `e406cf82922e9c3a5bfee746f9a97f67f3916a4c`:

```sh
git apply --check /path/to/emerald-world/docs/attempt-handoffs/rc7/native-world-integration-current.patch
git apply /path/to/emerald-world/docs/attempt-handoffs/rc7/native-world-integration-current.patch
```

For a new trusted upstream checkout, the original `STATUS.md` describes applying
`native-foundation.patch` then `native-world-wip.patch` to the pinned public
base. Apply `native-world-integration-current.patch` after those two patches.
The JSON manifest records this incremental patch hash and exact SHA-256 of all
changed source files at the current checkpoint. It is not a ROM/save/binary.

Patch reconstruction preserves source bytes, not the historical commit objects
or merge ancestry. The build wrapper has an ancestry check, so a newly
reconstructed history is NOT automatically build-ready; do not disable that
check or claim fresh-clone reproducibility has been verified. Existing matching
local ancestry/build inputs continue to use the normal build wrapper.

## Gameplay boundaries

- Ordinary two-client single battle: passed on build16.
- Independent ordinary saves and cold Continue: passed on build18.
- Generated-area NPC interaction and return: passed on primary build15.
- Tagged wild co-op: FAILED on build19. It advances past the stock four-human
  startup; host remains in `DoBattleIntro`, guest in `BeginBattleIntroDummy`,
  both under `BattleMainCB2`. Shared battle completion is not delivered.
- Build19 compiled with the mandatory checks. Compilation is not gameplay.
- Historical passing binaries came from then-uncommitted sources; their hashes
  identify the artifacts, not exact historical source commits.

The current work map and next actual integration blocker are recorded in
`docs/RC7_WORKBOARD.md`. Trading and newer Dot work are out of scope.

## Verified source-tree reconstruction

All three patches were applied in order to a temporary Git index seeded from
`bb3fd057061cdd7e6a9e79b76abb41924ee44ecc`. The reconstructed tree exactly
matches `fb9e7bde1a`'s tree: `289ad25553d2de1a8e6e57cb4cb110ee5841e108`.
There were no differing paths. The source worktree was not reset or modified.
This verifies the complete source handoff, not a fresh-clone build or gameplay.

Latest engine checkpoint also fixes the co-op link send task COUNT_PLAYERS gate
(two native owners versus four battlers). Build20 compiled before committing
this source; its actual co-op run is pending. No new gameplay pass is claimed.
