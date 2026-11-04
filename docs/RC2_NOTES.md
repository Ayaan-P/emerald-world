# Next Linux candidate: multiplayer and party-preparation batch

This is progress toward the wider roadmap, not a claim of full parity. It preserves the installable hosted-world product from RC1.

## Player changes in this batch

- Launcher status refreshes are serialized and have timeout/retry recovery. Solo trainer names are checked before launch. Dialog focus is retained during requests and initialized when an open dialog changes identity.
- The in-page game view captures a user-selected window locally and relays supported keyboard keys only to the dedicated game display. Preview requests carry independent ownership so late cleanup cannot stop a newer view. It is a window-sharing view of the native engine, not a WASM port; native-window play remains available.
- Native room/private chat and a Friends menu are integrated. Friends use a separate authenticated cross-map roster, not the limited same-map render slots. Fly still requires the player's own earned badge, a party member knowing Fly, a personally visited destination, safe field state, fresh friend information and a clear landing; cancellation/fallback must not grant progress.
- Gym/League guest participation does not consume the guest's boss, award their badge, or resume the owner's progression script. Ordinary shared trainer credit remains supported.
- Read-only Summary detail exposes local Pokémon IVs, EVs and stock Hidden Power type/power. No EV migration, stat recalculation, save-format change or private opponent-party export is introduced.
- Native Party auto-heal is being integrated as the remaining part of this batch. It must consume applicable owned medicine rather than invent items, and must not revive fainted Pokémon or operate inside an unsafe shared/battle context.

## Honest remaining scope

This batch does not complete story rallies/return recovery, public-only battle spectating, host milestone catch-up, team loadouts, global Exp Share, new EV rules, Bag search, expanded Dex content, or cosmetic/follower systems. Source-level implementation is not native acceptance. Window selection, earned-Fly gameplay, full campaign, adverse-network behavior and Windows runtime coverage must never be inferred from simulated component/eligibility checks.

Full native CI scenarios are manual dispatches rather than three extra game runs for every PR; the normal component and baseline checks remain enabled. The old chat PR's hosted-runner native job failed before building because Bubblewrap could not configure the isolated loopback device (`RTM_NEWADDR: Operation not permitted`). That is not a native gameplay pass, and the sandbox is not weakened to bypass it. The combined local RC run is the native release evidence.

Validation belongs to one frozen integrated candidate. Existing focused regressions, frontend build, native build and bounded disposable native/package flows are collected together; Windows play remains friend-owned. Publication notes must distinguish the actual results from unexercised paths.
