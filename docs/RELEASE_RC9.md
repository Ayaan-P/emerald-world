# Emerald World RC9 — Unified Expansion Worlds

RC9 combines the Expansion-native RC7 game with RC8's generated-world systems
in one Linux x86_64 player package. This is a release candidate for fresh
Expansion campaigns with matching clients, not a converter for old vanilla saves.

## Playable release scope

- Native shared-world multiplayer, peer rendering, invitations and ordinary
  battles; tagged co-op battles with private rewards and independent saves.
- Expansion engine, modern species catalogue, HGSS-style Dex and private summary
  detail controls, with the original multiplayer party and action integration.
- Shared 127×127 outdoor exploration, plus agent-editable shared terrain and
  geometry in supported event areas.
- Offline XL authored characters, painted terrain and persistent story journals.
  Offline story graphs are not advertised as synchronized multiplayer XL stories.
- Player guilds, private guild chat, expeditions and notice boards.
- Optional deterministic encounter shuffle. It is OFF by default and currently
  permutes National Dex 1–386; newer species retain their existing behavior.
- Engine-aware browser launcher, correctly matched authority credentials and
  separate trainer/offline profiles. The package selects the Expansion engine
  explicitly and contains no interchangeable vanilla executable.

## Integrity and safety

The larger native map backing buffer uses host memory; fixed GBA memory limits,
relocation/layout checks and battle-script operand checks remain enabled.
The existing compiler-derived Expansion wildlife cohort and CAVE10/11 formats
are preserved; XL exploration negotiates CAVE16 rather than reusing wildlife IDs.

Capture and medicine are implemented gameplay paths, not deliberately disabled
features. The attached evidence states which journeys were exercised; lack of a
separate action-specific run is not a claim that an implemented feature is broken.
Trading additions, playable Kanto and optional world-owned shuffle rules are not
part of this release.

## Run

Extract the archive into a new directory, then use system Python 3.11+:

```
python3 -I entry.py --check
python3 -I entry.py
```

Needs Linux x86_64, glibc 2.35+, SDL2, bubblewrap, Xephyr, X11/XWayland and a
browser. No pip/npm installation is required to play the archive. The new
Expansion library defaults to `~/.ew/x` to leave space for Linux Unix-socket
addresses; existing vanilla libraries are unchanged. See INSTALL.txt
and manifest.json. Do not import or overwrite older human saves. Existing RC8
releases and installed desktop shortcuts are not replaced by downloading RC9.
Windows binaries are not included.

## Source and evidence

The release evidence asset identifies the exact binary and exercised journeys.
The source-only engine patch chain and reconstruction manifest remain under
`docs/attempt-handoffs/rc7/`; CURRENT.md explicitly identifies the RC9 target.
Source reconstruction, local build, gameplay acceptance, CI, release upload and
installed desktop state are distinct facts; no fresh-clone build is implied by
an exact source-tree reconstruction. Checksums verify bytes, not authenticity.
