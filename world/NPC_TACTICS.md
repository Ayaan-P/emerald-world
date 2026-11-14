App child of #397 (01b6e8a79455806dd21f768b64e0eff5b0e00666), paired with native #60
at 7df0f76384a3a34295cc18fb34bebfddf13e68b3. Not RC12-based. Native pin and
unchanged map/species catalog pins advance together; no catalog content changed.
Agents discover world.set_tactics and use a JSON list of preferences, or [] to reset.
The existing public event/plan system supplies context and actual action receipts;
no predetermined arc or automatic learning/victory is implied.

# Optional recurring trainer tactics

Independent child of native #58 at 8db71c37086fec1139f6e0919c1d7a7ca9b9a889.
This does not depend on disabled RFU #59 and does not alter frozen #56 or RC12.
No denied source files are changed.

The paired authority lets a generated character choose composable native AI flags:
setup_first (3), risky (4), seek_two_hit_ko (5), baton_pass (6), hp_aware (8),
field_status (9), prefer_status (12), reserve_ace (15). These bit definitions were
checked against this exact parent's constants/battle_ai.h. Base CHECK_BAD_MOVE,
TRY_TO_FAINT and CHECK_VIABILITY remain enabled. Omniscience, arbitrary flags,
custom executable AI, unfinished stall behavior and party/stat edits are excluded.

Authenticated link transport polls public actor/version/profile configuration every
300 pumps. A bounded BEGIN/ENTRY/END snapshot is staged before replacing the cache.
Malformed profiles clear the cache; profiles expire after 600 pumps without refresh.
Unknown actor/version or unavailable profile uses ordinary basic AI. Current profiles
are copied into the native trainer's aiFlags in WorldCharacter_Prepare, never changed
mid-battle. Canonical trainers do not use that function. Both co-op owner and guest
explicitly reset to basic flags so network encounters do not diverge from cached data.
Native simulation steps still use normal moves, AI scoring and battle rules.

This is optional challenge behavior, not guaranteed particular moves, trained skill,
growth, victories or knowledge of private player moves/items. Strategies are inert
when the actual party lacks relevant moves. Existing rules may affect AI as usual.
The player can inspect public configuration with /guild tactics [ACTOR] in the paired
app and choose the existing optional NPC battle. A fresh session may use basic AI
until the profile arrives; the app's desired profile is not a receipt that a client
has already installed it. No new player-consent prompts or save writes are added.

Native component tests compile the actual parser/cache with fake transport and check
atomic staging, expiry, version mismatch, mask rejection and reset. Hook assertions
check frozen trainer assignment and co-op fallback. These do not run a rendered battle
or prove any particular move choice. Linked/cross-platform and gameplay QA remain.

App verification: 36 tests run, 2 skipped, no failures. The two skips are the
OpenAI/Anthropic fake-provider-to-mechanic integration cases because this environment
cannot start their required sandbox; no isolation bypass was attempted. Other tested
paths include real capability execution/receipt, profile wire output, reset/restart,
rejected masks/actors, exact discovery registry and unchanged map/species catalogs.
Native parser/hook suite: two tests pass. No live provider calls.
