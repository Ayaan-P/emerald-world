# Linux Player Bundle Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Produce a versioned Linux x86_64 player archive with a verified install/update path that never copies player state.

**Architecture:** Explicitly require system Python 3.11+ and native runtime libraries. Keep the existing sandbox unchanged, since it mounts system libraries but not arbitrary bundled libraries. Package only tracked Python world sources, the Linux prerequisite helper, a supplied ELF and approved prebuilt web assets. Install immutable version directories and atomically switch a user-local shortcut target without touching worlds.

**Tech Stack:** Python standard library, tar.gz, readelf, unittest, disposable C executable fixtures.

### Task 1: Archive tracer bullet
- Create `test/world/test_linux_package.py` with a compiled minimal ELF and disposable frontend tree.
- Run `python3 -m unittest test.world.test_linux_package -v` and observe missing script failure.
- Create `scripts/linux_package.py` to validate explicit inputs, stage allowlisted files, record version/checksums/native requirements, and write deterministic archives.
- Rerun and inspect archive contents. Never use the parent's game binary for fixture tests.

### Task 2: Install/update tracer bullet
- Add failing subprocess tests for install, shortcut, version update, saved sentinel preservation and checksum rejection.
- Create `scripts/linux_bundle_install.py` and `scripts/linux_bundle_entry.py` as standalone packaged scripts.
- Verify all archive members before install. Copy into a fresh version directory, atomically switch `current`, reject foreign shortcuts and preserve all old versions and saves.
- Rerun package tests.

### Task 3: Input safety and runtime checks
- Add failing cases for invalid version, linked input, private frontend artifacts, missing assets and modified installed releases.
- Reject unapproved inputs and unsafe destination paths. Record and check actual system library requirements without bundling fake libraries or downloading anything.
- Document exact release invocation, runtime dependencies, trust boundaries, compatibility limitations and save-preserving update/rollback in `docs/linux-packaging.md`.
- Run package tests and the existing world tests. Commit only this worker's files, no push.
