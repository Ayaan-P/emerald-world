# RC7 Expansion preview — 0.3.0-rc.7-expansion.1

Experimental Linux x86_64 player package. This is a separate fresh-campaign
Expansion build, not an upgrade/conversion of vanilla RC8 saves. Matching
Expansion clients are required. Existing installations and saves are untouched.

## Included

- Integrated Expansion engine and native world multiplayer, with independent
  trainer profiles, activity consent and rendered peer presence.
- Shared wild battles, deferred owner-private experience and normal field return.
- Engine-aware browser launcher, local host/join, remote invitation preservation,
  separate offline profiles, and an explicit Expansion package manifest/layout.
- Compiler-derived enabled-species catalogue and explicit modern wildlife cohort
  formats; legacy numeric wildlife is not silently reinterpreted.
- Restored original co-op party, roster, bag-selection and presentation contracts.

## Verification and limits

The release evidence file records the exact packaged binary hash and actual
acceptance results. Earlier build26/27 runs completed real two-client shared wins,
modest private EXP, separate normal saves and cold Continue with identity/progress
preserved. These historical runs alone do not validate a different final binary.

This preview is NOT full co-op feature acceptance: capture/medicine ownership,
full-team replacement/rotation edge cases and all NPC trainer paths are not
certified by the basic shared-win journey. A proposed strict-dispatch rewrite was
rejected and excluded after review; it is not silently treated as complete.
Do not expose this experimental world service to untrusted participants.

Normal acquisition of the entire expanded roster, evolution/PC/Dex coverage for
all species, Windows support and a fresh-clone source build are not verified.
The archive contains the selected compiled engine, not a Windows executable.
Some historical unit tests still assert the superseded Python presence-adapter
architecture; no blanket full-suite pass is claimed.

## Run

Extract to a new directory. With system Python 3.11+:

```
python3 -I entry.py --check
python3 -I entry.py
```

Requires SDL2, bubblewrap, Xephyr, X11/XWayland and a browser. No pip/npm install
is needed to play this archive. See INSTALL.txt and manifest.json. The launcher
uses Expansion-specific profiles; do not copy older human saves into them.
Installation/desktop replacement is optional and has not been performed.

Source is on the integrate/rc7 branch. The engine's exact source-only patch
handoff and reconstruction manifest are under docs/attempt-handoffs/rc7/.
Checksums verify bytes, not publisher authenticity.
