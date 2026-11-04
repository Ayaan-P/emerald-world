# Emerald World

A native Pokémon Emerald multiplayer experiment, based on the
[pret decompilation](https://github.com/pret/pokeemerald) and the original
[NTx86 PC port](https://github.com/NTx86/pokeemerald-sdl2pc). Each trainer keeps
a private team, bag and save while exploring a shared world.

`main` is the current development and playable co-op baseline. Start new work
from `origin/main` and target PRs to `main`. `rc` is a historical integration
branch, not the current release. The Linux release-candidate work includes the
React launcher, private backups, user-local packaging and lifecycle fixes; it
is not a claim of complete shared-campaign or Windows play acceptance.
See [Player release scope](docs/PLAYER_RELEASE_SCOPE.md) for current behavior,
recovery limits and the remaining friend-owned Windows gate.

For the versioned Linux archive and save-preserving user installation, see
[Linux packaging and installation](docs/linux-packaging.md). The package requires
system Python 3.11+, Bubblewrap, Xephyr, SDL2 and a browser; it does not require
npm, a development virtualenv or a source checkout on the player's machine.

The current source launcher is built with `npm ci && npm run build` in `launcher-web`,
then opened with `python3 -m world.web_launcher` from the repository root.
The browser opens the launcher; **Play opens a separate native game window**.
The older tkinter source launcher remains a fallback, not the packaged player UI.

## What is available now?

The verified gameplay baseline is [`ee3c130`](https://github.com/Ayaan-P/emerald-world/commit/ee3c130f96ea0be47e20ebd28bd46218f587cc65),
including durable private saves and trade/completion hardening
[#131](https://github.com/Ayaan-P/emerald-world/pull/131), and dedicated hosting
with full four-client Linux WAN acceptance
[#132](https://github.com/Ayaan-P/emerald-world/pull/132).
See [Co-op status](docs/COOP_STATUS.md) for current evidence and explicitly
separated historical verification records.

| Feature | Availability and evidence boundary |
|---|---|
| Shared exploration and tag invitations | Four native Linux clients passed real pinned-TLS WAN acceptance with all twelve directed peer sprites, ordinary walking, normal player menus and two bilateral Tag pairs. |
| Shared wild and ordinary trainer battles | Available after both players consent to tag up. The maintainer manually completed the shared May encounter locally. Special encounters are not universally verified. |
| Combat roster | Each human brings the first **three usable Pokémon**. Both retain their private parties of up to six outside the temporary combat layout. This is not six combat Pokémon per human. |
| Private wild catching | Earlier host/follower and full-party PC cases passed locally. The latest four-client WAN run passed two simultaneous pair battles and private owner-only catches, including one pair completing while the other remained active. All four saved, reloaded and re-saved. |
| Battle bag | Poké Balls in supported shared wild battles only. Trainer battle BAG use is rejected. Other co-op battle items and a complete shared battle bag are not supported. |
| Story progress | Private story progression, not blanket flag mirroring. Ordinary shared trainer defeat credit exists, but some rival/story continuations still require each player's own encounter/script. See [Player release scope](docs/PLAYER_RELEASE_SCOPE.md). |
| PvP and trading | Existing menu paths remain available. Checked private save/trade commits and fresh trade consent are merged through #131. Fresh native PvP/trade acceptance is not established by the WAN wild-catching run. |
| Remote play | Dedicated authority deployed and verified live with existing world, identities and TLS material preserved. Full four-client Linux WAN catching and persistence passed. This is not Windows guest or 32/64-player throughput acceptance. |

**Both peers must build the same updated native source with co-op protocol v3.**
An older client being visible in the world does not prove matching gameplay
versions. Base presence protocol compatibility is not a co-op version check.

## Get started on Linux

1. Follow [INSTALL_PC.md](INSTALL_PC.md) for dependencies, hash-pinned upstream
   build inputs and the native build. Use the current `main` checkout on both
   computers. No game binary, ROM or save is distributed by these instructions.
2. From that checkout, check launcher prerequisites without starting a game:

   ```sh
   python3 scripts/linux_client.py --check
   ```

3. Open the desktop launcher:

   ```sh
   python3 scripts/linux_client.py
   ```

The launcher checks Python tkinter, Bubblewrap, Xephyr, SDL2 and the native
executable. It does not install dependencies. A passing `--check` does not test
runtime sandbox policy or your desktop display. Use a graphical Linux session.
The launcher looks for `build/pokeemerald64`, then `pokeemerald64`. In **Settings**,
**Native game binary** lets you select the intended build. Check this when
updating, particularly if an older binary exists in the higher-priority location.

Optional application-menu installation:

```sh
python3 scripts/linux_client.py --install-user
```

This points to your checkout and Python interpreter without copying the game.
Keep them in place. An existing, different launcher is left unchanged, so do not
assume a previously installed menu entry now selects a new checkout. Start from
the checkout explicitly when checking a new build.

### Host a world

1. In **Play**, enter a **World key** using letters, digits, `_` or `-`, then choose
   **Create world**. For an existing world, select its key instead.
2. Choose **Host selected**.
3. Under **Human trainer**, select a saved trainer or enter a new name, then choose
   **Launch / resume trainer**. Leave **Seed save for NEW trainer** in **Settings**
   blank for a new adventure. An explicitly selected seed is copied only for a
   new trainer and does not overwrite an existing one.
4. For another local launcher joining a world hosted on this computer, select
   the same world and use **Join local**, with a different trainer identity.
5. To invite a friend on another computer, open **Connect friends**. Set
   **Listen address** and a friend-reachable **Advertised address (HOST:PORT)**,
   then choose **Enable secure sharing**.
6. Enter a unique **Friend trainer name** and choose **Save trainer invitation**.
   Send one invitation per friend through a trusted private channel.

The default listener `127.0.0.1:8765` is local-only. For LAN or internet access,
the host must arrange a reachable listener, firewall and any required routing or
port forwarding. A wildcard listener is not an address a friend can connect to.
Supply an explicit advertised address. There is no relay or automatic NAT
traversal service. Exposing a listener is an operator decision, not something
these docs deploy for you.

### Join a friend securely

1. Obtain your trainer invitation privately from the host. Do not import an
   untrusted invitation from a public post or issue attachment.
2. In **Connect friends**, choose **Import friend invitation**. It fills in the
   host address, certificate pin and assigned trainer identity. Importing alone
   does not connect or launch a game.
3. Verify the source and details with the host, then choose **Connect remote TLS**.
4. Return to **Play** and choose **Launch / resume trainer** for your assigned
   **Human trainer**.
5. After a successful connection, **Saved friend world** and **Rejoin saved friend**
   can reuse that private connection. **Forget saved friend** removes the saved
   connection, not your game progress.

You can also prefill the launcher without automatically connecting:

```sh
python3 scripts/linux_client.py --invitation FILE
```

The bundled SHA256 certificate pin is trustworthy only because the invitation
came through a trusted channel. TLS does not make an arbitrary invitation safe.
Keep invitations, trainer credentials and TLS private keys private. Do not paste
them into bug reports. If a connection fails, check the address, reachability,
assigned identity and trusted pin with the host instead of bypassing pin checks.
Legacy invitations may require a separate local world key and manually entered
host/pin fields, as indicated in the launcher.

## Persistent server hosting

For an always-on world, run the dedicated authority on the server rather than
hosting it inside a player's desktop session. See [dedicated deployment](deploy/README.md)
for the service, existing-world migration and private invitation commands.
Players join through **Import friend invitation** and **Connect remote TLS** as
above; leaving or closing a remote client does not shut down that server.

World population is configurable separately from native rendering: the default
is 32 authenticated trainers, while each native client receives at most eight
nearby peer records and draws only what the stock object pool can safely hold.
These are configured bounds, not a measured 32-player throughput guarantee.
Battle and trade activities remain two-person, with independent actor-scoped
sessions rather than a single global encounter. Parties, bags, PCs, story progress
and saves remain private. This does not alter the original campaign or add regions.

## Tag up and play together

1. Launch different human trainers in the same world. Both should have usable
   Pokémon and be free of battle, menus or dialogue. Meet on the same map.
2. Face the other trainer and press **A** (default keyboard **Z**) to open their
   native interaction menu.
3. Choose **Tag up (first 3 mons)**. The other player receives a **Tag up invitation**
   and must select **Yes**. The default response is **No**.
4. Stay nearby and enter grass for a supported shared wild encounter, or initiate
   an ordinary trainer encounter. Tag consent authorizes the encounter handoff.
   The waiting screen may show **Joining tagged encounter**.
5. Each human chooses actions for their own combat Pokémon. Finish the encounter
   and allow both clients to return to the field before saving or disconnecting.
6. To stop tagging, interact with the partner again and choose **End tag**.

The menu also contains **Talk**, **Battle single**, **Battle double** and
**Trade party**. Those are separate interaction paths, not the tag-up action.
**Prepare party at Center PC** appears at supported Pokémon Center locations.
It is not permission to access a partner's storage remotely.

**Known stale UI text:** the tag menu still says **No bag or catches in a tag**
and **Tag: nearby; no bag or catches** in this gameplay snapshot. Those lines
predate #91. Shared wild Poké Ball use is implemented despite that wording.
Trainer battles and non-ball battle items remain restricted. This documentation
does not change the in-game strings.

### Catch a wild Pokémon privately

1. Bring your own Poké Balls and ensure your private party or PC has space.
   Both players need the same updated co-op v3 native build.
2. Tag up and enter a supported shared wild battle as described above.
3. On your action, select **BAG**, open the Poké Balls pocket, select a ball you
   own and choose **USE**. Unsupported items do not offer a usable battle action.
   Safari Balls are excluded. A full party is fine if your PC has room.
4. Let the ordered battle action execute. Merely selecting or cancelling a ball
   does not consume it. An executed throw debits only the thrower's private bag.
5. After a successful catch and bilateral battle completion, the catcher gets
   normal private Pokédex/nickname handling. Delivery is to their party if it has
   room, otherwise their PC. The partner does not receive a duplicate catch.
6. Finish the private prompts, return to the field, inspect your party/PC and
   save through the normal native menu on each client.

Native trainer BAG rejection has been followed by normal combat, victory and
saves with balls unchanged for both controllers. A failed throw is covered by
source/component tests, but **a real native failed-throw continuation has not
been observed**. The latest regular-ball attempt caught immediately. Do not
mistake successful capture for evidence of the failed-throw path.

A completed catch can transiently produce a misleading connection-lost status
while the native link closes before private catch UI. Local acceptance verified
private delivery and saves despite that presentation issue. Unexpected loss,
mid-battle quitting and rejoin recovery still need broader acceptance. Do not
use normal-completion evidence as a guarantee against lost progress.

## Saves, ownership and offline play

- Multiplayer worlds default to `~/.local/share/emerald-world/worlds`. Each
  trainer has separate game state. Multiplayer profiles are separate from
  standalone Emerald saves.
- Each human retains their own team, inventory, PC and save. A temporary mixed
  combat roster is not a shared persistent party. Native full-party acceptance
  retained all six private Pokémon per trainer while delivering a catch only
  to its owner.
- **Save from the native game menu before closing or disconnecting.** Private
  result handling after battle is not a claim of crash-safe disk transactions.
  Back up stopped profiles before experimenting with new builds. Do not open
  the same trainer save concurrently in multiple games.
- **Play offline / resume copy** uses a separate offline save.
  **Copy online and play offline** requires the online trainer to be stopped.
  Offline progress never merges back into the online profile.
- Closing the launcher stops its own games and host. Disconnect before switching
  worlds. The optional Luna GM and AI-controlled trainer are not required for
  human multiplayer and do not attach an agent to your human game.

## Controls and standalone native port

The native port supports Windows, Linux and macOS build targets. That platform
support is separate from current Linux co-op acceptance. Windows guest
verification remains externally owned in [#2](https://github.com/Ayaan-P/emerald-world/issues/2).
See [INSTALL_PC.md](INSTALL_PC.md) for platform build instructions.

| GBA | Keyboard | Controller |
|---|---|---|
| A | Z | A |
| B | X | B or X |
| Start | Enter | Start |
| Select | \ or Backspace | Back |
| L, R | A, S | LB, RB |
| D-pad | Arrow keys | D-pad or left stick |
| Fast-forward (hold) | Space | Right trigger |

Ctrl+R resets the game, like A+B+Start+Select, Ctrl+P pauses and F11 switches to
fullscreen. Save first and do not treat resets or fast-forward as verified
multiplayer recovery tools.

The controls, window size and fullscreen can be changed in `pokeemerald.ini`,
which the game writes with defaults when it first starts. For standalone play,
it is next to the save in `%APPDATA%\pokeemerald` on Windows,
`~/.local/share/pokeemerald` on Linux and
`~/Library/Application Support/pokeemerald` on macOS. If the launch directory
contains a legacy `pokeemerald.sav`, both files are there instead. The game
prints its paths at startup. `--save FILE` and `--config FILE` select other files.
The multiplayer launcher supplies its isolated trainer paths instead.

SDL knows most controllers. For others, put a `gamecontrollerdb.txt` from
[SDL_GameControllerDB](https://github.com/mdqinc/SDL_GameControllerDB) in the same folder.

## Development and contributing

Fetch current `origin/main` before branching and open focused PRs into `main`.
Keep game/runtime changes separate from documentation updates. Do not replace
the working co-op baseline with historical `rc` or `vanilla` code.

The default [Main baseline workflow](.github/workflows/main-baseline.yml) runs
focused protocol and actual-source C regressions, a warnings-as-errors Linux
build, and standalone headless frame/save smoke. It does not certify native
human multiplayer, WAN recovery, Windows guests or GBA ROM neutrality. The
[legacy full-platform workflow](.github/workflows/build.yml) is manual-only.
Report exactly which checks actually ran.

After installing build prerequisites from [INSTALL_PC.md](INSTALL_PC.md), the
focused CI sequence is:

```sh
make -C tools/mapjson
tools/mapjson/mapjson groups emerald data/maps/map_groups.json data/maps include/constants
tools/mapjson/mapjson layouts emerald data/layouts/layouts.json data/layouts include/constants
PYTHONPATH=.:test/world python3 -m unittest test_coop_catching test_tag_coop test_link_protocol test_link_sessions test_trainer_abort_wire_regression test_link_battle_payloads test_coop_controller_repro -v
```

Those checks compile production-component fixtures but do not launch native
game sessions. The build and standalone smoke are separate checks:

```sh
python3 scripts/restore_upstream_assets.py
make -j"$(nproc)" linux CFLAGS=-g WERROR=1
python3 test/headless/smoke.py ./pokeemerald64 --out build/main-smoke
```

See [headless test documentation](test/headless/README.md) and
[CLAUDE.md](CLAUDE.md) for development invariants, including save layout,
portable guards, deterministic frames and GBA build safety. Do not update frame
expectations merely to hide a regression.

Use disposable profiles for native multiplayer testing, never another person's
live game. Report commit/build identity, roles, actions, expected versus observed
results and whether evidence is component-only, local native or WAN. Redact
credentials and private invitation data. Never commit or upload ROMs, saves,
private keys, runtime worlds or generated executables.

Follow the [roadmap](https://github.com/Ayaan-P/emerald-world/issues/5),
[open issues](https://github.com/Ayaan-P/emerald-world/issues) and
[release status](docs/COOP_STATUS.md). A merged fix is not proof every acceptance
criterion in its broader issue is complete. Draft PRs are not shipped features.
