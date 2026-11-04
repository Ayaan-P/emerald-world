# Emerald World

`main` is the development baseline for the native multiplayer client and world
host. Start new work and pull requests from `main`; `rc` is retained as a
historical integration branch, not the current playable baseline.

Each trainer keeps a separate party, inventory and save. This is an experimental
multiplayer build, not a complete shared-campaign release.

## Working co-op baseline

- Two human-controlled Linux clients can explore the same local world, accept a
  tag invitation and enter shared wild or ordinary trainer encounters.
- The maintainer manually played the shared May battle successfully after the
  trainer-dialogue admission, unused NPC wire-slot and false-blackout fixes.
  This is local gameplay confirmation, not a new Hetzner/WAN acceptance claim.
- Each human brings up to **three usable Pokémon** into a tag battle; the full
  private party is retained outside that temporary combat layout.
- **Story progression is still individual:** each player currently needs to
  initiate and win their own trainer encounter for it to count in their game.
  This limitation is accepted for this baseline, not silently treated as shared
  campaign completion.
- Shared wild battles support **privately owned Poké Balls**: each trainer selects
  from their own bag; an executed throw consumes only that trainer's ball. A
  successful catch belongs only to the thrower, with normal nickname/dex handling
  and private party/PC delivery after bilateral battle completion. Trainer
  battles reject bag use; other battle items remain unsupported in co-op.
  Both peers must use the updated **co-op protocol v3** build.
- Local SDK gameplay has verified host catches into both party and full-party PC,
  exact ball ownership, and ordinary save/reload. A follower ownership-encryption
  defect was reproduced and fixed; follower and failed-throw acceptance is still
  in progress on this branch. This is not WAN capture acceptance.
- Six combat Pokémon per human, complete special encounter coverage, and robust
  mid-battle quit/network-loss/rejoin acceptance remain unfinished or pending
  verification. Do not infer them from a build or a successful May encounter.
- PvP and trading remain in the existing client; this baseline promotion does
  not constitute a fresh end-to-end verification of those paths or of Windows.

Track completed slices and remaining acceptance in the
[roadmap](https://github.com/Ayaan-P/emerald-world/issues/5) and
[open issues](https://github.com/Ayaan-P/emerald-world/issues).

## Development checks

The default-branch workflow runs focused protocol/C regressions, a Linux
compile and standalone headless frame/save smoke. It does not certify
end-to-end human multiplayer or WAN recovery.
Locally, the focused checks do not launch game clients:

```sh
PYTHONPATH=.:test/world python3 -m unittest test_coop_catching test_tag_coop test_link_protocol test_link_sessions test_trainer_abort_wire_regression test_link_battle_payloads test_coop_controller_repro -v
```

Keep runtime worlds, saves, invitations, credentials and generated executables
out of commits. Never replace a missing acceptance run with mocked gameplay
results. Preserve the original upstream attribution below.

## Linux multiplayer

Build the native game using [INSTALL_PC.md](INSTALL_PC.md), then run:

```sh
python3 scripts/linux_client.py --check
python3 scripts/linux_client.py
```

The launcher checks Python tkinter, Bubblewrap, Xephyr, SDL2 and the native game.
It does not install dependencies. `--install-user` adds an application-menu entry
pointing to the checkout without copying a game binary or replacing another
launcher.

To join a host, choose **Connect friends**, then **Import friend invitation**.
Only import an invitation received privately from your host. The file supplies
the host address, certificate pin and your trainer identity. Select **Connect
remote TLS**, then return to **Play** and launch your assigned trainer. You can
also prefill the form with `python3 scripts/linux_client.py --invitation FILE`.
Importing a file does not connect or start a game automatically.

Multiplayer saves are kept under `~/.local/share/emerald-world/worlds`, separately
from standalone Emerald saves. Save through the native game menu before closing.
Never commit invitations, save files, private keys or generated connection
configs. The optional AI game master is not required to play.

## Native Emerald port

This is a PC port of Pokémon Emerald, based on the [pret decompilation](https://github.com/pret/pokeemerald).
The PC port was originally made by [NTx86](https://github.com/NTx86/pokeemerald-sdl2pc).


Supported operating systems: Windows, Linux and macOS


To set up the repository, see [INSTALL_PC.md](INSTALL_PC.md).

## Playing

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
fullscreen.

The controls, the window size and fullscreen can be changed in `pokeemerald.ini`, which
the game writes with the defaults when it first starts. It's next to the save file, in
`%APPDATA%\pokeemerald` on Windows, `~/.local/share/pokeemerald` on Linux and
`~/Library/Application Support/pokeemerald` on macOS. If the
folder the game starts in has a `pokeemerald.sav`, where earlier versions saved, both
files are there instead. The game prints where they are when it starts, and
`--save FILE` and `--config FILE` use other files.

SDL knows most controllers. For others, put a `gamecontrollerdb.txt` from
[SDL_GameControllerDB](https://github.com/mdqinc/SDL_GameControllerDB) in the same folder.
