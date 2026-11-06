# Emerald World 0.2.0-rc.8.1 — RC8 launcher coherence pass

This is the launcher-polished RC8 Linux release candidate. It retains RC8's exact native game executable and gameplay feature scope. Read [the full RC8 notes](https://github.com/Ayaan-P/emerald-world/releases/tag/v0.2.0-rc.8) for shared XL exploration, standard-area terrain/director tools and the separate offline-story authoring workflow.

## Clear player flow

- The launcher identifies the current generated area by name, kind and dimensions, and gives ordered steps for entering and returning to the trainer's ordinary field.
- An open game is identified as open; a stopped game gets the Play now instruction. A host with no selected generated area is told to choose or generate one before exploring.
- Actual owner-authority occupancy appears on the current-area card. Area activation and generation confirmations are disabled while trainers remain inside. Existing server-side validation remains authoritative if state changes during an operation.
- The play page distinguishes shared exploration, director-published interactive adventures and advanced offline story tools. It explicitly states that offline story progress is not a shared multiplayer quest system and that opening an adventure does not start a director.
- Guidance distinguishes trainer saves, generated-area storage and offline story journals. Model cost confirmation, no automatic retries and save-before-close behavior remain intact.

This pass does not add a point-and-click offline-story editor, a new story launch button, an autonomous director, expanded National Dex support or new native gameplay.

## Verification

- 52 React UI tests passed, including occupied-area replacement controls and the mode descriptions.
- 42 backend tests passed, including current-area dimensions/occupancy from a real disposable authority, existing launcher actions and explicit host authoring.
- Production frontend build and API test passed.
- A real headless-browser walkthrough against a disposable launcher created a local expedition, showed the empty-area guidance, then displayed an explicitly authored XL area published through the real owner socket. Its archive row was read back. Generation review/cancel was exercised without contacting a model. Desktop and 390-pixel viewport screenshots were inspected; no horizontal overflow or JavaScript errors were observed in the scoped flow.
- The exact RC8 native binary is retained: its original smoke, versioned offline story/restart and two-real-client XL gameplay evidence is unchanged. These native journeys were not rerun for this launcher-only pass.
- Package checks verify every archive file, the exact native executable, the standalone entry point and installer checks. Nothing is installed by these checks.

The previous RC8 tag/archive is retained. RC8.1 has a separate versioned archive to support the existing installer's safe update behavior. Publishing does not change the source-checkout desktop shortcut or copy/delete human saves.
