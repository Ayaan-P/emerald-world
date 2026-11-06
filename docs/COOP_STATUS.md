# Historical co-op status and evidence

This document preserves dated evidence from earlier integrations. For current mainline features and limits, start with [RC6 scope](RELEASE_RC6.md), the [documentation index](README.md) and [integration status](INTEGRATION_STATUS.md). Older roster, bag and capacity statements below do not override current source/release notes.

## Earlier release-readiness work

See [Player release scope](PLAYER_RELEASE_SCOPE.md) for the present player contract,
private-save ownership, ordinary battle result prompts, recovery limits and
Windows friend acceptance boundary. Hosted creation/invitations and the React
launcher were integrated after the baseline below. A human plus Hermes WAN
session subsequently completed a shared wild battle and both returned to the
field with Tag intact. This is not a full campaign or Windows acceptance claim.

The dated baseline and matrices below are historical evidence, not an assertion
that their listed commit is still the current main tip or that all their old
limitations still describe current code.

## Earlier verified baseline

The gameplay implementation at this historical checkpoint was on `main` at
[`ee3c130`](https://github.com/Ayaan-P/emerald-world/commit/ee3c130f96ea0be47e20ebd28bd46218f587cc65),
Git tree `d7e25e3c23e489c07037b9cd3388aade61fa0ad4`. Documentation-only
follow-ups do not change the tested gameplay source.

- [#131](https://github.com/Ayaan-P/emerald-world/pull/131) merged checked owned
  saves, fresh trade consent and checked trade commits, private faint friendship
  updates, and the co-op completion echo drain. The original source PRs remain
  traceable, but their older open/draft state does not mean the integrated code
  is absent from `main`.
- [#132](https://github.com/Ayaan-P/emerald-world/pull/132) merged dedicated
  persistent hosting, bounded population and nearest-peer views, safe busy
  presence, and explicit launcher lifecycle operations. It also fixes premature
  native LINK handshake expiry and idle active-Tag channel teardown.
- [CI run 41875036893](https://github.com/Ayaan-P/emerald-world/actions/runs/41875036893)
  passed the focused regressions and Linux warning-as-error build with standalone
  frame/save smoke on the source tree merged by #132. Separately, 53 focused
  transport/Tag/protocol/dedicated checks passed locally.
- Four disposable native Linux clients completed a real public pinned-TLS WAN
  run. All twelve directed peer sprites, ordinary walking, normal peer menus and
  bilateral consent for two independent Tag pairs passed.
- Both pairs entered simultaneous genuine grass battles with independent native
  battle masters. The first pair completed its capture while the second remained
  in its own connected battle, then the second pair completed its capture.
- Only each actual throw owner gained a Pokemon and spent a ball. Private party
  counts changed from 1/2/3/4 to 2/2/4/4. Non-owners' inventories and private PCs
  passed ownership checks. All four completed ordinary SAVE, Continue and re-SAVE
  with save counters 3, 4 and 5 and matching private state after reload.
- The dedicated authority is deployed and its active service/source hash were
  read back after the run. Existing world state, identities and TLS files were
  retained. Deployment had a private rollback backup and no connected users at
  cutover. All disposable native clients were reaped after acceptance.

This proves four players in one world running two independent two-human battles,
not four humans in one battle. It does not establish 32/64-player throughput,
Windows guest acceptance, fresh native PvP/trade acceptance, arbitrary disconnect
recovery or universal special-encounter support. The original campaign remains
playable; additional regions and expanded species are separate future work.
Private invitations, raw traces, screenshots, saves and binaries remain private.

The records below describe the older `02080a4` release snapshot. Their no-WAN,
no-live-deployment and unmerged-hardening statements are historical and are
superseded by this current section. Earlier failures and narrower evidence are
retained rather than rewritten as new acceptance.

## Historical snapshot and scope

The historical verification below records the earlier gameplay baseline at commit
[`02080a4140372be54c5115e605257cae96da45e6`](https://github.com/Ayaan-P/emerald-world/commit/02080a4140372be54c5115e605257cae96da45e6).
Its Git tree is `a102fffdfcd2c674daafe46cf0018c44dcb6e8b4`.
Documentation-only follow-ups do not change that gameplay implementation, though
they do change the repository tree hash. Future gameplay changes need their own
acceptance record rather than inheriting this one automatically.

[Player setup and controls](../README.md) and
[build instructions](../INSTALL_PC.md) describe how to use the current source.
`main` is the target for new PRs. `rc` is historical.

The acceptance results below are the maintainer's release verification record,
including independently checked local native results. The
[refreshed roadmap #5](https://github.com/Ayaan-P/emerald-world/issues/5) records
the combined release checks, and
[closed follower defect #102](https://github.com/Ayaan-P/emerald-world/issues/102)
records the corruption reproducer, repair and native persistence acceptance.
These results were not rerun by this documentation update. Disposable local
worlds were used, not human saves.
Private logs, screenshots, invitations, saves and executables are not published
here. Source links identify implementation and regression coverage, not a
substitute for native gameplay evidence. Earlier comments on #91 describe
intermediate failures and pending retests. This matrix records their later
outcomes without rewriting that history.

## Historical evidence matrix

| Area | Observed evidence | What it does not establish |
|---|---|---|
| Published main CI | [Run 41769845995](https://github.com/Ayaan-P/emerald-world/actions/runs/41769845995) at `02080a4` completed successfully: 87 focused regressions, Linux build and standalone smoke ("All checks passed"). | These 87 focused checks are narrower than the expanded 134-test local combined suite. Standalone smoke is not multiplayer acceptance. |
| Combined-main non-native checks | 134 combined protocol/component tests passed, and the Linux native build passed in the maintainer's verification. | This is not a count of native playthroughs or a claim that every legacy CI platform job passed. |
| Combined-main follower full-party catch | On the exact gameplay tree above, two real Linux clients completed a follower catch. Bob alone received the catch in his PC. Bob's ball count changed from 5 to 4 and Alice's remained 5. Both retained their original six private Pokémon. | Local-only proof, not a remote Windows guest or WAN catch. |
| Combined-main native persistence | Both clients completed ordinary native save, reload and resave after that follower/PC run. | Not an atomic two-disk transaction, forced-quit test, crash rollback or arbitrary reconnect guarantee. |
| Earlier host catch acceptance | Native host catches into a party slot and into PC with a full private party passed, with exact private ball ownership and ordinary save/reload checks. | These earlier individual runs are not described as fresh runs of every case on the exact combined tree. |
| Earlier follower catch acceptance | Native follower party and full-party PC delivery passed after the OT encryption repair. The combined-main follower/PC run subsequently confirmed the integrated path. | Does not cover every species, ball, storage state or special encounter. |
| Follower OT corruption regression | The original native follower failure corrupted species/moves/EXP. The repair rekeys only the catcher's private copy before stock ownership delivery. An actual-stock regression exercises encryption, shuffled substructures and ownership handoff across both owners and personality permutations. | The original failure is real history, not a current claim that follower delivery is still pending. A component regression alone would not have proven native delivery. |
| Trainer BAG rejection | Both native controllers were exercised, followed by continued normal combat, victory and saves with balls unchanged. Rejection was independently verified from native screenshot pixels. | OCR was unavailable. The raw harness false result was preserved rather than rewritten as an automated pass. This is visual native evidence plus continuation/save checks, not a clean OCR pass. |
| Failed throw continuation | Source/static and production-component path coverage exists. | No observed real native failed-throw continuation. The latest ordinary-ball attempt caught immediately, so this acceptance item remains pending. |
| Shared trainer encounter | The maintainer manually played the shared May battle successfully after the admission, unused NPC wire-slot and false-blackout fixes. | Local human confirmation is not universal trainer/special-encounter coverage or fresh WAN acceptance. |
| Full private parties | Native catch acceptance retained six private Pokémon per human, including reserve ownership. Each human's temporary combat roster remains capped at three usable Pokémon. | Not six combat Pokémon per human. |
| Hardening slices | Merged regressions cover presence local-ID collisions, bounded handshakes, reserve ownership, stale abort records, crossed tag offers and move reply validation. | Not comprehensive mid-battle quit, network-loss, rejoin or adversarial WAN acceptance. |
| Windows and WAN | Existing transport/client paths and older remote work remain in the repository. Windows verification has an external owner. | No new Windows guest acceptance, WAN catching acceptance or live server deployment is claimed for this release. |

## Ownership and gameplay contract

- Tagging requires bilateral consent and proximity. The native menu action is
  **Tag up (first 3 mons)**, followed by the partner's **Yes** response. Existing
  consent authorizes supported encounter handoff.
- Each trainer contributes their first three usable Pokémon. The temporary
  mixed roster must not replace either trainer's full private party.
- Balls are selected from the acting human's private bag. Selection/cancellation
  does not spend a ball. An executed throw spends only that human's ball.
- Supported shared wild catches use normal capture odds with synchronized wild
  HP/status and owner-specific context. Safari Balls are excluded. Only the
  catcher gets private dex/nickname and party-or-PC delivery after bilateral
  completion. The partner does not receive a duplicate.
- Capacity is private. A full party can receive a catch in PC, but selection is
  blocked if both that trainer's party and storage are full.
- Trainer battles reject BAG use. Non-ball battle items are unsupported in co-op.
  There is no claim of a complete co-op battle bag.
- Story credit remains individual. Each player currently initiates and wins
  their own trainer encounter for it to count. This is an accepted baseline
  limitation in [#89](https://github.com/Ayaan-P/emerald-world/issues/89), not
  shared-campaign completion.
- Save through the native menu after returning to the field. Normal completion
  and save/reload success do not prove safe abrupt shutdown at every protocol
  phase. Checked disk-save APIs and further commit-close work are not merged.
- Both peers need the same updated native source with co-op protocol v3.
  A base presence connection does not prove matching co-op versions.

## Included in the historical gameplay snapshot

Git ancestry and GitHub merge state were checked for this documentation update.
These slices are on `main`, not merely present on worker branches.

| PR | Included change |
|---|---|
| [#84](https://github.com/Ayaan-P/emerald-world/pull/84) | Reviewed native multiplayer, saved friend worlds and offline play integration. |
| [#86](https://github.com/Ayaan-P/emerald-world/pull/86) | Earlier asynchronous remote battle/trade pipeline integration. Not a fresh acceptance of this release. |
| [#87](https://github.com/Ayaan-P/emerald-world/pull/87) | Shared wild co-op, private rewards and independent native saves. |
| [#90](https://github.com/Ayaan-P/emerald-world/pull/90) | Launcher setup/navigation and connection status polish. |
| [#91](https://github.com/Ayaan-P/emerald-world/pull/91) | Private ball selection, executed-throw consumption, capture delivery and follower OT encryption repair. |
| [#92](https://github.com/Ayaan-P/emerald-world/pull/92) | Prevent local-ID collisions from starving remote trainer presence. |
| [#93](https://github.com/Ayaan-P/emerald-world/pull/93) | Bound presence/native-link handshakes without replaying old activity. |
| [#94](https://github.com/Ayaan-P/emerald-world/pull/94) | Reserve ownership hardening and private six-party preservation coverage. |
| [#96](https://github.com/Ayaan-P/emerald-world/pull/96) | Preserve new tagged encounter offers when stale abort records arrive. |
| [#97](https://github.com/Ayaan-P/emerald-world/pull/97) | Present crossed tag offers without waiting for the outgoing rejection. |
| [#98](https://github.com/Ayaan-P/emerald-world/pull/98) | Validate move replies against the outstanding controller request. |

## Historical pending work at 02080a4

| PR or issue | Status at this snapshot |
|---|---|
| [#95](https://github.com/Ayaan-P/emerald-world/pull/95) | Open draft. Private save ownership and checked native save commits. Not in `main`. |
| [#99](https://github.com/Ayaan-P/emerald-world/pull/99) | Open draft. Preserve both trainers' faint friendship changes. Not in `main`. |
| [#100](https://github.com/Ayaan-P/emerald-world/pull/100) | Open draft. Drain co-op COMMIT echo before closing the active native session. Not in `main`. |
| [#101](https://github.com/Ayaan-P/emerald-world/pull/101) | Open draft, stacked on #95's branch rather than `main`. Fresh trade consent and checked local save commit. Not shipped. |
| [#82](https://github.com/Ayaan-P/emerald-world/pull/82) | Historical open, unmerged Fly-to-friend travel work. Not a current release feature. |
| [#83](https://github.com/Ayaan-P/emerald-world/pull/83) | Historical open, unmerged native field/battle chat work. Existing Talk/menu presence is not proof this PR shipped. |
| [#2](https://github.com/Ayaan-P/emerald-world/issues/2) | Windows build/real guest verification remains externally owned and open. |
| [#89](https://github.com/Ayaan-P/emerald-world/issues/89) | Open known limitation for individual trainer story progression. |

At that historical snapshot, remaining acceptance included an observed native
failed throw followed by continued combat, broader mid-battle
quit/network-loss/rejoin timing, WAN catching, and special encounter coverage. Six combat Pokémon per human and
complete battle-item support are not available claims.

### Issue closure is separate from merging a fix

At the documentation audit, the May blocker
[#88](https://github.com/Ayaan-P/emerald-world/issues/88) and Linux relocation
blocker [#78](https://github.com/Ayaan-P/emerald-world/issues/78) and the focused
follower OT corruption defect
[#102](https://github.com/Ayaan-P/emerald-world/issues/102) were closed.
The roadmap and 11 broader issues received refreshed merged/pending summaries:
[#7](https://github.com/Ayaan-P/emerald-world/issues/7),
[#9](https://github.com/Ayaan-P/emerald-world/issues/9),
[#14](https://github.com/Ayaan-P/emerald-world/issues/14),
[#15](https://github.com/Ayaan-P/emerald-world/issues/15),
[#16](https://github.com/Ayaan-P/emerald-world/issues/16),
[#18](https://github.com/Ayaan-P/emerald-world/issues/18),
[#26](https://github.com/Ayaan-P/emerald-world/issues/26),
[#73](https://github.com/Ayaan-P/emerald-world/issues/73),
[#74](https://github.com/Ayaan-P/emerald-world/issues/74),
[#75](https://github.com/Ayaan-P/emerald-world/issues/75) and
[#76](https://github.com/Ayaan-P/emerald-world/issues/76).
They remain open because broader acceptance is incomplete, despite merged
implementation slices. Stale swarm-active/ready labels were removed from those
refreshed issues. This documentation update does not itself
close issues or declare full parity. The live
[issue tracker](https://github.com/Ayaan-P/emerald-world/issues) and
[roadmap #5](https://github.com/Ayaan-P/emerald-world/issues/5) remain authoritative
for subsequent tracker changes.

## Known presentation and operational limits

- The current tag interaction strings still say **No bag or catches in a tag**
  and **Tag: nearby; no bag or catches**. These predate merged catching support.
  They are stale UI text, not evidence that follower catching is unimplemented.
- Normal link closure before private catch UI may transiently look like a
  connection loss. Verified local runs still delivered the catch and persisted
  both private saves. This does not excuse actual disconnect failures.
- A launcher installed previously can still point to another checkout. Verify
  the checkout and **Native game binary**, and rebuild after updating source.
  This documentation change does not install launchers or update live servers.
- Invitations are private trainer credentials. Trust a bundled TLS pin only
  when received from the host through a trusted channel. There is no relay.
  Remote reachability and safe exposure of listeners remain the host's task.

## Implementation and reproducible checks

Useful source boundaries for reviewing this record:

- [Launcher entry point](../scripts/linux_client.py) and
  [desktop UI/session labels](../world/session.py).
- [Native tag menus and encounter admission](../src/platform/world_activity.c).
- [Co-op ownership, catch packets, private delivery and OT rekey](../src/platform/world_coop.c).
- [Battle bag admission](../src/item_menu.c) and
  [ball selection versus consumption](../src/item_use.c).
- [Catching source/component regressions](../test/world/test_coop_catching.py).
- [Current default-branch CI](../.github/workflows/main-baseline.yml).

The [README development section](../README.md#development-and-contributing)
provides the exact focused CI commands, including map constant generation,
followed by the Linux build and standalone smoke. The focused tests do not
launch game sessions. Standalone frame/save smoke is not multiplayer acceptance.
The combined 134-test result above is a release verification result, not a
promise that the narrower default workflow runs exactly that many tests.
The [legacy full-platform workflow](../.github/workflows/build.yml) is
manual-only. GBA ROM neutrality, sanitizer smoke and Windows/macOS checks must
be reported individually when actually run.

For any new acceptance claim, record the source identity, both native binaries'
build identity, client roles, connection scope, exact action/outcome and private
save readback. Keep raw failures when visual/manual interpretation differs from
a harness result. Never substitute mocked gameplay for an unobserved path or
publish private save/credential artifacts as a convenience.
