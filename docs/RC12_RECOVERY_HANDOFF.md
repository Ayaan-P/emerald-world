# RC12 recovery handoff

## Verified

The new `scripts/rehearse_hosted_restore.py` handles the actual full activation
archive format. It is separate from `world.hosting_backup` and does not install
or activate anything. `HOSTED_RECOVERY.md` documents its use and independent-copy
policy. The change does not modify launcher, session, server, builder or UI code.

A normal approved read-only SSH/SCP copied the existing protected activation
archive to an owned mode 0700 directory outside this checkout. Remote mode was
0600 and the trusted SHA-256 matched before and after the rehearsal:

`016e11a65344b884e0ee29fba837c5044e8f228fb2a0e252f073f426235c52ff`

Real command output included:

```text
"archive_entries": 107
"files": 51
"sqlite_integrity_checks": 8
"tls_registry_pin_consistent": true
"hosted_worlds_started": 4
"hosted_credentials_authenticated": 9
"standalone_credentials_authenticated": 6
"isolated_network_namespace": true
"loopback_only_listeners": true
"no_external_network": true
"management_https_replayed": false
"original_source_bundled": false
```

Both production services returned `active` on a final read-only status check.
The protected archive remained mode 0600 with its original SHA-256. The final
local extraction had zero file/directory permission mismatches. No production
backup, restart, shutdown, TLS rotation, public listener, registry edit, cutover,
save merge, timer, cloud account or upload was performed.

`python3 -m unittest test.world.test_rehearse_hosted_restore test.world.test_hosting_backup -v`
returned `Ran 17 tests` and `OK`. Tests cover malformed archives, link and device
refusal, traversal, duplicate/colliding paths, resource bounds, private ownership
and modes, hash mismatch, fresh-only/active-destination refusal, corrupt SQLite,
TLS/registry mismatch, current-network refusal, and an isolated fixture restart
with rules-v3 admission. The existing live-backup lock refusal tests still pass.

## Proof locations

Sanitized integration evidence is outside the repository:

- `/home/ayaan/rc11-swarm-integration-evidence/rc12-product/recovery.json`
- `/home/ayaan/rc11-swarm-integration-evidence/rc12-product/recovery-tests.txt`
- `/home/ayaan/rc11-swarm-integration-evidence/rc12-product/recovery-production-copy-proof.txt`

The archive and extracted state remain private under
`/home/ayaan/.local/state/rc12-recovery/`. Do not copy that directory into the
repository or release evidence. Disposable runtime copies are normally removed
at process exit. The tool never reads credentials aloud or emits private values.

## Limits and operator decision

This is recovery of the supplied activation snapshot, not a current snapshot of
subsequent human progress. The copied metadata references a historical source
release but the archive contains no `/opt` source. Actual runtime proof used the
reviewed local checkout, with its aggregate Python-source SHA-256 recorded in the
sanitized proof. It proves state compatibility and identity authentication, not
a byte-identical historical source recovery or replay of the archived service
sandbox. Preserve the matching reviewed source release separately.

Management HTTPS, public DNS/firewall reachability, native gameplay and production
promotion were not exercised. The recovery proof deliberately cannot contact the
production endpoints. Do not weaken that isolation to make a result pass.

Native build verification was attempted. The first build exposed missing
pkg-config sysroot settings. Supplying the existing dependency sysroot resolved
that step, but compilation then failed with:

```text
Error: file not found: data/mb_ereader.gba
Error: file not found: data/mb_colosseum.gba
```

The native headless command was also attempted and failed because no
`pokeemerald64` was produced. No fabricated multiboot data or borrowed executable
was used to turn that failure into a pass. Recovery-specific Python and real
production-copy authority proofs passed independently of that build blocker.

Before any real cutover, the operator must separately approve a maintenance and
promotion plan, resolve the exact reviewed release source, take a consistent
current snapshot, and verify the missing external/management/native boundaries.
Keep offline save ownership independent. An offline copy never becomes an online
merge source automatically.
