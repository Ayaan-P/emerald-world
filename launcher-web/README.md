# Emerald World React launcher (experimental)

This is a browser-based Linux launcher backed by the existing Python `DesktopSession`. It does not replace the Tk launcher. A trusted invitation connects to an existing remote world; server-side world creation is not implemented yet.

## Run

1. Complete the Linux game build and runtime prerequisites in `INSTALL_PC.md`, including the native executable and Xephyr.
2. Install Node.js 20.19+ or 22.12+ and npm. From the repository root:

   ```sh
   cd launcher-web
   npm ci
   npm run build
   cd ..
   python3 -m world.web_launcher
   ```

Optionally, after building, run `python3 -m world.web_launcher --install` to add a separate experimental application shortcut for your user. It will not replace an existing shortcut and requires this checkout to remain in place.

The command opens your default browser and listens only on an ephemeral loopback address. Keep the command running while playing. Select a private JSON invitation from a trusted host to join; saved connections appear under Your worlds. Use **Quit launcher** after saving in the game to close its local processes. Closing the browser tab alone does not stop the launcher; use Quit or Ctrl-C in its terminal.

Your save stays on this computer. Under Your worlds, Play offline starts or resumes a separate save, or can make a one-time copy of the online save. Offline progress never merges back online. Close your current session and game first. Forgetting a world removes its saved connection, not its trainer save. Treat invitations as passwords. To use a custom game binary or world storage directory, run `python3 -m world.web_launcher --help`.

## Checks

```sh
python3 -m unittest test.world.test_web_launcher
cd launcher-web && npm test && npm run test:ui && npm run build
```

These checks do not run a real multiplayer session or exercise the native game. A graphical Linux desktop and native prerequisites are required for an end-to-end run. Windows and macOS are not supported by this experimental launcher.
