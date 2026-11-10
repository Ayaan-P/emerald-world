# Optional route rematch events

App child of #399, paired native child of #61. Neither is RC12-based.
Frozen #384/#56 and Maya integration remain untouched.

Agents configure a time-limited route event using `world.organize_rematches`.
Players browse `/guild rematches`, travel normally, and use the original trainer
interaction. This is a temporary readiness overlay, not a trainer flag write or
an assertion that canonical characters independently agreed to attend.

Eligibility is evaluated against the player's own native save: ordinary rematch
table entry, original trainer already defeated, Match Call registration, and
existing OW_REMATCH_BADGE_COUNT. Special trainers, Gym leaders, Elite Four and
Wally are excluded. VS Seeker configurations retain their existing behavior.
No event removes ordinary randomly generated rematch readiness.

Original scripts choose the next canonical team and apply normal battle results
and progression. No custom roster, shared credit, forced interruption, invented
battle, NPC growth or player save synchronization. During an event repeated
rematches are available; players choose whether to speak to eligible trainers.

The independent J channel polls every 300 link pumps. Server responses require
fresh current-map presence and carry a maximum 30-second lease (1800 pumps at
60Hz); NONE, malformed response or disconnect clears the overlay. Pausing the
client also pauses pump time. Expiry/closure can take a polling interval to reach
a client. No battle already begun is cancelled or rewritten.

Tests compile the actual wire cache and the native eligibility function extracted
from battle_setup.c, with fake engine dependencies. They cover different maps,
expiry, malformed input, disconnect, original defeat, registration, badges,
special entries and VS Seeker exclusion. They do not execute original scripts
or a full battle. Full linked/rendered/two-client QA remains pending. No live
model/provider calls. Default behavior is unchanged with no active event.
