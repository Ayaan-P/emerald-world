# Model-authored XL interaction graphs

The opt-in existing model author can now turn a theme into an offline XL area with characters and state-dependent dialogue using `python -m world.author_cave 'theme' --xl-events-wilds-output area.bin`. It sends the theme to the configured provider and may incur usage charges. The model returns constrained inert data. Python and native validators check geometry, character positions, text and bounded state transitions; the game runs its fixed interpreter rather than executing model output.

Tests mock the provider and do not call a real model. Native CI attempts to compile a mocked model response, play through the graph in the offline game and check save isolation. This does not verify real model quality, visual appearance, multiplayer or shared state. This draft stacks #216 and its predecessors; the current integration candidate remains separate.
