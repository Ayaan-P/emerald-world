# Expansion world rebuild

This is a fresh native Expansion-based game, with the existing World project serving as the reference for what to rebuild. The first slice implements shared-world presence against the existing server's SOCIAL protocol. It does not replace the current game or deploy a server.

The overlay is new game-side code. It uses Expansion virtual sprites rather than allocating persistent object events for remote trainers. An applier checks the pinned native Expansion revision and requires a clean checkout before adding the overlay and a small main-loop hook. With no World configuration the native game runs without enabling presence. Linux is the first target; the Windows presence implementation is not yet built.

Map identities are enabled only where the name and numeric group/map match the existing World catalog. That is not a guarantee that map geometry matches. In particular, the original generated-world map IDs collide with Expansion maps and are intentionally excluded. Generated worlds, multiplayer battles, trading, saves migration and the rest of the previous game's features are future work.

The wire parser is tested against a real server snapshot without sockets, and the CI build runs the Expansion opening replay without a World connection. Actual two-client communication, visual presence, and save safety have not yet been validated in a running multiplayer session. Use disposable saves for experiments.

To build from a clean checkout, first check out `uehlbran/pokeemerald-expansion-native` at commit `bb3fd057061cdd7e6a9e79b76abb41924ee44ecc` into `engines/expansion-native`, then run:

    python3 rebuild/scripts/apply.py engines/expansion-native
    cd engines/expansion-native
    make -f ../../rebuild/expansion.mk -j2 native BITS=64

The applier modifies the donor checkout; use a separate disposable checkout rather than an existing working tree. It refuses to apply to a dirty checkout or overwrite donor files.
