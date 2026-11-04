# Dedicated persistent world (Linux / existing Hetzner deployment)

This reuses `python3 -m world.server`, `WorldServer`, and the existing EWTR1 TLS
broker. There is no desktop session, emulator, SDK, ROM launch, new framework,
or HOME-based state discovery in the dedicated process. No campaign party or
save is rewritten by this service. Campaign/default gameplay is unchanged.
Optional mechanic modules are only loaded if previously deployed to this world.

## Existing-world start

From `/opt/emerald-world`, run as the existing `emerald-world` service owner,
after stopping the old authority through the operator's normal maintenance flow:

```sh
/usr/bin/python3 -m world.server \
  --require-existing-state \
  --state-dir /var/lib/emerald-world/worlds/friends \
  --listen 0.0.0.0:8765 --advertise 46.225.82.130:8765 \
  --cert /var/lib/emerald-world/worlds/friends/tls/certificate.pem \
  --key /var/lib/emerald-world/worlds/friends/tls/private-key.pem \
  --max-players 32 --max-controls 64 --connection-headroom 8
```

These TLS filenames are the existing DesktopSession convention, not a claim
about a remotely inspected filesystem. Confirm them against the old host.py
before switching. Reuse the actual existing paths if different. Never generate
a new certificate, change the pin, rotate tokens, delete the world, or overwrite
existing invitation files as part of this change. `--require-existing-state`
fails before creating a world if the explicit directory has no world.sqlite3.
Existing identities, hashes, modules and events remain in the same database.
The authority flock prevents running the desktop and dedicated host together.

`deploy/emerald-world.service` and `deploy/server.env.example` are reviewable
migration templates, **not installed or deployed by this change**. Preserve the
existing service name, user, working directory and state ownership; back up the
old unit/wrapper and persistent data before the parent operator changes ExecStart.
Use the existing Python environment if it differs from `/usr/bin/python3`.
No installs or native build are required for these Python components. For a
brand-new development world only, omit `--require-existing-state`.

SIGINT/SIGTERM stop admission, close/join the TLS workers, flush pending durable
presence hashes/events, close SQLite, remove owned sockets and release authority
and world activity locks. Active two-person activities are intentionally ephemeral:
restart/disconnect terminates them rather than replaying engine commands or
pretending an interrupted battle/trade completed. The service outlives every
individual player's connection. A failed listener exits nonzero for systemd.

## Repeated, identity-specific invitations

While the authority is running, from the same service UID and working directory:

```sh
/usr/bin/python3 -m world.server --require-existing-state \
  --state-dir /var/lib/emerald-world/worlds/friends \
  --invite friend2 \
  --invitation-out /var/lib/emerald-world/invitations/friend2.emerald.json
```

Repeat with a different output filename to reissue the **same identity/token**;
repeat with a different trainer ID for an independent identity. Existing output
files, symlinks, and destinations inside transport/trainers are refused. Outputs
are mode 0600; tokens are never printed by this command. Send each invitation
privately and authenticate its bundled certificate fingerprint independently.
Existing ayaan/friend invitation files remain valid and untouched. No cert/key
read is needed by the invitation command: it asks the private owner-only admin
socket. Legacy `--create-identity` remains for compatibility/offline provisioning;
it prints a credential, so use `--invite` for normal operation instead.

Admin-only API on `STATE_DIR/admin.sock`:

* `{"command":"invitation","trainer":"friend2"}` ->
  `{"ok":true,"invitation":{"version":1,"trainer":"friend2","token":"...",
  "endpoint":{"host":"...","port":8765},"pin":"..."}}`.
  It requires configured secure sharing; this response is private credentials.
* `{"command":"inspect"}` -> existing inspection data plus `capacity`
  (`players`, `controls`, `connections`) and nonsecret `sharing`
  (`endpoint`, actual `listen`). The existing full admin player listing remains
  independent of native render views. Never publish this admin response on WAN.

The broker still pins **only** transport/world.sock's inode; it cannot forward
admin requests or choose arbitrary destinations. WAN CONTROL requests still
accept only the existing actor-scoped intention/status APIs, not invitations.
TLS framing, pin verification, HELLO auth, capabilities, readiness checks,
private local profiles and strict native activity wire all remain unchanged.

## Capacity and native compatibility

* World population: default **32**, configurable `--max-players 1..64`.
* CONTROL sockets: default `2 * players`, configurable `--max-controls 0..128`;
  maximum two authenticated CONTROL channels per identity remains enforced.
* One presence + one LINK per identity, with exact live-presence binding.
* Total authority sockets: `2 * players + controls + headroom`.
  Headroom defaults to 8 (range 2..64), including **two reserved admin slots**.
  Dedicated TLS broker derives its relay budget from total minus those two slots.
  Defaults therefore allow 136 authority sockets / 134 TLS connections, not eight
  relay connections mistaken for eight trainers. Standalone broker CLI/constructors
  default to 136 relay connections and accept explicitly bounded 1..1024 budgets.
* Activity/tag budgets derive from player capacity: at default population up to
  **16 disjoint two-person activities** and **16 tag pairs**, never a many-human
  battle. Sessions retain strict per-actor reservations, consent and recipient
  guards. Each individual battle/trade/co-op encounter is still exactly two people.
* Native snapshots retain the **existing eight-PEER wire/render ceiling** regardless
  of global population. With known recipient location, select only same-map peers,
  nearest Manhattan distance first, ID as deterministic tie-breaker. Before the
  recipient's first location, send at most eight eligible existing peers. Legacy
  absent STATE and SOCIAL FIELD visible-but-unready behavior remain unchanged.
  No new busy/status fields were added; FIELD ready=0 is the generic busy signal.

These are admission/memory bounds, **not a tested 64-player throughput promise**,
not an unbounded MMO, and not new roster/UI functionality. Flooded TLS handshakes
can exhaust the public relay budget until the existing handshake timeout expires;
private administration remains separately reserved. Size/load-test infrastructure
before raising capacity. Public ingress still needs operator firewall/rate limits.

## Focused verification (no game launches)

```sh
python3 -m unittest test.world.test_dedicated test.world.test_server \
  test.world.test_transport test.world.test_link_sessions \
  test.world.test_link_protocol test.world.test_link_transport \
  test.world.test_crossed_tag_transport -q
```

The new checks exercise the actual authority, framed loopback pinned TLS,
subprocess dedicated CLI, private invitations, SIGTERM/reopen persistence,
more than eight trainers with multiple channels, 16 independent pair reservations
and bounded nearest-eight views. No SDK or native emulator is started.

## Self-service hosted-world backend (separate deployment)

`world.hosting` adds owner-account enrollment, world creation/list/resume and
private per-friend invitations. It starts an independent authority and pinned TLS
broker per world. It does not read, seed or replicate player save files. This is
a management/backend implementation, not an installed or integrated launcher UI.
Existing single-world services and their state must remain unchanged.

The separate `deploy/emerald-hosted.service` template expects a reviewed source
release at `/opt/emerald-world/hosted-current`, the existing `emerald-world`
service user, and `/etc/emerald-hosted.conf` containing `EMERALD_HOST=HOSTNAME`.
Ship the complete `world` Python package **and `world/map_catalog.json`**. Use a
new private root `/var/lib/emerald-hosted`, with a separately provisioned TLS
certificate/key in `tls/server.pem` and `tls/server.key`. Bootstrap once, as the
service user, **before** starting the management service:

```sh
python3 -m world.hosting create-account \
  --root /var/lib/emerald-hosted/state \
  --cert /var/lib/emerald-hosted/tls/server.pem \
  --key /var/lib/emerald-hosted/tls/server.key \
  --advertise-host HOSTNAME --game-listen-host 0.0.0.0 \
  --management-advertise HOSTNAME:8766 --invitation-out PRIVATE_HOST_ACCESS_FILE
```

The operator must explicitly expose management TCP 8766 and the bounded game
port pool 9001–9016. These are new endpoints, not changes to the existing 8765
friend world. Registered worlds, ports and credentials survive service restart;
a missing registered world database fails closed, never silently creates a new
world. Sixteen is an allocation limit, not a load-tested concurrency promise.
The template is not deployed by tests or by importing any module.

### Launcher integration (no GUI changes in this backend)

`HostingClient.enroll(access_file, profile_file)` exchanges private HOST ACCESS
for a client-generated owner credential; the credential is persisted before the
request so enrollment can safely retry. The bootstrap owner can use
`.invite_account(destination, request_id=...)` to invite independent owners
remotely—friends do not require SSH or operator-created accounts. Other owners
cannot sponsor accounts or access someone else's owned worlds.

`world.hosting_session.HostedWorldSession(desktop_session, host_profile)` supplies:

- `.create(name, trainer, request_id=stable_id)` → create and connect.
- `.resume(world_id)` → reconnect the owner to the same private profile.
- `.join(private_join_file, trainer)` → redeem and connect a friend; no owner
  profile or host account is required for joining.

Results contain `world` metadata (including the friendly name), stable local
`key`, and ordinary native `paths`; no bearer credential is returned by the
adapter. Use the launcher's existing `desktop_session.launch(paths, ...)` and
Disconnect controls. The adapter never starts a game, creates a save, selects a
starter, edits flags or changes an existing private save. Remote connections
are remembered by the existing friend-world backend. The launcher must render
remote-world metadata itself; the existing local-world library is not a remote
world listing. Its UI integration remains a separate collaborator task.

For friend invitations use `HostingClient.from_file(host_profile).invite(
world_id, private_destination, request_id=stable_id)`. Share only that private
join file. A join invitation binds to one trainer; retrying that same claim is
safe, while taking an existing identity or claiming a different trainer is
rejected. Native v1 invitations and save isolation are unchanged. Never log API
results containing `invitation`, access files or owner profiles; never publish
these files or private acceptance traces.

Run the actual local HTTPS/authority/native-session handoff regressions with:

```sh
python3 -m unittest test.world.test_hosting test.world.test_hosting_session -v
```

These tests do not establish deployed WAN management or native gameplay. The
opt-in `test/world/hosted_native_acceptance.py` instead runs real native clients
from **empty** private profiles with ordinary player SDK buttons, the original
new-game/starter sequence, save/Continue, bilateral Tag and owner leave/return.
It requires explicit private native invitations, a matched ready marker and
`--allow-launch`. `--through-dex` additionally attempts the stock individual May,
Pokédex and Poké Ball sequence; it must not be reported passed unless executed.
Story/intro progression remains private per trainer; ordinary shared trainer
victories grant both players trainer credit, but a guest's first shared May win
alone does not complete that guest's separate opening storyline.
