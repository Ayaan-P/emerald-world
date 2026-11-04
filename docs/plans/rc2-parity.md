# RC2 parity integration

Goal: advance the broader parity roadmap in meaningful integrated batches. The current dot PR145 and149–154 consolidation is a foundation, not the definition of parity or an automatic release boundary. Hermes chooses when a candidate contains enough coherent progress to justify one bounded acceptance pass and release; do not stop for per-PR test projects.

Before extending scope, compare roadmap specifications with current main implementation and already merged source. Stale pending-verification labels are not evidence of missing code. Prioritize P0 human adventure/persistence and then P1 adventure/QoL. P2 content/challenge/online work follows actual dependencies, not a promise to replace it with metadata-only stubs. Windows human play remains friend-owned.

## Integration
- Frontend stack: serialized status reads, read-only timeout recovery, solo validation, stable modal focus, in-page capture/input view.
- Fix known focus identity transition and stale preview teardown races during integration.
- Native stack: room/private chat, earned-Fly-to-friend with a distinct authenticated cross-map travel roster. Retain existing same-map render bounds and every private eligibility/arrival guard.
- Preserve save/account backup, guides, launcher reuse and shutdown fixes from RC1.
- Preserve source ancestry so included PRs can close only after main integration.
- Add individual Gym/League guest-credit protection without disabling ordinary shared trainer credit.
- Add real native owned-medicine auto-heal (no revives, no invented inventory), and local read-only IV/EV/Hidden Power Summary detail. These are partial deliveries of broader #52/#54, not closure of loadouts, EV-cap changes, Bag search or expanded Dex/HM work.

## One RC acceptance pass
Freeze one source commit and build native/frontend/package from it. Run existing integrated UI/API and touched protocol/native-component suites once. Run the actual package install/reuse/quit check and a bounded native chat/travel session on disposable trainers. Check supported Fly menu/cancel/rejection and cross-map roster separately from earned-Fly gameplay; never label a synthetic eligibility seam as a real earned-Fly run. Browser capture requires a real user window choice; source/DOM checks alone do not establish desktop capture, audio or input latency. No human save, browser profile or protected display is used.

If an RC check identifies a concrete fault, fix only that fault and rerun its affected check on the revised integrated RC; do not restart every independent PR test campaign. Record limitations honestly. Windows human acceptance remains friend-owned.

## Ship
Run CI on the integrated branch, merge main, close included/superseded PRs after ancestry verification. Produce RC2 package/checksum, verify published bytes and update next-launch local assets. Deploy matching server changes only if managed worlds are empty, with a private cold backup and rollback. No active human game is restarted.
