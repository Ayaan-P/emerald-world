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

## Readable choices and explicit preview

Matched native clients request `FM VIEW sequence token action` after receiving the existing action offer and whenever the selected action changes. The authority validates the live facing target, sequence/token, revision and expiry without staging any effect. `FM DETAIL` returns printable-ASCII hex for actual target text, public label and authored expected response. Replies fit the existing 512-byte line bound. The bounded native tokenizer accommodates all eight offered actions. Older clients retain their existing offer/use behavior.

Screen one shows the target and readable choice. Enter previews; it does not use the move. Screen two labels the expectation **Authored**, states that no PP is consumed and the move/action becomes public, and offers Enter to use, Left to return or Escape to cancel. No preview success is represented as a committed effect. Native party/position/facing snapshots are checked again on confirmation, and the authority revalidates the original revision through normal use admission.

This applies to shared prop move actions, not local weather, sensing, healing or encounter-profile activation. Descriptions are explicit public authoring, not inference from private state or arbitrary handler execution. Existing generic handlers without descriptions remain usable with a truthful missing-description label. The feature remains behind the existing world-field-moves experimental switch. No battle PP, inventories or saves are changed by previews.

Validation uses actual authority fixtures and a compiled native controller harness. Full linked/rendered UI, real keyboard/controller play and multi-client gameplay remain unverified.

Paired native draft #100: `bd88c0f08e1eea42297130c34b8e5ffbdb123a6c`, based on #99. App ancestry is #451, not RC12 or the reconciled integration candidate. 41 focused authority tests and 10 native host tests pass; linked visual QA is still required.

## Face an object, then find a useful move

With the existing experimental field-moves feature enabled, **Ctrl+M** opens an object-first overlay directly from the overworld. The chat strip advertises the shortcut. Face a shared authored prop first. The host returns its current public text and a bounded set of acceptable move IDs; it receives no party roster, nicknames, HP or learned-move list. The native client matches those requirements against actual learned slots on healthy, non-egg party members. The overlay displays the target and matching party position/move names; Left/Right selects, Enter requests the ordinary action choices for only that selected move. Empty matches and unavailable targets have explicit feedback. No profile-category detour or typed object/action IDs are needed.

Selection is still only inspection: it opens the existing readable target/action preview and separate confirmation. Only that confirmation submits the ordinary revision-bound shared action. The original party/position checks and authority admission remain in force. A changed object may yield different choices or a rejection; discovery is not a reservation. Other visitors can act normally. No run, ready or witness step is introduced, no credit is fabricated, and no PP or save write occurs. The old party-menu path remains available for private field abilities.

Lookup uses additive `FM LOOK` / `FM LOOKED` messages over the existing negotiated field transport, with a 128-byte public move bitset (IDs 1..1023, currently sufficient for the native catalog). Unknown/out-of-range selectors fail closed. The reply stays below the existing 512-byte line bound. Lookup neither mints an action token nor authorizes use. A fresh ordinary `FM GET`, `VIEW` and `USE` transaction follows local selection. Old servers fail or time out safely; old clients retain their existing behavior. Escape, focus loss, movement and disconnect clear or invalidate the overlay; lookup timeout makes no success claim. Escape after submission still cannot undo an already admitted shared effect.

Tests compile and run the actual field controller with the feature enabled and disabled, cover local matching/no match, eggs, changed party/location, malformed replies, timeout/cancel and reuse of explicit GET/VIEW/USE confirmation. Authority tests cover public-only lookup, no deployment/party upload, missing target, stale choices and normal result admission. Shortcut/focus hooks receive source checks only. Full linked SDL rendering, keyboard/controller usability and live two-client presentation remain unverified; this is not a rendered playtest.

Object-first paired native draft #101: `511e4e8e7382f8868ae567653139f1ca0e298f61`, based on #100. App ancestry is #461.
