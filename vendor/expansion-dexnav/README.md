# Native DexNav compatibility stage

## Status and scope

This is a source implementation awaiting the parent's combined RC3 build and
runtime acceptance. No build, test, game, GUI, SSH session, dependencies, or
trainer profiles were run or opened by this worker. It is not a claim that the
uncompiled candidate has passed gameplay acceptance.

The real RHH DexNav translation unit is retained, not replaced with a new list
menu. The original complete files and credits are under `upstream/`.
`provenance.json` records every imported file's pinned Git blob, byte count and
original path. All imported bytes, including PNG/PAL/tilemap assets, were checked
with Git's `blob <length>\0<bytes>` SHA-1 before writing.

Upstream: https://github.com/rh-hideout/pokeemerald-expansion
Pinned commit: `c460a8661dfa0598ae25d42a968c690ecbf489c6`
Base: `fb4dd14254708a6ad1840858dbed2442875998c7`

## Access and controls

- Native game buttons **L+R**, while free in the field, open the full browser.
- D-pad selects a map encounter. Unseen species remain concealed.
- **R** in the browser registers the selected seen species privately.
- **A** exits the browser and starts that species' field search.
- **B** leaves the browser without a search.
- **R** in the field searches for the registered species on the current map.
- Hold **L** while approaching a signal to use real native slow-walk movement.
  Running/biking near it, walking normally too close, timeout and losing range
  retain the donor's failure behavior. Water/cave targets can relocate twice.
- Reach the signal tile to generate the final encounter and enter the existing
  native wild-battle admission path. A water search requires already surfing.
- START/SELECT end a live search before handing off to ordinary field menus.
  Changing maps and battles also clean up private search graphics.

Gating uses the existing received-Pokédex flag and a usable native party. Safari,
Battle Frontier/Pike/Pyramid and native link modes are excluded. Opening DexNav
never unlocks story flags or the National Dex. Ordinary wild tables, vanilla
encounters and vanilla saved structures are not replaced. DexNav search rewards
are opt-in through an explicit search, not an ambient change to vanilla play.

### Native feature menu contract

`include/dexnav.h`: `bool8 DexNav_RequestOpen(void)` queues only. The caller must
close its own window and release its own field lock. The next real free field
input frame drains the request, allocates the actual donor GUI task, fades, and
opens it. FALSE rejects an unavailable or already queued request. No synthetic
ready state is published. `DexNav_OpenFromField()` is the guarded immediate
field entry used internally. No start-menu row was added or edited by this
worker, avoiding conflict with the native feature-menu worker.

## Whole module reuse and native adapters

- `src/dexnav.c` preserves the donor GUI state, cursor tasks, encounter dedup,
  registered search, tile/proximity/habitat movement, HUD, search probability
  curves, potential/held-item/move generation and embedded strings. The full
  donor hidden-row/detector code remains present, but its native provider is
  deliberately absent at this compatibility stage.
- `include/dexnav.h`, `include/config/dexnav.h`, the message scripts and complete
  DexNav asset bundle come from the same pinned source. Donor compression is
  replaced by the existing native LZ asset pipeline. No donor tools are run.
- `src/platform/dexnav_native.c` is a replaceable native data/resource/private
  progression boundary. Species/moves/items are native `u16` values and native
  names/accessors/learnsets. Temporary moveset generation uses a local native
  Pokemon, never `gEnemyParty` or invitation/capture APIs.
- Two narrow native wild-encounter wrappers expose the existing current-map
  header (including Altering Cave selection) and final native wild generation.
  Donor chain/random extra shiny rolls are applied only to final hunt creation
  with the native creation and shiny predicates. Ordinary encounters do not
  call them. This is not a claim of all ORAS/Expansion shiny mechanics.
- Final IVs, normal ability, item, and moves are applied before
  `BattleSetup_StartWildBattle()`. Thus native `WorldActivity_TryCoopWildBattle`
  captures the final original-layout mon and performs its real range/consent/
  admission checks. No scripted `dowildbattle` shortcut is used.
- Solo native `SetWildMonHeldItem` has a small PORTABLE guard keyed to the owned
  final encounter's species and personality so it cannot reroll a DexNav item
  after co-op would have captured it. Ordinary item assignment is unchanged.
- Solo and co-op return callbacks consume one initiating-owner result latch.
  Win/catch raises that species' level up to 255 and chain up to the donor cap.
  Loss/escape breaks the chain. Guests have no owner latch and cannot receive
  another player's search credit. Existing co-op private catches/rewards are
  not replaced, and battle results are not forced.
- Native unused grass, long-grass, sand and water art/animation templates are
  reused through a separately owned sprite/palette. Imported cave dust supplies
  the missing cave signal. No saved ObjectEvent or remote local ID is allocated.
- Sprite allocation checks the existing `MAX_SPRITES`/tag allocators. Three OBJ
  palettes are acquired only from the native dynamic region, rejecting active
  untagged users. HUD palettes are not hardcoded to slots 12/13/15. Ownership
  markers protect sprite teardown, palette ownership is checked before restore,
  and palette snapshots are restored only while still owned. A busy resource
  pool reports a failed search instead of evicting campaign or multiplayer art.
  Dedicated fullscreen GUI palettes are separate from field resources. Current
  pool sizes are compatibility constraints to lift in the parent's capacity
  work, not permanent product limits.

## Private progression and ABI

The only runtime storage is `DexNavNativeState`. No SaveBlock bytes, arbitrary
story flags/vars, party layouts, native constant tables or battle engines are
transplanted. A static assertion pins `sizeof(struct Pokemon) == 100`.

On Linux/macOS, `<explicit opened save path>.dexnav` holds registration and
per-species levels. It is inside the already writable private profile mount.
There is no HOME discovery, broader sandbox mount or world/session.py change.
The existing NativeSave API supplies owned regular-file/no-symlink/no-hardlink
checks, exclusive lifetime locking and durable fsync writes. Private permissions
are additionally required. DNV2 is an explicit byte format with trainer ID,
native species count, registration, sequence and checksum. Two journal slots
retain the previous valid record through an interrupted write without replacing
the locked inode. An I/O failure disables further persistence for that session.
Unknown/truncated records are never interpreted as native structs. Trainer-ID
mismatch does not load another trainer's progression. The chain, target, timer,
search RNG and active HUD are session-only and never transmitted/shared.

## Current limits, not permanent product restrictions

- Current coverage is the native Gen3 species/moves/items ABI, not a claim of
  a completed Gen9 data migration. The adapter is intentionally isolated for
  future coherent Expansion species/forms/battle-engine migration, including
  Megas and the current National Dex as separate opt-in content/mechanics.
- Hidden abilities are unsupported by current native mon storage. Accessor 2
  returns ABILITY_NONE and normal ability selection remains native. No fictive
  hidden ability or widened party/save structure is introduced.
- Hidden-only sidecar encounters/detector spawning are not enabled, and the
  third browser habitat row contains no native hidden-provider entries. No
  secret expanded species or altered ordinary tables were invented.
- Fishing/rock-smash are not browser habitats in this donor module.
- Native icons use a single 32x32 frame rather than unsafe donor/native
  mon-icon allocation callbacks. The donor GUI layout and tasks are retained.
- Windows currently retains search progression only for the session because
  the existing ownership-safe NativeSave sidecar API is POSIX-only. This is
  explicit rather than using an unsafe unlocked file fallback.
- Runtime resource stress, return-to-field proxy rebinding, exact UI rendering,
  scripted interruption and real co-op capture must be accepted on the combined
  candidate. No capacity or gameplay success was fabricated by this worker.

## Corrections made at the boundary

Corrected donor object-array spriteId indexing, signed/width-safe search tile
coordinates and probability divisors, allocation failure guards, zero-national-
dex reads, screen-X overwriting proximity, fade timing, unchecked native icon
allocation, ephemeral sprite-template pointers and stale sprite cleanup. Native
scripts use existing event macros and pointer-width encoding; no pointer is
serialized with `.4byte` or cast to 32 bits.

## Credits and asset rights

Retain `upstream/CREDITS.md` and `upstream/docs/CREDITS.md` with all RHH,
individual contributor and upstream pret/CFRU/resource credits intact. This
port does not invent an individual DexNav authorship credit absent in the
pinned source, and it does not remove any existing credit.

No root project LICENSE grant was established in the pinned tree. Public source
availability is not an MIT/public-domain/commercial grant. The imported DexNav
and cave-dust art, and derivative Pokémon assets generally, need rights review
before distributing an asset pack. This branch is a source checkpoint, not a
new licensing assertion or a binary/game/save distribution.

## Parent-only acceptance

Added but **not run**: `test/test_dexnav_source.py` (pin/provenance and native
handoff/privacy gates) and `test/test_dexnav_progress.py` (compiles the exact
pure C codec helpers in a temporary harness, checking corrupt/torn journal
fallback, sequence wrap, registration bounds and species-ABI mismatch).

The combined RC3 checkpoint must also exercise real controls: queued native-menu
open with its lock released, L+R browser/cancel, map encounter rows/seen conceal,
registration restart, native slow-walk approach, timeout/run/map cancellation,
water/cave relocation, native egg moves/IVs/items, solo catch/result credit,
tagged real admission/capture/private rewards, guest non-credit, admission
fallback, full-resource failure and field/remote palette restoration. Test
profiles only. No human saves or displays 90/91 are required by this worker.
