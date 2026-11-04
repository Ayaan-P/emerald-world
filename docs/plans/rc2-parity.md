# RC2 parity integration

Goal: consolidate dot PR145 and149–154 into one installed, working candidate, not hold chat/travel/preview as unrelated projects. User requested one bounded acceptance pass on the integrated RC, not per-PR test projects.

## Integration
- Frontend stack: serialized status reads, read-only timeout recovery, solo validation, stable modal focus, in-page capture/input view.
- Fix known focus identity transition and stale preview teardown races during integration.
- Native stack: room/private chat, earned-Fly-to-friend with a distinct authenticated cross-map travel roster. Retain existing same-map render bounds and every private eligibility/arrival guard.
- Preserve save/account backup, guides, launcher reuse and shutdown fixes from RC1.
- Preserve source ancestry so included PRs can close only after main integration.

## One RC acceptance pass
Freeze one source commit and build native/frontend/package from it. Run existing integrated UI/API and touched protocol/native-component suites once. Run the actual package install/reuse/quit check and a bounded native chat/travel session on disposable trainers. Check supported Fly menu/cancel/rejection and cross-map roster separately from earned-Fly gameplay; never label a synthetic eligibility seam as a real earned-Fly run. Browser capture requires a real user window choice; source/DOM checks alone do not establish desktop capture, audio or input latency. No human save, browser profile or protected display is used.

If an RC check identifies a concrete fault, fix only that fault and rerun its affected check on the revised integrated RC; do not restart every independent PR test campaign. Record limitations honestly. Windows human acceptance remains friend-owned.

## Ship
Run CI on the integrated branch, merge main, close included/superseded PRs after ancestry verification. Produce RC2 package/checksum, verify published bytes and update next-launch local assets. Deploy matching server changes only if managed worlds are empty, with a private cold backup and rollback. No active human game is restarted.
