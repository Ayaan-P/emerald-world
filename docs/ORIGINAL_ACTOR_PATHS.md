# Original actor path adapter (draft follow-on to living-cast RC)

This paired candidate replaces the hard-coded Rydel coordinates in the native
runner with reviewed original-actor bindings and bounded closed paths. It does
not add replacement NPCs, autonomous town travel, earned rewards, or new story
flags. Maya owns linked build, rendered multiplayer QA and release.

## Player experience

An author can retain `scene: rydel_step` on Rydel or `scene: steven_study` on
Steven, optionally gated by an existing actor-owned activity project. Talk to
the actual character, then use `/history scene ask rydel` or
`/history scene ask steven`. Every connected trainer must be ready in that room
and independently use `/history scene join`. The native original actor walks;
each observer acknowledges each completed step before the next one is issued.
B/cancel returns along the traversed path. Original services resume only after
verified home restoration. This remains an optional shared scene, not an
unattended agent travel scheduler or a claim of completed research.

## Reviewed bindings

- Rydel: original Bike Shop object 1 / MAN_2, (2,5) -> (3,5) -> (2,5).
- Steven: original house object 1 / STEVEN, post-Dive state 2 and received-Dive
  flag, (6,5) -> (5,5) -> (4,5) -> (5,5) -> (6,5).

Source: native parent f5b45730ef96debf512f501109b3388ab2342cc6,
`data/maps/MossdeepCity_StevensHouse/scripts.inc`, particularly
SetStevenPos and StevenReturn. The original return script already traverses
these Steven tiles. No map/object/story script is edited. Native actual
collision, object occupancy and direction-overwrite checks can refuse any
step. Hidden/absent/wrong-stage Steven is never spawned or repositioned.

## Protocol and recovery

HELLO2 advertises named-path support. Legacy HELLO retains the Rydel route;
Steven requires all participants to advertise HELLO2. PREPARE_PATH and
RECOVER_PATH carry only a reviewed path key, never model-defined coordinates.
New native clients fail closed against old authorities that refuse HELLO2.
The per-client lease reserves every route tile, freezes controls only during
the joined scene, and checks native actor identity before every operation.
A later vanilla script takes precedence and is never overwritten.
Cancellation reverses completed path edges using ordinary held movement. A
blocked reverse route retains restoration debt rather than teleporting.

Authority persists actor/path identity before sending PREPARE. Restart recovery
uses that exact binding, not Rydel's home. Old Rydel debt remains compatible.
Wrong-save reconnects cannot clear it. Existing cohort/session reservation and
late-join exclusion remain unchanged. HOME is native attestation, not anti-cheat
or public achievement. No client result is converted into XP or world history.

## Validation boundary

Actual C controller is compiled with explicit engine doubles and paired with
production authority in a two-observer four-step Steven regression. Existing
Rydel regression remains. Native tests cover reverse cancellation, late
collision, story interruption, reused object, wrong binding, disconnect and
recovery. App tests cover legacy refusal, route occupancy and restart identity.
These checks do not establish rendered geometry, animation, timing, or complete
linked engine compatibility. Maya must test original Dive sequence, post-Dive
scene, later Steven absence, bike service, cancellation, observer disconnect,
restart and original-script interruption in the paired full build.
