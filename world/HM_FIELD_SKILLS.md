# Optional HM field skills: paired draft

App base: #392 at `b13d423ace2294a71ec69185b15d93cdfcea0463`.
Native pair: [#57](https://github.com/Ayaan-P/pokeemerald-expansion-native/pull/57)
at `84ec1023888b616f163b9e1b82e60450cb07639a`, based on frozen #56
`739be20ecf1101f84cc2fb272587978350955b6d`.
This separate branch updates its own build pin; it changes neither #384/#56
nor Maya's integration. It is not based on the released RC12 pair.

## Player path

Build the pinned native pair with the existing build procedure, start the
world normally, then explicitly opt in for this player's process:

    python -m world.launcher --state-dir /path/to/world join Ash --engine expansion-native --field-skills --display :93

The `offline` launcher subcommand also accepts `--field-skills`. Existing
online/offline profile separation, locks and sandbox mounts remain unchanged.
Omit the option to retain default behavior. It is not a shared world rule,
save setting or permission for other trainers. Older native binaries reject
the unknown option instead of silently pretending to support it.

Open the ordinary party menu, select a Pokémon, then FIELD SKILLS. Four skills
fit per page with NEXT/PREVIOUS/BACK; B goes back. Cut, Fly, Surf, Strength,
Flash, Rock Smash, Waterfall and Dive do not need to occupy battle moveslots
when this player owns the correct HM, has the existing required badge and
the selected non-Egg Pokémon can learn the move. Contextual Surf and scripted
HM checks use the same eligibility. Learned moves retain stock behavior,
including learned non-HM skills. Native map/link/location checks and the actual
field-effect animations/callbacks are not replaced.

This adds no bag contents, badges, PP or battle moves and does not modify
another player's save. The field effect itself still makes the ordinary game
change, such as cutting a tree. No agent can grant the option, invent a badge
or declare a field effect complete. No provider is called.

The native party UI is implemented. The browser/Tk launcher has no new
checkbox yet; explicit command-line launch or
`ExpansionSession.start(..., field_skills=True)` is required.

## Validation

The paired native `tests/test_field_skills.py` runs four component tests with
the real eligibility/parser code and extracted real paging callbacks. It is
not a linked/rendered playtest. App `test_field_skills_launch` checks default,
opt-in, offline/online CLI routing, strict types and unchanged command/mount
construction. Broader native acceptance for all eight real effects, page
rendering, cancellation, transitions, save/reload and co-op remains required.

The source research rejected duplicate imports of DexNav and followers:
followers already exist in #56 through the `pokemon_follower` world rule.
The discarded follower experiment is not part of this branch. No new donor
assets or code are copied. Fan design references:
https://www.reddit.com/r/PokemonROMhacks/comments/1dyg2zf
https://www.reddit.com/r/PokemonROMhacks/comments/1uioov8/pokemon_project_pi_update_v_12_final/

The resident-site and encounter-trait catalog pins are carried forward to #57: its complete 11-file diff changes only field-skill code/UI/options and tests, not any catalog source inputs, maps, tilesets or species data. Exact-pin validation remains enabled.
