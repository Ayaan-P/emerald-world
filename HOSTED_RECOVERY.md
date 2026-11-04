# Hosted authority backup and recovery

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
