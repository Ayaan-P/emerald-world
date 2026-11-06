# Model-authored XL characters draft

The opt-in existing model author can generate an offline XL outdoor blueprint with up to three characters, including their positions, appearance and dialogue: `python -m world.author_cave 'theme' --xl-cast-wilds-output area.bin`. The tool sends the theme to the configured model provider and may incur usage charges. The tool-disabled model returns bounded data, not executable code. The compiler and native runtime independently validate the geometry, positions, protected entry and exit, dialogue, connectivity and reachability.

Tests mock the provider: no real model call has been made. The native CI attempts to compile a mocked model response into a map and interact with its characters in an offline game. It does not demonstrate a real model's output, visual quality or shared multiplayer support. This draft stacks on #214, #213 and their predecessors; integration with the current release candidate remains separate.
