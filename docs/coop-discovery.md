# Personal discovery during co-op encounters

Experimental, default off: EW_COOP_DISCOVERY=0. App opt-in is
--experimental-coop-discovery --development. No new packet, shared Pokédex,
reward, save layout, automatic save operation or partner identity transmission.
This local presentation preference does not require a different wire version.

A completed local LOADMONSPRITE or SWITCHINANIM presentation can add the actual
opponent to that player's native SEEN records. Completion of ILLUSION_OFF can
register the revealed identity. The observer runs before the controller retires
its command and checks current co-op generation, active opponent slot, authenticated
public snapshot readiness on the guest, original opponent identity, visible live
sprite, absence/substitute/transform/disguise state, and actual visual species.
The roster is never scanned. Receiving an opponent party or EXP/victory packet
is not evidence that a player saw its reserves. Partners and their benches are
excluded. CAUGHT flags remain exclusively owned by the existing native catch path.

A genuine completed observation stays seen after retreat or disconnect, as a
personal discovery. Pending/hidden presentations at disconnect do not grant it.
Repetition uses the native idempotent SEEN setter, including the native personality
handling for Unown/Spinda. This changes normal in-memory personal progression;
it does not force a disk save or change an actual user's save in development.

Conservative limits: unidentified Ghost encounters, transformed/substitute
appearances and mismatched/form-dependent presentation are not registered by
this hook. Illusion's copied appearance is not credited as a genuine individual;
the actual identity is credited only after its completed reveal. A skipped or
incomplete rendering may under-record rather than expose a hidden species.

Validation: production observation function compiled with synthetic engine
structures and exercised for initial/switch/reveal presentations, repeats,
master/guest readiness, stale generation/slot, hidden/absent sprites, partner
exclusion, disguise/transform/substitute, and disconnect. Source checks confirm
the completion hook and SEEN-only default-off behavior. Two new app flag tests
and existing regional/Rusturf build-contract tests also pass.

No complete native link or rendered/two-client QA was possible: private native
checkout authentication remains unavailable to shell Git. Required QA includes
actual route encounters, trainer switches and unrevealed reserves, Illusion break,
retreat/loss/disconnect, Pokédex entry/personality rendering, and ordinary solo/
competitive regressions. Do not call these component checks a playtest.
