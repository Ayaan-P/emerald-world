# Co-op full party switching: development draft

This stacked draft explores allowing each trainer to switch among their own six Pokémon while the shared battle engine continues to use three staged slots per trainer. `COOP_FULL_SIX_READY` defaults to 0. Do not enable it in a release candidate until the integrated native build and multiplayer scenarios have been verified.

The battle keeps each trainer's complete party in a private battle-local working copy. Selecting an unstaged Pokémon rotates it into an inactive staging slot, with an owner-authoritative request and a mirror update to the other client. A temporary private six-Pokémon switch view pauses battle controllers, including while its read-only summary screen is open. Defeat participation and knocked-off held-item state are associated with original party identities across rotations. The abort path restores the original party. The protocol uses version 8 only with the development gate enabled; incompatible versions are rejected.

Current limitations and integration checks:

- The gate-on path has isolated C tests and syntax checks, but has not been built or played in the native application. Test both trainers' voluntary and forced switches, simultaneous switching, disconnects, summary navigation, multiple opponents, XP, held items, and save/reload on the combined candidate.
- The gate-off path retains the existing version 7 and three staged slots. Stacked dependencies include the owned-medicine drafts; medicine's reserve selector still covers staged Pokémon only.
- Battle recording is disabled for gate-on co-op battles because the existing recording format does not represent private roster rotations.
- This draft inherits the reserve-medicine string ID coordination issue with the separate Mega draft. Resolve the string table and ID assignment during integration.
- No protocol or isolated test result is a claim of real-network compatibility or multiplayer acceptance.
