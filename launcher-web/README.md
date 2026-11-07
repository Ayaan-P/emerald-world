# Emerald World React launcher (experimental)

The Linux browser launcher manages native game sessions, local worlds, dedicated-hosted worlds and separate offline saves. It uses the Python `DesktopSession`; the game runs in its own native window. The Tk launcher remains an operator fallback.

**Play** separates Local and Hosted. **Local worlds** lists local authorities and solo saves. **Hosted worlds** joins private player invitations or manages an owner account. A configured management service is required for owner actions; a standalone dedicated server can still be joined with its player invitation. The launcher does not deploy Hetzner or configure Internet routing.

**Explore** opens a local world's generated-area library. Cave and outdoor generation is shown only when supported by that host. Generation requires a supported signed-in model CLI and explicit cost confirmation. Saved areas do not make a model call. Native entry is START → WORLD → Explore generated area, outdoors on foot with a conscious non-Egg Pokémon.

**Area library** searches saved names and filters caves, outdoors and published adventures. Preview map reads the selected local world’s validated archive without activating it or making a model call. The zoomable schematic shows the stored base layout, entrance, exit and fixed character positions. It does not show live terrain edits, player positions, dialogue or story progress. Custom wildlife lists the stored species and levels using the archive’s actual Vanilla or Expansion catalogue, not guessed encounter chances. A preview is not a compatibility or live-play check.

Saved areas appear before the generator. Switching still requires review, and the authority rejects replacement while anyone is inside. Closing a preview, changing worlds or receiving an obsolete response cannot activate an area. The archive is owner-local only; this does not add remote server browsing or a new generation format.

**Explore → active interactive adventure → Edit terrain** opens the existing durable 63×63 geometry system. Paint grass, tall grass or blocked water, restore individual cells, undo drafts or restore the base layout. This is not available for caves, fixed-dialogue areas or XL worlds. The map shows the stored shared overlay, not per-trainer temporary overrides or proof of native rendering.

Review validates the complete proposed overlay using the authority’s connectivity and protected-cell checks. Apply requires an explicit confirmation, the exact reviewed revision, and no connected players anywhere in the world. Save and close all games first; this editor never disconnects anyone. The stricter empty-world gate avoids exposing the existing geometry entry/return race through this UI. Checking the revision and committing through the existing authority share its lock. Changes persist in the local world, with at most 512 overrides. Matching geometry-capable clients are required, including large-overlay support above 64 cells.

An uncertain save requires reload before another edit. Unapplied edits are guarded on navigation and tab close. Draft overlay JSON uses the existing `shared_terrain_control --geometry --replace --tiles-file` format for authorized owner workflows. The editor does not add remote hosted editing, new terrain/art, runtime settings or a new multiplayer protocol. Rejoin to inspect the result in-game; a stored revision is not proof of client application.

Closing a game, disconnecting a session and stopping a host are separate operations. Disconnect leaves owned local hosts running, and they remain visible under Local worlds. Stop host requires confirmation and affects only that local world. Quit closes this launcher's games and owned hosts; it does not stop remote servers.

**Local worlds → Invite friends** exposes the existing local TLS sharing flow. Open the host without starting the game, enter a numeric listen address and port, then review before enabling it. The default is loopback, so nothing becomes remotely reachable automatically. For LAN play, use this computer's LAN address and an address your friend can reach. Router/firewall/relay setup is not automated, and an active listener is not proof of Internet reachability. TLS identity creation requires OpenSSL; an existing world identity is reused.

Create a separate trainer profile per player and review the advertised endpoint and fingerprint before creating its private invitation. The file grants reusable access to the named trainer, unlike the hosted service's redeemable invitations. Existing-trainer export must be selected explicitly and never rotates or revokes older credentials. Confirm the fingerprint separately and send the file through a trusted channel. Nothing is sent automatically. Browser downloads may have ordinary folder permissions; store invitations privately.

Disconnect leaves the local TLS listener running, including when another world is selected. Reopen its host to manage sharing. Stop sharing disconnects its TLS friends but leaves the authority and local game running. Stop host or Quit also closes sharing. An uncertain export may already have created the trainer: refresh, then explicitly review an existing-trainer export to recover access. No automatic retries occur.

**World options** is under each Local worlds entry. Open the host without launching the game, edit a draft, then review and apply. A running background host can be edited without changing your selected session. All players must leave before applying changes. No one is disconnected automatically. Loading options never changes existing worlds. Display and key bindings remain personal native settings, applied when the game starts.

**Settings → Display & controls** edits existing Expansion trainer profiles. Choose the world or solo profile, change window scale, fullscreen or keyboard buttons, then save with that trainer's game closed. These are real startup options in the profile's `settings.ini` under the game's `--data-dir`, not the legacy vanilla `pokeemerald.ini`. The launcher leaves that legacy file alone. Defaults are loaded without creating a file; Use defaults only changes the draft. F1 shows the bindings active in the running game.

Only explicitly changed display/keyboard fields are rewritten. Unrelated settings and comments remain, including controller and fast-forward settings. Custom SDL keys outside the editor's offered set remain unchanged unless replaced. Existing world/profile locks prevent writing while another game or launcher holds the profile. File revision checks reject stale drafts. Atomic replacement uses a private temporary file, refuses symlinks/nonregular files and retains the native 16 KiB limit. No trainer save, account credential, gameplay flag or shared world rule is edited.

The editor connects to the existing world-rules version-one authority: wild shuffle on/off and seed 1–20. It requires the world-rules host and matching native-client update; older RC9 hosts show an unavailable state. This UI does not install the authority or change game eligibility. Hosted owner services do not yet expose world-options editing. Additional RC10 categories and Expansion playground remain unavailable until they have matching host and runtime support.

### World-options integration

- The bridge reads existing owned authorities under their lock. It never constructs `WorldRules`, migrates a database, or writes a trainer save. A detached local authority remains owned by the launcher.
- Applying sends the existing private admin command `world_rules`, action `replace`, complete `rules`, and `expected_revision`. The authority retains the atomic zero-player and revision checks. Browser requests cannot supply an admin path or target a saved remote connection.
- The UI accepts only the verified version-one schema. Unknown fields or versions fail closed rather than dropping options. Polling preserves drafts, conflicting revisions require reload, and an unconfirmed write is never retried automatically.
- Extending RC10 needs a versioned gameplay schema with authoritative supported values/defaults, a backend-defined preset and its exact change preview, persistence/admission semantics, and an authenticated owner API for hosted worlds. Distinguish whether a world allows a system, whether its matching build supports it, and whether a trainer is eligible. Do not turn compile-time flags into launcher toggles.
- Keep the existing world's rules unless its owner explicitly reviews and applies changes. Personal native startup settings and save-local game options are separate from shared gameplay rules.

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
python3 -m unittest test.world.test_hosting_ui test.world.test_hosting_ui_contract test.world.test_web_launcher test.world.test_rules_ui test.world.test_personal_settings test.world.test_local_sharing_ui test.world.test_area_library_ui test.world.test_terrain_ui
cd launcher-web && npm test && npm run test:ui && npm run build
```

These checks do not run a real multiplayer session or exercise the native game. A graphical Linux desktop and native prerequisites are required for an end-to-end run. Windows and macOS are not supported by this experimental launcher.

The local-sharing suite uses actual session invitation files and in-memory trainer identities, with the TLS broker substituted and socket creation blocked. It does not test a live TLS connection, certificate creation, WAN reachability or native multiplayer.

The world-options suite mocks transport and never opens sockets. Its optional compatibility cases exercise the actual world-rules authority in memory when that backend is integrated; they are explicitly skipped on branches without it.

Hosted worlds use a private HOST ACCESS file to enroll an owner account. A host owner can create and resume worlds and download one-trainer join invitations. World-join invitations are private credentials: share them through a trusted channel. A pending creation is retried with the same request ID to avoid duplicate worlds after an uncertain result. The existing single-world service is not modified by this launcher.

If the separate hosted-profile backup module is installed, **Back up account** downloads a private owner credential and **Restore account** imports it on another device. Treat this file like a password: it grants control of hosted worlds. Downloads may be readable according to your browser and folder permissions; move the file to encrypted private storage. Restoring does not back up player saves or verify the server is reachable.
