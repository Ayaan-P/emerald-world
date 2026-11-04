# Emerald World React launcher (experimental)

This is a browser-based Linux launcher backed by the existing Python `DesktopSession`. It does not replace the Tk launcher. A trusted invitation connects to a remote world. Hosted-world creation, account enrollment, and friend invites activate only when the hosted-world backend from PR #136 is installed and its separate management service has been configured. The current existing single-world deployment does not itself provide this management API.

For a guided one-command frontend setup and optional application shortcut, see [React launcher setup](../docs/REACT_LAUNCHER_SETUP.md).

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

The command opens your default browser and listens only on an ephemeral loopback address. Keep the command running while playing. Select a private JSON invitation from a trusted host, drop the file, or paste its JSON, then choose **Join and play**. The launcher connects and opens the game in its own window. Saved worlds have a direct Play action; creating a hosted world also offers Create and play or Create only. Switching worlds asks before closing a running game. Saved connections can be named, searched and favorited locally. Use **Quit launcher** after saving in the game to close its local processes. Closing the browser tab alone does not stop the launcher; use Quit or Ctrl-C in its terminal.

When the online game is running, the launcher can show connection status and nearby trainers from fresh local game telemetry; it does not claim to list everyone on the server. Use **Play solo** to start a separate offline adventure without an invitation. You can optionally import a copy of a local save file up to 128 KiB; the original file is not changed. Save compatibility is not validated by the launcher. Previously created offline profiles appear under Solo adventures, including after a saved connection is forgotten. Your save stays on this computer. Under Your worlds, Play offline starts or resumes a separate save, or can make a one-time copy of the online save. Offline progress never merges back online. Close your current session and game first. Forgetting a world removes its saved connection, not its trainer save. Treat invitations as passwords. To use a custom game binary or world storage directory, run `python3 -m world.web_launcher --help`.

## Checks

```sh
python3 -m unittest test.world.test_hosting_ui test.world.test_hosting_ui_contract test.world.test_web_launcher
cd launcher-web && npm test && npm run test:ui && npm run build
```

These checks do not run a real multiplayer session or exercise the native game. A graphical Linux desktop and native prerequisites are required for an end-to-end run. Windows and macOS are not supported by this experimental launcher.

Hosted worlds use a private HOST ACCESS file to enroll an owner account. A host owner can create and resume worlds and download one-trainer join invitations. World-join invitations are private credentials: share them through a trusted channel. A pending creation is retried with the same request ID to avoid duplicate worlds after an uncertain result. The existing single-world service is not modified by this launcher.

If the separate hosted-profile backup module from PR #137 is installed, **Back up account** downloads a private owner credential and **Restore account** imports it on another device. Treat this file like a password: it grants control of hosted worlds. Downloads may be readable according to your browser and folder permissions; move the file to encrypted private storage. Restoring does not back up player saves or verify the server is reachable.
