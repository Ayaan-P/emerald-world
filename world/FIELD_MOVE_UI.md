# Party-menu world moves (experimental)

This builds on #409/native #71. With `--development --experimental-field-moves`, face an already-authored shared object and open the normal party menu. Choose a conscious Pokémon, WORLD MOVE, and one of its actual learned moves. Back/cancel leaves the party unchanged.

The party screen closes normally. The client asks the server which current actions on the facing object accept that move. A five-line in-game overlay names the move and explains that the move/action is shared with world players. Left/Right selects an action, Enter confirms, and Escape closes. No command typing is needed for this path. The action selector currently uses keyboard keys, not a newly implemented controller UI.

Only explicit confirmation submits an effect. The server reuses the existing facing/revision/token checks and authoritative prop/network executor. The overlay waits for a committed result. Only an affirmative result can trigger the stock neutral sparkle at the original facing tile. This is local success feedback, not a move-specific attack animation or a remote broadcast effect. Other players see the already-supported synchronized object state/position changes.

## Safety and compatibility

Default off. Vanilla party behavior remains unchanged when off. When enabled, stock learned field moves are grouped under the existing paged Field Skills entry to retain the eight-action parent menu bound; the separate optional HM compatibility rule is not enabled implicitly. The new submenu reads actual learned move slots.

Party, trainer ID, map, tile and facing are captured and rechecked before submission. Changed context, unavailable objects, disconnects and bounded timeouts do not submit a replacement or retry. Escape before confirmation abandons the interaction. Escape after confirmation closes the overlay only: an already submitted effect may still commit. No result is inferred from connection closure or a missing ACK. A committed effect remains in authority history even if the client never receives its acknowledgement.

The FM request/result protocol runs on the existing authenticated trainer-bound link channel. Requests negotiate current compatible actions; no full party is transmitted. The server still labels learned-move evidence as client-reported, not independently verified. No PP, Pokémon or player-save writes, provider calls, new story flags or fabricated NPC responses occur.

No denied `world_bridge.c` change or replacement is included. Native additions use the existing party-menu, link transport, overlay and stock field-effect seams. Maya's frozen #384/#56 and RC12 are untouched. This separate draft follows #409/#71 and is not RC12-based.

## Validation limits

Compiled native controller fixtures exercise feature off/on, choosing/confirming, exact response sequencing, no feedback before commitment, no repeated success effect, changed party/position, timeout and cancellation. Source checks verify real party-menu/overlay/transport hooks and absence of a bridge-file edit. Authority tests exercise the actual authenticated channel binding, offer selection, stale facing, replay, successful admission and failed-admission result.

These checks do not substitute for a complete linked native build or rendered playtest. Actual party-menu layout, return-to-field behavior, keyboard release handling, sparkle allocation/palette behavior, save coexistence and live two-client presentation still require Maya's QA. No live model was used.
