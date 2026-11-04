# Set up the React launcher on Linux

From a current Emerald World checkout with Node.js 20.19+, 22.12+, or 24+ and npm installed, run:

```sh
python3 scripts/setup_react_launcher.py --install-shortcut
```

This installs the locked JavaScript dependencies in `launcher-web`, builds the launcher, and adds a **separate experimental launcher** shortcut for your user. It replaces `launcher-web/node_modules`, as `npm ci` normally does. It does not install system packages, run `sudo`, build the native game, modify saves or deploy a server.

The script reports the native game, Bubblewrap, Xephyr and SDL2 prerequisites. If any are missing, follow [INSTALL_PC.md](../INSTALL_PC.md) to install or build them. A successful launcher build does not guarantee the game will start. A graphical Linux desktop is needed for the game.

To check without building or installing a shortcut:

```sh
python3 scripts/setup_react_launcher.py --check
```

To build without creating a shortcut, omit `--install-shortcut`. Start from the checkout with `python3 -m world.web_launcher`; keep the checkout and Python environment in place. The launcher and shortcut are experimental and do not replace the existing Tk launcher. Save in-game before using **Quit launcher**. Closing the browser tab alone does not stop the local launcher process.
