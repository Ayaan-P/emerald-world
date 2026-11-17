# Native seven-floor Pyramid courses (experimental)

Independent draft on app #402 / native #64. Not RC12. Maya's frozen #384/#56
and all pending/denied operations remain unchanged.

## Actual gameplay

Agents use `world.publish_pyramid_course(id, seed)` to publish an immutable uint32
seed. The returned forecast exposes seven real native floor templates: item/trainer
counts, entrance/exit squares and native layout-offset options. It does not invent
new rooms, completed travel, catches, victories, or identical enemy teams.

Players browse `/guild pyramid page 0`, inspect `/guild pyramid show ID`, then
explicitly `/pyramid load ID REVISION yes` outside an active Pyramid. Check
`/pyramid status` for arming. `/pyramid off` cancels only the pending next admission.
Enter through the ordinary Battle Pyramid receptionist, choose your own eligible
three Pokemon and accept the ordinary save prompt. No eligibility bypass, party
replacement by the server, automatic battle or new reward system.

The course sets the four existing saved Pyramid seeds at NEW challenge admission.
Each subsequent floor deterministically advances those seeds. The engine continues
to build its real tiles, exits, objects, enemies, bag and battles. Identical courses
at the same floor share geometry, not synchronized party progression or guaranteed
identical battles/loot. This is cooperative exploration planning through existing
world chat/presence, not a new simultaneous co-op battle facility.

## Persistence and cancellation

- Explicitly reserves Hoenn variable `VAR_WORLD_PYRAMID_COURSE = 0x40FD`, replacing
  its unused name. Marker 0xC700..0xC706 stores version 1 and last seeded floor.
  The existing four `pyramidRandoms` fields store the complete continuation state.
  No save structure or size changes. No 0x40FE/0x40FF DexNav writes.
- The actual lobby script calls init/seed BEFORE its normal save. Resume bypasses
  init, reconstructs the admitted floor from saved seeds, then deterministically
  continues at the next native transition. Repeated seeding of the same floor is
  idempotent. No model/server connection is needed after admission.
- Pending downloads/arming are memory-only, expire after 36,000 native pumps and
  clear on disconnect or off. They are bound to the current native trainer ID;
  actual admission consumes the arming once. Restart before admission means reload
  the course. Disconnection after admission never edits the saved course.
- A normal NEW admission without an armed course clears the marker and uses stock
  RNG. Canceling/suspending/losing uses the original scripts. Closing a course only
  prevents new downloads, not already downloaded/admitted runs.
- Existing admitted version-1 courses continue correctly even if new-admission
  experiment is disabled in this implementation. Do not downgrade to an older
  engine lacking this implementation during an unfinished custom run.
- An incompatible/corrupt marker is not claimed to be an active authored course.
  It follows existing random seeding at the next transition. Existing saved floor
  geometry is not rewritten.

## Collision review

Reviewed 3,404 exact native #64 source/header/script/map/platform files, with
blob-verified local copies and current remote reads for mismatches. The only
pre-existing Hoenn reference to 0x40FD was its unused declaration. The FireRed name
`VAR_0x40FD` maps to Kanto's 0x50FD bank when regional state is enabled and has no
current script use. Feature hooks are disabled for IS_FRLG. The exact DexNav config
uses 0x40FE for registered species and 0x40FF for its step counter. Compile-time
assertions protect both. Existing event-data initialization clears variables for
new games; this is a persistent, non-temporary, non-daily variable.

`tools/audit_pyramid_variable.py` adds a repeatable literal/name collision guard
for complete native checkouts. It is not a formal proof against future dynamically
computed variable IDs. Maya must preserve this reservation when integrating other
branches and must not infer compatibility with unseen future changes.

## Build and verification

Default-off new admissions: `scripts/build_expansion.py --development
--experimental-pyramid-courses`. The existing native CPPFLAGS path carries the
explicit flag. No live model calls or network execution in tests.

68 app tests: 66 passed, two existing provider-sandbox skips. Four native tests pass:
compiled seven-floor state/restart/idempotence vectors; actual protocol
consent/cancel/owner/timeout; compiled actual native admission/seed wrapper retaining
DexNav values; source hook/reservation checks. These do NOT verify a full linked
build, rendered seven-floor run, native disk save/suspend/reload, or two-client
play. Those remain Maya's QA before enablement/release.
