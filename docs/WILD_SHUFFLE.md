# Wild shuffle

Wild shuffle is an opt-in adventure mode. Open WORLD > Wild shuffle, turn it on, and choose one of 20 numbered seeds. Ordinary grass, water, Rock Smash and fishing encounter-table species are mapped through a deterministic one-to-one shuffle of the original 386 National Dex species. Levels, encounter rates and the ordinary battle/catch flow remain unchanged. It does not consume the game's normal random-number stream.

Two players who choose the same seed get the same species mapping, not necessarily the same individual encounter or timing. A shared battle continues to use the existing encounter-owner flow; no multiplayer synchronization or compatibility proof is implied. Each player chooses their own mode and seed. The mode is off and seed 1 on each fresh game process; settings are session-only and do not alter trainer saves. Choose the seed again after restarting.

The mapping uses canonical National Dex numbers instead of engine-specific internal species IDs. Both engines expose conversion functions; this is intended to make the shuffle reusable for the Expansion version, but no Expansion integration or gameplay test has been performed. Expansion-only species and forms are outside this first 386-species pool.

Scripted encounters, roaming Pokémon, mass outbreaks, DexNav's deliberate hunts, generated areas and Battle Frontier facilities are excluded. The Route 119 special Feebas path is also unchanged. Type-attracting abilities still select a slot using its original encounter table before the species is shuffled, and DexNav's displayed wild tables are not rewritten. This is a wild-species shuffle, not a trainer, starter, item or move randomizer.

This mode changes gameplay only after it is enabled. Caught Pokémon remain ordinary Pokémon in the player's independent save. Disable it before relying on vanilla encounter locations.
