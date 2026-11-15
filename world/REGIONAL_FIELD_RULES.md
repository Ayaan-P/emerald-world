App parent #436: 666f4c965dbe7dcab32e2974372bebef6a22ca6d.
Paired native: 23b5a42d58b30be435ed4b7e2fe5a629ee9ce52f.

# Combined-world field eligibility correction

Parent native #84: 659eb2ae1fd66dc6be9b0c733a8850b9b3b40c74.
Independent experimental stack; Maya #72 remains untouched.

The combined executable is Emerald at compile time. Its shared field-move
table therefore used Hoenn badge requirements on Kanto maps. The single
HasBadgeForFieldMove callback now uses GetCurrentRegion() in combined builds
and selects the existing FireRed badge indices for Cut (2), Flash (1), Rock
Smash (6), Fly (3) and Waterfall (7). Strength (4), Surf (5) and Dive (7) remain
as configured. Ordinary Emerald and standalone FireRed builds are unchanged.

This callback is reused by IsFieldMoveUnlocked, party-menu eligibility,
script field-move checks and relevant field interactions. No moves are granted,
no HM item or learned-move requirements are removed, and the actual native
setup routines still decide whether a move can run in the current context.
This does not implement or certify Kanto Fly destinations, story completion,
or a new travel menu. It corrects the common badge eligibility layer only.

## Core-path audit and remaining progression limitation
Current source already includes FireRed encounter headers under
EW_KANTO_CONTENT, separate Kanto trainer IDs/defeat flags, regional vars/scene
flags and counter-bound regional save restoration. Heal locations already
include Pallet and Kanto Pokemon Centers. These were inspected, not newly
proven in a complete native playthrough.

IMPORTANT: include/constants/region_state.h explicitly leaves system badges
shared within a player's save. PewterCity_Gym_Frlg/scripts.inc writes the same
FLAG_BADGE01_GET symbol that Hoenn uses. Brock's separate trainer battle is not
therefore skipped, but badge-dependent gates/dialogue can share progress.
This change preserves that existing save contract; it does NOT claim separate
regional badge progression. A safe split requires a deliberate old-save policy:
the shared historical badge bit alone cannot identify which gym awarded it.
Do not globally reinterpret FlagGet, infer old victories or silently migrate
the bank. Personal saves remain independent between players, as before.

## Validation
Three compiled tests execute the actual callback over all eight field moves,
both region contexts and each possible owned badge, with stubbed region/flag
boundaries: combined build, default Emerald and standalone FireRed. They also
check changing regions does not retain cached eligibility. No full native link,
rendered HM interaction, end-to-end campaign or save/reload QA is claimed.
No held bridge/worker/activity files, save writes, donor assets or live providers.
