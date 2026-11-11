# Composable committed-event waits

The existing unrestricted world-author request already returns novel Python
`source` + `tests`, run through the established mechanic sandbox and validation.
This adds no second script engine or permission to bypass that path.

`world.await_event(event, where)` gives canonical and generated actors a missing
plan primitive: subscribe from the current public history boundary, wait without
model calls, then use the first actual matching event as input to later steps.
`where` is JSON with up to four exact top-level scalar equality filters. Outputs
include `event_seq`, the complete public `payload`, and `event_FIELD` scalar values
usable with normal result references. Private logs, older matching events, and
mere model predictions cannot satisfy a wait.

Cursor updates and tool receipts use normal authority transactions. Polling scans
at most 64 records per tick, persists progress across busy backlogs and restart,
and never skips unscanned pages. Withdrawal uses the runtime's existing pending
cancellation. Waiting is one-shot; an agent may author a new subscription after a
result, but this does not introduce an unbounded recursive rule or self-loop.

Example composition is generic: wait for another character's actual public
letter, execute an available authority action, pass the received text to a later
message. The sender acts independently. Other event types/filter values can be
chosen from the inspected public log. A public record is shared knowledge, not
proof the actor physically saw an event, another player's private memory, or
permission to mutate a native save. Existing action preconditions still apply at
execution time, so stale decisions block rather than invent success.

Tests exercise two original actors, real delivered correspondence, actual shared
opportunity changes, scalar result composition, restart, old/private exclusion,
and a 130-record backlog. Synthetic signal events are explicitly test fixtures.
No live provider or rendered/native gameplay claim. Base is consolidated #314;
Maya's integration remains untouched.
