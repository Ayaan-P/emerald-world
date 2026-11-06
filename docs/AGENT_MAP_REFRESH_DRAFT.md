# Offline agent map refresh

The existing opt-in model author accepts `--replace-output` alongside an offline output path. It validates the generated map first, writes a private temporary file in the same directory and atomically replaces the existing regular file. The target must already exist and cannot be a symlink. The default remains exclusive creation. Output is reloaded by the existing offline game when the player next enters the generated area; the current area does not change while occupied. This is not live multiplayer editing.

The provider receives the supplied theme and may charge when the model-author command is invoked. Tests mock the provider. The native CI attempts to run the game continuously across an offline map replacement, re-enter and interact with a new character, and confirm the save remains unchanged. Until that CI passes, actual game reload is unverified. This stacks #217 and its predecessors; integration is separate.
