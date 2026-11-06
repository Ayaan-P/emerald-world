# Emerald World 0.2.0-rc.6

## Inhabited expeditions and interactive adventures

RC6 builds on released RC5. It adds characters to generated outdoor areas and a small interaction system that a director can influence while you play. It does not replace the native battle engine or add a new campaign.

### Choose what you want to play

- **Cave with custom wildlife:** a generated cave with a selected encounter roster and levels.
- **Outdoor wilds:** generated outdoor terrain with existing Hoenn artwork and Route 101 encounters.
- **Outdoor wilds with a guide or cast:** an outdoor area with one guide or up to three characters. They have fixed authored dialogue, not live AI conversation.
- **Interactive adventure:** a director-published area where talking to characters can change later interactions. Select a published adventure in the launcher. The director can also change one trainer's interaction state or dialogue rules during that visit.

The guide/cast generator does not automatically create an interactive adventure. Adventure graphs are authored and published through the existing owner interface. The launcher lists what has actually been published. It does not imply that Luna or another director is currently running, watching the game or generating content automatically.

### Player flow

1. Continue your existing world with its displayed trainer. A new world or new trainer starts a separate save. At the native title screen, choose CONTINUE if you already have a save.
2. In the launcher, select an area or open a published interactive adventure. Only one generated area is active for the world at a time. Everyone must leave it before it can be switched.
3. In the game, go outdoors, get off your Bike or stop Surfing, and have a conscious non-Egg Pokémon. Open START, WORLD, Explore generated area.
4. Face a character and press A to talk. The default keyboard A button is Z. Talking can advance an adventure's conversation state.
5. To return, open START, WORLD, Leave generated area. Save normally after returning. Closing the game discards unsaved progress. There is no claim of automatic saving.

The area and characters stay in the world's saved-area library when persistence is enabled. Your adventure's conversation state is separate: it belongs to your trainer's current visit, is not synchronized with other trainers, and resets on a new visit. Reconnecting to the same area while still inside preserves the local state. There are no durable quest rewards or quest-completion records.

### Director workflow

The owner authors a bounded JSON graph and publishes it with `python3 -m world.wilds_events adventure.json --admin-socket /path/to/admin.sock --name "The Lantern Trail"`. The optional name is what players see in their adventure library. No player-side JSON editing or terminal work is required to select a published adventure. Existing characters, dialogue and graph state are used; the document is data, not executable code.

For an admitted trainer inside the active adventure, `python3 -m world.agent_event_control --help` describes live state/rule changes and status queries. A submission response means queued. Keep its returned connection session and sequence, and query both for the client-reported applied, rejected or unknown result. Do not automatically resend an uncertain command. The game independently validates and defers changes until ordinary gameplay is ready. These commands do not alter terrain, inventory or saved progress.

### Cost and operation

Generating a new cave, outdoor area, guide or cast explicitly sends the theme to the configured model provider and may incur usage charges. It requires the supported, logged-in Codex CLI used by the authoring adapter. A failed attempt can still incur provider usage. The launcher must not automatically retry generation.

Selecting an already published or saved area does not make another model call. Director authors may use a model in their own environment, but compiling/publishing an existing JSON graph does not itself call one. Hosting ends when its launcher exits. Matching RC6 clients are required for the new formats.

### Preserved and polished

RC5's private trainer saves, co-op stack, extended presence, saved-area archive and launcher continuation remain. Its no-Pokémon entry guard, chat Num Lock fix and missing-display restart recovery remain included. RC6 clarifies the existing area/NPC/adventure flows and owner command outcomes rather than adding a director dashboard.

### Evidence and limits

The initial combined WERROR Linux and production React builds passed. A focused real-socket native journey published an explicit graph, entered through WORLD, completed an NPC interaction, applied a live state assignment and rule replacement, observed the changed native transition, and returned to the original field position. Both command queries reported applied. The original seed and disposable save were unchanged. This was one client with controlled authored data, not a live model call, two-player proof or autonomous-GM acceptance.

Known limits remain: rough outdoor generation; at most three authored characters, sixteen interaction states and twenty-four rules; temporary per-trainer adventure state; no generated art, free-form NPC conversation, new reward actions or authored trainer battles. RC5's full six-party rotation, medicine and catch-to-storage acceptance gaps are not claimed resolved. No new Windows, WAN/load or full-campaign certification is claimed. RC6 remains a local candidate until explicitly published.
