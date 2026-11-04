# Linux Release Readiness Implementation Plan

> **For Hermes:** Use subagent-driven-development to implement the isolated workstreams and parent-owned integration.

**Goal:** Deliver a versioned Linux player release with dependable launcher lifecycle, truthful co-op completion state, usable consent timing and rehearsed private backup/recovery. Windows native acceptance belongs to friends and remains explicitly pending.

**Architecture:** Preserve the native engine, loopback capability-authorized React launcher, pinned TLS hosting and private trainer saves. Fix the demonstrated lifecycle seams; do not add regions, AI GM or require browser gameplay. Independent branches are reviewed and consolidated into main by the parent.

**Tech Stack:** C native engine, Python stdlib server/session/packaging, React/Vite frontend, Linux Bubblewrap/Xephyr/SDL2.

## Task 1: Launcher lifecycle
- Files: `world/web_launcher.py`, `world/session.py`, new instance helper and focused tests.
- Reproduce duplicate-root broker contention with disposable state, not the human root.
- Make shortcut launch reuse the existing instance using owner-only state and capability-safe loopback handoff.
- Translate occupied broker locks into actionable errors without stealing live locks.
- Keep CLI and Host/Origin/auth protections intact.
- Verify focused reuse, stale instance, unsafe path and lock-contention cases; commit.

## Task 2: Co-op completion and invitation timing
- Files: `src/platform/world_activity.c`, related co-op/transport seam only if needed, `world/link_protocol.py`, focused tests.
- Reproduce false reset-required status during ordinary post-battle private rewards; distinguish genuine abort from successful link closure.
- Preserve private save ownership and never force idle during an actual battle.
- Align human invitation deadlines across authority/native paths, retaining explicit consent.
- Run focused status/deadline regressions; commit; parent compiles native binary.

## Task 3: Linux distribution
- Files: new `scripts/linux_package.py`, install/entry helpers, docs and package tests.
- Bundle compiled native ELF, prebuilt frontend and required Python source/data, not developer state or credentials.
- Include explicit runtime requirements, version and hashes; install/update user-local without touching profile roots.
- Exercise actual disposable bundle/install/update and tamper rejection paths.
- Parent produces final real archive from integrated source and native build, verifies package, publishes release artifacts.

## Task 4: Operations and recovery
- Files: new private hosting backup/restore and read-only health tooling, focused tests, recovery docs.
- Prefer a consistent offline snapshot guarded by the existing authority lock; never stop active human services for a release check.
- Preserve account/world identities and TLS pin. Restore only to a new destination; reject traversal, unsafe links and overwrite.
- Rehearse creation, backup, restore and reopened authority on disposable data; verify SQLite integrity and private credential continuity without printing them.
- Document that local trainer saves and host-account backups are distinct from authority backups.

## Task 5: Integration, release and supported scope
- Merge isolated reviewed branches into `release/linux-readiness`.
- Review dot's already-open invitation race/controls/co-op guide PRs for useful release docs; browser prototype remains optional and outside required release scope.
- Keep historical evidence labeled; publish a current support contract including individual story progression, ordinary stock play and two-person activities.
- Bounded checks: focused touched seams, one integrated frontend build, one native Linux build, one real package/install launch check on disposable state. No full campaign harness or Windows acceptance claim.
- CI must pass before main merge. Publish versioned archive plus checksum and release notes with remaining limits.
- Installed launcher updates must preserve existing saves and running games; do not restart the user's game or hosted service.

## Acceptance boundary
A Linux player can install/update, reopen the same launcher without stranded locks, join/play/save/return normally, understand recoverable battle-end prompts and export a private backup. Packaging and component evidence are not proof of arbitrary network-loss recovery, every special encounter, campaign completion or Windows human play. Those limits must remain visible rather than represented as completed by passing tests.
