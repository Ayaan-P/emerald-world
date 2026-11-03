# Emerald World (release candidate)

The default `rc` branch contains the multiplayer client and world host. Each
trainer has a separate party, inventory and save. This is an experimental build,
not a complete shared-campaign release. Shared wild and trainer co-op battles
are not implemented.

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
