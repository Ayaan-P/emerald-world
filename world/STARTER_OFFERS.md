# Optional agent-authored starter offers

Agents can inspect the 27 supported main-series starter species and publish an
immutable offer of three distinct names using `world.starters`. Players remain in
control: a fresh Hoenn save explicitly loads an exact offer revision before Birch's
normal selection. Vanilla choices remain the default. No generated narrative,
automatic adoption, party replacement, training or victory is inferred.

## Use

Build with `scripts/build_expansion.py --development --experimental-starter-offers`.
Admissions are disabled by default pending actual intro/save QA.

- Agent inspect: operation `inspect`, value empty string. Publish: operation `publish`,
  value JSON `{id, species:[three catalog names]}`. Close: operation `close`, value own ID.
- Player: `/guild starters page 0`; `/starter load ID REVISION yes`; check
  `/starter status`. `/starter off` cancels an unstarted offer.
- Load before approaching Birch's bag, on a fresh save with no Pokemon and before
  the Pokemon-get flag. There is no injection into an established party/save.
- The native bag UI shows the offered species' existing sprites, labels and cries.
  Declining a choice returns to the same frozen offer. Confirming uses the existing
  `CB2_GiveStarter` / `ScriptGiveMon` level-5 grant and first battle, not server-created
  Pokemon. Actual starter stats, moves and identity remain engine-generated.
- Rival teams and core scripts remain their original slot-based versions. This does
  not retheme the rival or promise a new region/story/type-balanced campaign.

## Persistent species and recovery boundary

Explicitly reserves previously unused Hoenn variable 0x40FC as
`VAR_WORLD_STARTER_SPECIES`. Bit 15 marks this format; remaining bits store a validated
supported species. The existing starter slot variable remains 0..2. Later native
starter-in-party checks and credits resolve the retained species, not a newly fetched
server offer. No save-layout/size change, no reuse of Pyramid 0x40FD or DexNav
0x40FE/0x40FF. A normal new-game initialization clears the reservation.

Pending offer and arming are memory-only, expire after 36,000 native pumps, and clear
on disconnect/off/restart. When the real UI begins, it freezes the owner's three
choices; network changes/disconnection cannot change what confirmation grants.
The Route101 script sets Pokemon-get BEFORE opening that UI, so the selection hook
allows that exact transition while new request admission still rejects the flag.
Confirmation retains the species before the existing native grant. Ordinary saving
persists the result; a crash before saving has ordinary unsaved-intro semantics.
No disk-save transaction or rendered save recovery has been verified here.

Disabled new-admission builds retain support for already chosen species. Older
engines without this implementation do not: **do not downgrade a custom-starter save**
if correct later starter checks/credits are required. Invalid marker/species falls
back to stock resolution. Closing an offer cannot revoke a frozen or chosen starter.
Kanto/FireRed is excluded. Unsupported compiled-out species refuse admission.

## Collision review and verification

Native audit metadata records the 3,404-file exact-source baseline, cached remote
reads and refreshed platform reads, plus subsequent #65/#66/#67 additions. Only the
unused Hoenn declaration used 0x40FC; FireRed's symbolic 0x40FC maps into the separate
Kanto 0x50FC bank. This is not a proof about dynamically computed IDs or unseen future
changes. Maya must preserve the explicit reservation when integrating.

Independent draft on app #405 (99a862df6457f58e353112930392f92abb6ac929) and native
#67 (6ea6125d4937238824cd4752eb32b68cbb912791), not RC12. Frozen #384/#56, Maya's
integration and denied/uncertain operations are untouched. No donor assets or live
provider calls.

79 selected app tests: 77 pass, two existing provider sandbox skips. Two native tests
pass: compiled actual protocol/native wrapper with engine fixtures for flag ordering,
owner/fresh-save checks, invalid choices, decline/frozen selection, disconnect,
cancel/timeout, saved continuation with admission disabled and adjacent reservation
preservation; source hook checks for the actual selection UI. Full native linked build,
rendered selection/first battle, actual disk save/reload, credits and later scripted
starter checks remain required integration QA before enabling/releasing.
