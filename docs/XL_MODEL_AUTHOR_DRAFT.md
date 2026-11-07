# Model-authored XL wilderness draft

The existing, opt-in model author can now turn a theme into a validated 127×127 outdoor blueprint with `python -m world.author_cave 'theme' --xl-wilds-output area.bin`. The resulting file can be loaded by the offline XL runtime from #210. Existing modes and the default preview remain unchanged. The compiler independently checks the shape, coordinates, connectedness and fixed entrance/exit and never executes model output as code.

This command sends the theme to the configured model provider and may incur usage charges. It runs only when explicitly invoked, uses the existing locked-down tool-disabled model adapter, and does not publish a map or overwrite a file. Tests use a mock provider, not a real model. It does not add XL characters, encounter authoring, or online publication; the integration stack remains separate.
