# Optional live battle spectating

Friends can follow an ordinary Emerald fight while keeping their own game control. This is a read-only native panel of the active Pokémon's species (long names abbreviated), level and current/maximum HP, not mirrored battle animations, a replay, remote input or synchronized battles.

## Player entry

On the matched client, Ctrl+V toggles the spectator panel in the native chat strip. Ctrl+T opens commands:

- `/watch share`: allow authenticated players in this world to view your active battlers for this connected session. Sharing is off initially and capture starts only after the server acknowledges. It can include spoilers about currently active opponents.
- `/watch list`: list trainers who have enabled sharing.
- `/watch view NAME`: subscribe to that trainer's current connection. Open Ctrl+V to read the panel.
- `/watch stop`: stop your capture immediately and queue withdrawal to the server. Already queued/sent frames cannot be recalled.
- `/watch off`: unsubscribe from another trainer.

The panel does not stop your own overworld or battle input. Watching is allowed from elsewhere in the world, so friends can explore independently while following a major fight. Closing the panel does not unsubscribe or stop sharing; use the explicit commands. Disconnect clears both. There is no automatic sharing on a new session or automatic subscription to a reconnected name.

## What is real and what is private

The native frame hook reads actual active `gBattleMons`, side, level and HP at up to five updates per second. Absent battlers are skipped; invalid rows and ended battles produce an empty view. It sends no bench, nicknames, moves, items, personality, ownership IDs or save paths. No result is asserted, no outcome is credited, and no character grows from a spectator packet. Frames are client-attested, not anti-cheat evidence. Unsupported species/ranges reject and turn off that stream safely.

Authority buffers live frames only in the exact connection. Subscriptions relay them only to explicit viewers; other peers receive none. `/watch list` reveals only the names of currently opted-in sharers. Data is not saved to SQLite, public world history, model author context or native telemetry JSON. A world server still handles the transport, and already received information cannot be revoked. Stale streams become a waiting message after two seconds. Disconnect/withdrawal ends the subscription. Session sharing can be enabled again deliberately.

WATCH1 is the outermost capability and first fallback. Commands are intercepted locally and use dedicated wire messages; they never fall through into public chat on legacy servers. Old clients/servers cannot use this UI. New clients require fresh complete snapshots; they clear stale rows instead of retaining a frozen alleged battle.

## Verification and integration

App follows #367 443509e3c2e6a3f96d23dce1b76d8025524a57cf. Matching native #55 babbe0e3272120523d509cecf22705f158429586 follows #54. Builder/gitlink/manifest match. The source species/evolution catalog inputs are unchanged.

This is the cumulative feature stack, not released RC12 (app f484577b606348d07337387f14f75ab8cf4970b6, native f7a813317d1b9fec803b48b682f5d74245c79037). Maya's integration and release are untouched. No original scripts, player save formats or battle logic are modified.

Paired component testing compiles the actual native capture/command/text-decoder/panel-text functions with explicit test battle globals, sends their emitted packet through the authenticated authority, and feeds its snapshot back to the C decoder. Tests cover opt-in/ack, late ack after stop, legacy refusal, missing/invalid frames, absent battlers, ended battle, stale view, exact-session reconnect fencing, unsubscribed peers and absence of history/context writes. Existing fishing and TV component tests also run. These are not a full native link, rendered UI test or live two-client campaign playtest. Maya retains those QA steps before release, including field/battle switching, disconnect, save/reload and input focus behavior.
