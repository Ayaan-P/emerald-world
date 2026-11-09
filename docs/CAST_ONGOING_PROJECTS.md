# Ongoing actor-owned decisions

Follow-on to #289 (2c871354), retaining the consolidated native #26 pin. No fixed project is automatically installed and no integration branch is changed.

Characters may now author assigned project scenes with `once: actor`. Unlike one-shot `world` scenes, these remain executable whenever their current requirements allow. A character can make, reconsider, pause and resume a shared commitment in the same long-running project rather than publishing a disposable replacement project each time.

Each execution still requires a separately authored retained intention, a fresh exact revision, an assigned actor and a nonzero valid state change. A completed intention ID is never replayed. Nothing acts because a timer alone elapsed; the test's alternating decisions are test fixtures, not a predetermined story or a deployed behavior.

## Observable existing-game consequence

The test author gives Steven one ongoing decision scene: offer partner time or pause it. Actual committed project state controls his existing companion invitation at his original house. Later independent decisions can make that opportunity available again. The authority admission path is exercised, but no native battle or physical travel is simulated by this feature. A pause affects future invitations, not a running battle or player save.

The same mechanism supports cooperation, changing commitments or competing plans across the original locations supported by #289. It does not infer feelings or agreements by another character. Existing once-only scenes retain their semantics.

## Durable bounded execution

The old dispatcher ceiling of eight lifetime world-action completions is replaced by eight committed actor actions per actor per UTC day, shared by the underlying authority method used for direct intentions and accepted project invitations. The budget persists across restart, fails closed on clock rollback, and rolls back with a failed transaction. All prior intention receipts remain; crossing a day boundary never replays a completed intention.

The model's separate author-turn budgets remain unchanged. Existing invitation and immutable project limits remain. This is not unlimited autonomous execution.

## Checks and handoff

Tests execute ten independent decisions through the real authority across two budget days, observe actual companion invitation admission changing, retain no player participation records, verify restart/non-replay and verify budget rollback. No live model or rendered battle validation is claimed. Maya owns integration, native build, save safety and release QA.
