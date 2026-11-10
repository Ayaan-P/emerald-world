# Character-initiated optional Match Calls

Existing Wally and Steven authors may retain `call: {id, text}` alongside their
normal evidence-grounded goals. IDs are stable lowercase identifiers (24 chars);
text is literal and bounded to 160 characters. New content needs a new ID. No
fixed story arc ships, and there is no request naming a real player or exposing
private interaction history to the shared character author.

A connected native client checks for calls about once a minute while in ordinary
field play. Only its already registered Wally/Steven contact mask is requested.
The authority offers a current authored call at most once automatically per
trainer/save/actor/request, with a ten-minute cross-actor interval. A reconnect
never automatically rings the same request again. Thirty-two retained requests
per actor/save bound the ledger. Busy field states do not receive offers.

The actual existing incoming Match Call machinery rings at a safe allowed-map
step. Original random, scripted and story calls retain priority. The player sees
who is calling and chooses A to answer or B to decline. Answer uses the real call
window; decline hangs up without consuming a player story choice. Original game
calls still behave normally. Undelivered native offers expire after two minutes;
window allocation failures release the custom call's field lock and record a
miss, not a player refusal. No follower, transport, inventory or save-format
change is involved.

`/history calls off` persists quiet mode for this trainer/save (not ordinary game
calls); `on` enables invitations. `/history calls` distinguishes acknowledged
local settings from an unconfirmed saved setting. `/history calls check` explicitly
reconnects to a current missed or declined request, even in quiet mode. Already
answered requests do not repeat. Normal outgoing PokéNav contacts remain usable.
Older authorities safely refuse optional RING/RSET/RACK, with no chat fallback.

Delivery records and answer/decline/missed dispositions are private authority
state. Nothing enters public world history, inferred friendship or relationship
credit. An answer is a button choice, not proof that text was read. Lost disposition
packets are not retried automatically; a manually requested check can recover an
unacknowledged offer. Native registration is client attestation under the existing
game trust model, not anti-cheat verification.

Tests cover real authored action, authenticated wire, different recipients/saves,
quiet mode, cadence, explicit reconnection, restart, failed/reused request IDs,
production native parser, original-call priority, A/B handling and custom failure
cleanup. Engine window/task APIs are explicit doubles. Full linked ringing,
rendering, sound, safe-point timing and original-story-call QA remain Maya's gate.
