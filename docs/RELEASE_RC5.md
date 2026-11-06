# Emerald World 0.2.0-rc.5 — Shared Expeditions

Linux x86_64 prerelease. RC4's unfinished engine-replacement experiment is not included.

## Included

- Shared generated caves with custom wildlife and 63×63 outdoor areas using existing Hoenn artwork and Route 101 encounters.
- Persistent generated-area library: one active area at a time; leave before switching, revisit without another model call.
- Integrated co-op, expanded trainer presence/rendering and batched updates through the frozen PR #191 scope.
- Launcher continuation uses the existing local trainer rather than silently defaulting every reopened world to Player. Clearer continuation, saved areas and new-world controls.
- Generated-area entry requires a conscious non-Egg Pokémon, with defensive encounter guards.
- Restart recreates a lost dedicated Xephyr display.
- Chat no longer blocks movement indefinitely because Num Lock is reported held by the nested display.

## Playing

Extract the Linux archive. From the extracted folder, use system Python 3.11 or newer:

```
python3 -I install.py --check
python3 -I install.py
```

Open the installed Emerald World player launcher. Existing source-checkout launchers are not replaced. The package installer preserves its existing worlds and saves; this release does not automatically migrate saves from separate development roots.

For local expeditions, reopen your world with the displayed trainer, then start the game. Choose **CONTINUE** on the native title screen if a save exists. New profiles begin the normal Emerald introduction and must acquire a Pokémon before exploring.

In-game, outdoors/on foot: **START → WORLD → Explore generated area**. Return with **Leave generated area**. Save normally after returning. Closing or restarting discards unsaved progress.

Generating an area is optional and explicitly confirmed; it sends your description to the configured model provider and may incur usage charges. The current authoring adapter requires a supported, logged-in Codex CLI. Playing saved areas does not require a fresh model call. Local hosting ends when the launcher exits; area data persists.

## Evidence and acceptance

The combined native Linux build and production React build succeeded. Earlier focused integration journeys exercised two-client cave combat, return/private saves, outdoor travel, archive activation and host persistence. The user additionally played the release candidate live: generated cave entry/combat/blackout/home respawn; chat after the input fix; a wild Wurmple battle in a new outdoor area and successful menu exit. The user accepted remaining outdoor generation roughness for this prerelease. No broad new gameplay test campaign was run for release cleanup.

## Known limitations

- Outdoor procedural terrain can look rough. No generated art or custom outdoor wildlife.
- One generated area per authority, not simultaneous generated regions. All occupants must leave before replacement/activation.
- Full six-party switching, medicine targeting/consumption and catch-to-storage are unverified in the integrated candidate. They are not claimed as passing; the user accepted proceeding without further checks.
- No Windows release asset, full campaign certification, WAN/load certification or 32-player benchmark for RC5.
- All clients in a session should use this matching RC5 build. No Mega Evolution or expanded National Dex claim.
- Linux requires SDL2, bubblewrap, Xephyr, X11/XWayland, permitted unprivileged user namespaces and system Python 3.11+. See the included manifest and INSTALL.txt.
