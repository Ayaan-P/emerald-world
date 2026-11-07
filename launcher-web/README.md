# Emerald World React launcher (experimental)

The Linux browser launcher manages native game sessions, local worlds, dedicated-hosted worlds and separate offline saves. It uses the Python `DesktopSession`; the game runs in its own native window. The Tk launcher remains an operator fallback.

**Play** separates Local and Hosted. **Local worlds** lists local authorities and solo saves. **Hosted worlds** joins private player invitations or manages an owner account. A configured management service is required for owner actions; a standalone dedicated server can still be joined with its player invitation. The launcher does not deploy Hetzner or enable local Internet sharing.

**Explore** opens a local world's generated-area library. Cave and outdoor generation is shown only when supported by that host. Generation requires a supported signed-in model CLI and explicit cost confirmation. Saved areas do not make a model call. Native entry is START → WORLD → Explore generated area, outdoors on foot with a conscious non-Egg Pokémon.

Closing a game, disconnecting a session and stopping a host are separate operations. Disconnect leaves owned local hosts running, and they remain visible under Local worlds. Stop host requires confirmation and affects only that local world. Quit closes this launcher's games and owned hosts; it does not stop remote servers.

For a guided one-command frontend setup and optional application shortcut, see [React launcher setup](../docs/REACT_LAUNCHER_SETUP.md).

## Run

1. Obtain the matching native binary and runtime prerequisites, including Xephyr. RC9 uses Expansion; the source vanilla game requires `--engine vanilla` and its own binary. Use the packaged RC9 launcher for the packaged game.
2. Install Node.js 20.19+ or 22.12+ and npm. From the repository root:

   ```sh
   cd launcher-web
   npm ci
   npm run build
   cd ..
   python3 -m world.web_launcher --engine expansion-native --binary /absolute/path/to/pokeemerald-native
   ```

Optionally, after building, run `python3 -m world.web_launcher --install` to add a separate experimental application shortcut for your user. It will not replace an existing shortcut and requires this checkout to remain in place.

The command opens your default browser and listens only on an ephemeral loopback address. Keep the command running while playing. Select a private JSON invitation from a trusted host, drop the file, or paste its JSON, then choose **Join and play**. The launcher connects and opens the game in its own window. Saved worlds have a direct Play action; creating a hosted world also offers Create and play or Create only. Switching worlds asks before closing a running game. Saved connections can be named, searched and favorited locally. Use **Quit launcher** after saving in the game to close its local processes. Closing the browser tab alone does not stop the launcher; use Quit or Ctrl-C in its terminal.

When the online game is running, the launcher can show connection status and nearby trainers from fresh local game telemetry; it does not claim to list everyone on the server. Use **New solo save** to start a separate offline adventure without an invitation. You can optionally import a copy of a local save file up to 128 KiB; the original file is not changed. Save compatibility is not validated by the launcher. Previously created offline profiles appear under Local worlds → Solo saves, including after a saved connection is forgotten. Your save stays on this computer. Under Hosted worlds, Play offline starts or resumes a separate save, or can make a one-time copy of the online save. Offline progress never merges back online. Close your current session and game first. Forgetting a world removes its saved connection, not its trainer save. Treat invitations as passwords. To use a custom game binary or world storage directory, run `python3 -m world.web_launcher --help`.

## Checks

```sh
python3 -m unittest test.world.test_hosting_ui test.world.test_hosting_ui_contract test.world.test_web_launcher
cd launcher-web && npm test && npm run test:ui && npm run build
```

These checks do not run a real multiplayer session or exercise the native game. A graphical Linux desktop and native prerequisites are required for an end-to-end run. Windows and macOS are not supported by this experimental launcher.

Hosted worlds use a private HOST ACCESS file to enroll an owner account. A host owner can create and resume worlds and download one-trainer join invitations. World-join invitations are private credentials: share them through a trusted channel. A pending creation is retried with the same request ID to avoid duplicate worlds after an uncertain result. The existing single-world service is not modified by this launcher.

If the separate hosted-profile backup module is installed, **Back up account** downloads a private owner credential and **Restore account** imports it on another device. Treat this file like a password: it grants control of hosted worlds. Downloads may be readable according to your browser and folder permissions; move the file to encrypted private storage. Restoring does not back up player saves or verify the server is reachable.
