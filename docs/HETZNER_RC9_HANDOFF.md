# Hetzner hosting handoff

Deployment verified 2026-11-07 UTC (2026-11-06 America/New_York).

## Source and running services

- Main release merge: `4b1f554e` (PR 240).
- Deployed Python source: `73af5021705d67f65c9d5a9e510ba35d35a6902a`, the accepted RC9 head whose tree matches that merge.
- Both `emerald-hosted.service` and `emerald-world.service` now use `/opt/emerald-world/releases/rc9-73af5021705d`.
- Both read back active/running, with zero restarts after deployment.
- Service working-directory overrides are in each service's `90-rc9-source.conf` drop-in. Original units, ports, service users, state locations and TLS configuration are unchanged.
- Existing hosted management endpoint and independent dedicated friends authority remain separate services.

## Preservation and acceptance

All existing authorities reported zero connected players before maintenance. Services were stopped gracefully and persistent hosted state, dedicated worlds and invitations were backed up privately on the server before switching source.

- Three registered hosted worlds and the separate friends world were preserved.
- Before/after comparison verified the hosted account/world/member/invitation/config registry and TLS file hashes unchanged.
- All existing authorities answered their private inspection endpoint after restart.
- Local targeted hosting, session, UI-adapter and UI-contract tests: 22 passed.
- From the installed RC9 client modules, the existing owner account successfully listed its world and resumed it over the public endpoint.
- Public pinned TLS and actual trainer authentication passed through a temporary local broker. No player save was read or rewritten by this check.
- This acceptance did not create a new production world or run a new WAN native battle. It does not claim those actions were exercised during this deployment.

## Launcher account namespace

The installed Expansion launcher uses `~/.ew/x`. The existing owner profile and enrollment marker had remained in the older `~/.local/share/emerald-world/worlds` namespace, causing the new launcher to appear unenrolled.

The existing account was restored into the new namespace through `HostedLauncher.restore_profile`, using the validated old profile/marker, without issuing a new account or rotating credentials. Server-side listing and resume verified the restored account. The old namespace and saves remain untouched. No private profile, token, certificate key, invitation or account backup belongs in Git.

## UI ownership

Ayaan assigned consumer UI organization to Dot. No frontend worker patch was integrated, and the installed frontend was not modified in this follow-up. The existing UI still needs Dot's consumer-facing organization and labels; updating server source/account enrollment does not fix its navigation.

Use the existing hosted operations (`host_create`, acknowledgment, resume/join) for persistent remote worlds; do not redirect the primary creation flow to `local_create`. Local expeditions are a different mode. Read the game's implemented features before deciding the consumer hierarchy.
