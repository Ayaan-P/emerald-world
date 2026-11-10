# Original cast and world characters working together

`actor.request_work` is an explicit public-correspondence capability available to
both canonical Hoenn actors and generated recurring characters. It reuses the
existing durable cooperation records, independent recipient decisions and exact
successful action-receipt matching. It does not spawn a duplicate canonical NPC,
move an original actor, alter an original script, or convert a request into work.

A request contains an existing recipient, public fictional purpose, a capability
available to that recipient's actor kind, and an exact result predicate. There
can be only one outstanding request between a pair, as before. Cooperation tools
cannot recursively request more cooperation. Unknown, inactive or self recipients
are rejected. Capability preconditions and world permissions remain unchanged.

The recipient receives a real public event and independently chooses whether to
accept, decline or abandon using `world.respond_cooperation`. Acceptance does not
install a plan. If the recipient chooses to act, `world.deliver_cooperation` only
accepts its own successful authority receipt after acceptance for the exact tool
and result predicate. The original sender can then receive an author turn and use
that evidence in an ordinary supported action or revised goal/dialogue. It may
also wait. Withdrawal never undoes already committed world changes.

The existing `world.request_cooperation` still requires actual adjacency between
world characters. The new correspondence route explicitly records
`public_correspondence_not_physical_meeting`; it never claims a meeting, travel,
animated labor, inventory transfer or achievement of the prose purpose.

## Player-visible path and scope

Component tests exercise a canonical Rydel request to an independently controlled
world researcher, separate acceptance, an actual supported outbreak configuration,
a real native-facing outbreak snapshot, evidence delivery, and a validated Rydel
response available through his existing original-actor dialogue path. Another
test sends a world-character request to Steven, who independently declines. These
are deterministic test decisions, not installed scripts or a claim that a model
chose them. No role-specific task, fixed relationship score or prescribed arc is
added. Wally and Briney use the same canonical capability boundary.

Real map/NPC effects depend on which existing capability the recipient chooses.
Player progress, bags and parties are not written by this system. Historical
receipts do not establish that an effect still exists, a client rendered it, or a
fictional purpose is objectively fulfilled.

## Integration

App-only follow-on to #360 `fa6f48c30540593f210f5ea1535a4c3d5e82939e`.
Native pin remains #51 `5408512d66c2c6903f9d28316e88e6db3ed90447`.
No native protocol change. Existing parent branches and Maya's integration/release
are untouched. This is the cumulative divergent candidate, not released RC12.

Tests cover actual authority plans, independent decisions, recipient capability
validation, exact action evidence, canonical author validation, native-facing
world snapshot and restart without replay, plus existing adjacent-cooperation
regressions. Full linked/rendered and live-model behavior remains Maya's QA.
