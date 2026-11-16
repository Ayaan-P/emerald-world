# Emerald World RC12

A matched Expansion-native client and world authority integrating the RC12
adventure/launcher work with the compatible Living Cast work.

## What is new

- **Lantern Trail:** a built-in authored adventure with residents, four private
  discoveries, directions, an optional beginner trainer battle and an opt-in
  public project. Owners review its preview and explicitly confirm installation.
- **In-game objectives and guides:** start a private survey, get directions,
  refresh your view and speak to the route's residents. Opening or refreshing
  objectives does not start progress or publish private history.
- **Authored character identity:** native battles retain the author's literal
  character name, reviewed portrait and individual Pokemon/team state. Battles
  require an explicit offer and your consent.
- **Living Cast controls:** scoped initialization and opt-in author workers for
  original characters' public goals, dialogue and projects. Original story,
  bicycle, sailing and other native services remain the game's own scripts.
  There is no hidden author-worker startup or automatic model selection change.
- **Encounter coherence:** DexNav's displayed species and levels use the same
  authored habitat/slot resolver as actual encounters. Expanded encounters remain
  an owner choice; existing worlds' shuffle and encounter settings are preserved.
- **Delivery integration:** required trainer runtime catalogs are included in the
  packages. Windows retains the current protocol capabilities and its own private
  profile namespace rather than substituting an older client.

## First play without risking your main progress

If the isolated demonstration kit is installed, select world `rc12-field-trip`
and trainer `RC12Preview`. This is a clearly labeled demonstration using an
existing disposable Alice/Treecko starter fixture, **not your personal save or
proof of naturally earned starter progress**. It does not start an AI worker.

1. Play the selected local world, then use the native **WORLD** menu to enter
   Lantern Trail.
2. Open **Objectives**. **S** starts your private route; **G** requests directions;
   **Enter** refreshes the view. Visit the four clearings and talk to Mira.
3. Speak to Ivo for the optional battle. Decline with **B** or consent with **A**
   when offered; do not accept unless you want to battle.
4. Leave the generated area through WORLD and save from the normal stock-map
   Start menu. SAVE is intentionally not offered while inside the generated area.
   Route progress is private authority state; party/story progress stays in your
   own native save.

Without the kit, create a **new** local world, review and install Lantern Trail
from the owner's adventure catalog, then use a new or explicitly imported
Expansion profile. Do not replace an existing world's authored content just to
try the new release.

## Living Cast

Choose a local world and a supported author backend in the launcher. Initialize
only the character you intend to commission, then explicitly start the worker
when ready. Provider prerequisites and errors are visible. Model output still
must pass actor/version/evidence checks, compilation and the real sandbox before
it can change the authority. A rejected request is not an applied character turn.
Private player questions and history require their existing opt-in permissions;
they are not automatically public story material.

## Platforms and boundaries

- Linux is the primary player/owner application. Its managed installer keeps
  worlds and saves outside the release directory and retains the previous
  installed release for rollback.
- The matching Windows x64 archive is a **native guest client** for friends.
  Extract the entire private archive and run `Start-Expansion.cmd`. It requires
  an existing **64-bit Python 3.11+ with tkinter**. It is not a Windows port of
  Linux's world-hosting/author sandbox.
- The content cohort is combined Hoenn/Kanto with region state enabled. The
  experimental `GENERATED_WORLD_REGIONS` engine mode is not part of this cut;
  supported authored areas use the reviewed existing transport and admission.
- World-rule permissions do not grant battle key items or bypass native story,
  species or ownership requirements. This release does not claim every species
  or every optional mechanic has been naturally acquired in a playthrough.
- Game-containing archives are private handoffs. No game binary, ROM, personal
  save, provider credential or private research archive belongs in public release
  assets.
