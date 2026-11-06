# Offline generated outdoor casts (experimental)

An opt-in 63×63 outdoor template can contain one to three native characters. The authoring adapter accepts a model-proposed terrain blueprint and a small cast with boy/girl sprites and one or two short lines of inert, validated text per character. NPC positions are fixed, and the terrain compiler connects all walkable land while keeping the characters from blocking passage. The native loader independently validates geometry, positions, text, and canonical encoding before staging it.

Build with `GENERATED_MAP_READY=1 GENERATED_MAP_AUTOTILE=1 GENERATED_MAP_LARGE=1 GENERATED_MAP_WILDS=1 GENERATED_WILDS_GUIDE=1 GENERATED_WILDS_CAST=1`. Run `python -m world.author_cave 'theme' --cast-wilds-output area.bin` and launch the native game with `--generated-map area.bin`. The theme is transmitted to the configured model provider and usage may incur charges. The output path must not already exist.

This is an offline-only first slice. It does not add shared cast synchronization, quests, battles, generated artwork, or dynamic character behavior. No real model-provider call or multiplayer session is exercised by its automated tests. Existing multiplayer clients reject this format rather than treating it as a shared area.
