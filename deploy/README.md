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
