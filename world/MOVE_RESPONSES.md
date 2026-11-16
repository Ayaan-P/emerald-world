# Reusable learned-move responses

App continuation of #412, native pin unchanged at #74
c727376a85d9a5dedc5207e435d66417d46a01f5. Not RC12 and not Maya's #410/#72.
No native file changes, live providers, player-save changes or new automatic actions.

Existing `world.program_object` and `world.program_network` move requirements now
accept either the existing 1..8 exact IDs or a selector:
`{"types":["water"],"categories":["special"],"exclude":[55]}`.
Types and categories intersect; entries within one list are alternatives. Either
field can be omitted; each accepts 1..3 values. Exclude allows up to8 known static IDs.
The example matches special Water moves except Water Gun, not a prescribed puzzle.

Agents define the actual responses using existing state transitions: alternate
text/appearance, changed available actions, and linked props' collision-checked
one-tile movements. Different move families can trigger different transitions in the
same state; later states can accept different families, letting players/NPCs combine
moves over time. The framework supplies no hardcoded burn/freeze/water behavior or
rewards. Network occupancy, region revision, native admission and player choice guards
remain in force. No ordinary A-button bypass is added.

Player: face an authored prop, party → WORLD MOVE → learned move → matching authored
action → confirm. Matching uses current state and exact offer revision. Compatible
moves from the whole static family appear without authors enumerating each ID. Chat
discovery summarizes selectors instead of flooding hundreds of move names. NPCs use
the same rules but must still have a matching current native individual-move receipt.
Shared #412 feedback and durable move history remain admission-only.

`world.inspect_move_rules` lets agents page matching static metadata in batches of24.
This is not an ownership/learned-move claim. Actual NPC inspection remains separate.

## Metadata and conservative limits
819 standard named native moves have unambiguous literal type/category entries.
21 configuration-dependent entries are excluded from selectors, not guessed. Exact-ID
rules still support them. Move-derived battle type changes (Weather Ball, Hidden Power,
abilities, terrain etc.) are not evaluated: selector means native static type/category.

`scripts/build_move_traits.py` reproducibly extracts metadata only, no donor assets,
from native c727376a85d9a5dedc5207e435d66417d46a01f5:
- include/constants/moves.h blob cca0f09fc3041ecdc4a9a5f968e7b56dc6910a8c
- src/data/moves_info.h blob d75670d7357cbb68f994f36367dd89554b47d539
The current native pin is unchanged. A future engine update must regenerate/review
this catalog before claiming matching selectors. Existing exact-ID programs preserved.

## Verification
Tests cover conservative extraction, invalid selectors, exclusions/category filters,
registered catalog paging, concise discovery, different actual move IDs selecting a
shared response, opposite-family rejection, admission/restart, and actual linked-object
position changes. Existing native/UI/evidence/replay tests remain applicable. These are
component/authority tests, not rendered gameplay or live-model outcomes. Full paired
native visual/save/co-op QA remains with Maya; no new engine build is claimed.
