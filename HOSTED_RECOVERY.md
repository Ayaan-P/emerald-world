# Hosted authority backup and recovery

## Production activation archives (RC12)

The protected RC11.3 activation archive is a **full service/state archive**, not
`world.hosting_backup`'s `root/` plus `tls/` format. Do not pass it to that
module's restore command. It contains private hosted and standalone state under
`var/lib/`, plus service metadata under `etc/`. It includes credentials, history,
and possibly player-owned files. Never publish its listing or content.

Use the separate activation rehearsal tool from a reviewed checkout:

```sh
umask 077
mkdir -m 700 "$HOME/private-recovery"
# Copy an already protected, consistent archive here through approved SSH/SCP.
# Set the local archive mode to 0600. Obtain its SHA-256 independently.
python3 scripts/rehearse_hosted_restore.py \
  --archive "$HOME/private-recovery/activation.tar.gz" \
  --destination "$HOME/private-recovery/rehearsal-NEW" \
  --sha256 TRUSTED_SHA256 \
  --authority-proof
```

The destination must not exist, even as an empty directory or dangling symlink.
Its existing parent must be owned by the caller and mode 0700. Archive input must
be an owned, single-link regular file with mode 0600. Symlink ancestors, absolute
archive paths, traversal, duplicate names, file/directory collisions, sparse
files, links, devices and FIFOs are refused. Extraction only accepts the known
activation archive prefixes and never writes to the archive's original absolute
paths. System directories cannot be destinations. Files are created exclusively
as 0600 and all extracted directories as 0700. Limits are 100,000 entries and
4 GiB of expanded content. A failed extraction removes only its fresh destination.
A later verification failure retains the private extraction for operator review.
These checks assume operator-controlled parents without concurrent same-user
renames or archive mutation. A matching hash is only trustworthy if the expected
hash came from a trusted channel.

Offline verification checks every extracted SQLite database, including copied
WAL state, with `integrity_check` and `foreign_key_check`. It reads service units
and ordered drop-ins as inert metadata, resolves the known hostname variable,
checks the hosted registry's endpoint and certificate SHA-256 against its service
configuration, loads both TLS certificate/key pairs, and matches hosted member
tokens to restored world identities. It hashes configuration and source deployment
references without printing names, tokens, endpoints or private key material.
This is a deliberately bounded systemd parser, not a general unit evaluator.
Unknown environment substitutions fail closed. No archived command is executed.

The optional authority proof requires Linux `unshare`, `ip`, and permission for
unprivileged user/network namespaces. It checks for a distinct network namespace,
loopback as the only interface, and no external routes before enabling loopback.
All TCP listeners bind 127.0.0.1 inside that namespace. It runs local reviewed
Python source against additional short-path private disposable state copies,
starts every registered hosted world and the standalone authority on their
original game ports, and authenticates the copied identities over pinned TLS
using the current `SOCIALRULES3` native handshake. Rules and admission policy are
not disabled. No player STATE, save import or world edit is sent. Runtime copies
are removed on normal exit. An interrupted process may leave a mode 0700
`/tmp/er-*` directory, which the operator should inspect and remove privately.

There is **no fallback to the active network namespace**. If isolation is not
available, omit `--authority-proof` for an offline-only check and record that
boundary. A failed command emits only a sanitized failure stage and any completed
offline checks. Successful output contains aggregate counts and hashes only.
No service is installed, stopped, restarted, promoted or replaced. Public
registry and TLS identities are never changed.

This proof does not replay management HTTPS, DNS, firewall, service sandboxing,
external client reachability, gameplay, or a production cutover. The activation
archive has source deployment references but **does not bundle `/opt` source**.
The output explicitly identifies and hashes the local implementation used for
the rehearsal. Recover the matching reviewed release source separately before
an operator-approved promotion. Do not infer a byte-identical source restore
from a successful state rehearsal. An old activation snapshot is also not a
current backup of everything humans have done since it was taken.

### Private independent-copy cadence

A practical operator policy is to review backup freshness daily, keep a verified
copy after each approved cold snapshot, and rehearse monthly and before a release.
A daily review does not itself create a daily consistent snapshot. If a 24-hour
recovery-point target is needed, approve a consistent snapshot method and
maintenance policy first. Never tar changing live SQLite files or stop human
worlds just to satisfy a schedule. The existing activation archive can be copied
read-only without recapturing or touching running services.

For each already-approved cold snapshot, use a fresh private local directory and
exclusive new filename, copy through approved SSH/SCP, set mode 0600, verify the
trusted hash, and run the rehearsal above. Keep the archive, hash, sanitized proof
and matching reviewed source release together on private encrypted storage.
Keep a second encrypted offline copy on an independently controlled device or
approved storage account. Verify that second copy's hash and rehearse from it
before treating it as recoverable. Suggested retention is seven daily snapshots
and four weekly snapshots, subject to capacity and the user's retention approval.
Do not delete the last verified snapshot until its replacement and independent
copy pass. This is a recipe, not an installed job: no timer, cron, cloud account,
upload, pruning or new production backup is created by the rehearsal tool.

Player saves and offline exports remain independently owned. Copy them separately
on the player's terms. A restored offline copy is a separate history and must
never merge into or silently replace the online authority. Do not copy private
archives, world databases, player files or TLS keys into Git or a release bundle.

## Hosted-manager archive format

These operator tools apply to `world.hosting.HostedWorldManager`, not a single
standalone `world.server` root or a player's hosted-profile export. No deployment
is performed by this change. Never interrupt current human play to run a backup.

## Cold snapshot

Use Linux and the same service account that owns the private root. Arrange an
operator-approved maintenance window separately. This tool does not stop services.
It refuses a live manager using a nonblocking exclusive `hosting.lock` flock,
and also acquires existing managed `world.lock` files. It holds the locks until
all files have been archived and flushed. Do not delete or replace lock files.
Do not allow concurrent filesystem writers, TLS rotation or direct database
editors. Advisory locks cannot protect against a writer that ignores them.

From the checkout or installed application directory:

```sh
python3 -m world.hosting_backup backup \
  --root /var/lib/emerald-world/hosted \
  --cert /etc/emerald-world/tls/cert.pem \
  --key /etc/emerald-world/tls/key.pem \
  --archive /var/backups/emerald-world/hosted-20261104T030000.tar
```

The archive parent must already exist. Use a new filename each time. Creation is
exclusive and mode 0600. Existing archives are never overwritten. Output contains
only status and file counts, never paths, identity tokens or TLS material.
A failed operation exits 1 and does not claim a successful backup. Ordinary
errors remove a partial archive. After a crash or SIGKILL, treat any remaining
archive as unverified until a disposable restore succeeds.

The uncompressed tar holds the entire private root's regular files under `root/`,
including management accounts, invitations, world identities, world SQLite files
and any WAL/journal files. Explicit certificate and key copies are under `tls/`.
Treat the whole archive as a credential vault. It is NOT encrypted. Store it on
private encrypted storage, keep independent copies and apply a reviewed retention
policy. Nothing is uploaded or pruned automatically. Player-local game saves and
client profile files outside the root are not included. Empty directories and
runtime sockets are not persistent state. Unexpected special files, hard-linked
files and symlinks (including path ancestors) are refused. The bounded format
supports at most 100,000 file entries and 4 GiB of file content.

## Disposable restore rehearsal

Restore only into a NEW, nonexistent destination whose parent exists. An existing
destination is refused even if empty. No live root is modified or replaced.

```sh
python3 -m world.hosting_backup restore \
  --archive /var/backups/emerald-world/hosted-20261104T030000.tar \
  --destination /var/lib/emerald-world/rehearsal-20261104
```

Restore validates all member paths/types before writing and uses exclusive file
creation, mode 0600 files and mode 0700 directories. Links, traversal, absolute
paths, duplicate names and entries outside `root/` and the two TLS files are
refused. SQLite `integrity_check` runs on every restored `*.sqlite3` database.
Ordinary extraction/integrity failures remove only the newly created destination.
Treat interrupted restores as incomplete. This is structural validation, not
archive authenticity verification. Only restore archives from trusted storage.
The path checks assume operator-controlled directories, not adversarial concurrent
renames of ancestors.

Before any promotion, independently rehearse the actual manager using
`DEST/root`, `DEST/tls/cert.pem` and `DEST/tls/key.pem`. Choose a short destination
path because managed Unix sockets have a strict path-length limit. Keep the original
advertise host and game port range. The registry pins the endpoint and TLS
fingerprint. Startup must restore every registered world or fail closed. Use an
isolated machine/network namespace if production still owns those ports. Retain
the original management endpoint and max-worlds setting in private operator
configuration. They are not inferred or rewritten by this archive tool. TLS
private keys must match the certificate and registry. Certificate renewal and
hostname migration are separate operations. Never run production and a restored
clone as competing authorities for the same published endpoint.

For the automated local rehearsal:

```sh
python3 -m unittest test.world.test_hosting_backup -v
```

The test creates disposable TLS and a real manager, enrolls an account, creates a
world and guest identity, proves live snapshot refusal, closes the fixture,
snapshots, restores, checks SQLite integrity, restarts a real restored manager
and verifies the original owner/guest credentials still resolve to the same
invitations. It also checks live health with a connected native client. This is
not a claim that a deployed service was backed up or restored.

## Live read-only health

```sh
python3 -m world.hosting_backup health --root /var/lib/emerald-world/hosted
```

Health reads the existing registry with SQLite `mode=ro`, samples each existing
private Unix admin socket with `inspect`, and emits only aggregate counts:
registered worlds, allocated port capacity, connected players, player capacity
of responding worlds, unavailable worlds and whether the manager authority lock
is held. The existing admin response stays in process. No player names, world
names, identity tokens, hashes, paths or module error text are emitted. There is
no new public endpoint. A down manager or unavailable world exits 1. A missing
registry fails without creating state. Port capacity is NOT the configured
max-worlds setting. Player capacity and connected counts exclude unavailable
worlds. Samples are sequential, not an atomic global snapshot. Lock ownership
and admin responses do not prove management HTTPS availability or external TLS
reachability. This probe does not call enrollment or any mutation action.

## Optional deployment template

`deploy/emerald-hosted-backup@.service` is a manual one-shot template with no
service stop/start dependencies. Review paths and account before installing it,
copy `deploy/hosted-backup.env.example` to your private operator configuration,
and precreate `/var/backups/emerald-world` as mode 0700 owned by the service user.
Use a fresh instance ID such as `20261104T030000` on each approved run. Installing
or running the unit is not part of the test. No timer is enabled or supplied:
an automatic cold backup against a running authority must fail, not interrupt
play. Only schedule it if a separate approved offline maintenance policy exists.
