# Agent-curated Slateport rental selections

A general `world.rentals(operation="configure", value="[17,8,32,15,63,57]")` capability lets an enrolled canonical or
world actor choose six actual compiled Slateport Battle Tent rental sets, or close
its own pool with `[]`. The provider-neutral discovery context exposes the tool. The
`world.rentals(operation="inspect", value=page)` capability returns ten sets per page (0..6), with
species, moves, held item and nature, keeping the authority transport bounded. Agents choose their own
purpose from committed history; no named character, scripted theme or fixed story
is installed. This is public venue authoring, not a claim that an NPC traveled,
trained the rentals, recruited Pokémon or won a battle.

## Actual player flow

Enter the normal Slateport Battle Tent and begin its existing rental challenge.
After the normal initial rental generation, a compatible connected client offers
an optional shared-world selection. Declining leaves the original six rentals.
Accepting replaces only the six initial rental set IDs before native opponent
generation. The existing choose-three menu, three battles, swaps, prizes and
original-party restoration remain the native game's responsibility and are
unchanged. This does not recruit rentals into the permanent party, grant items,
reset story flags or replace Battle Factory/other Tent rules.

An absent, changed, disconnected or stale pool leaves the original selection.
The offer freezes its exact IDs/revision; no mid-challenge mutation is applied.
Paused challenges resume their already saved rentals, not the current world pool.

## Rules and durable results

Both authority and native code validate six distinct species and distinct nonempty
held items. More importantly, every eligible native opponent must retain a legal
third Pokémon for every legal first/second pick, so the authored exclusion set
cannot strand the native greedy generator. Invalid pools are refused before any
history or rental change. A single actor owns the active pool until it closes it;
other actors cannot overwrite it. Configuration and resulting plan receipts use
the existing transaction and history runtime and persist across authority restart.
The receipt means the optional venue pool exists, not that a player selected it.

Only RENTALS1 clients receive RENTAL_POOL snapshots; native fallback negotiates
this independently of older capabilities. The ordinary unconfigured game stays
unchanged. There is no player bag, permanent-party or cross-save server editing.

## Verification and integration

Tests execute an actual actor plan into an authenticated snapshot, validate
restart/ownership/refusal, compare the shipped catalog against exact native source,
and compare app/native validators across 101 varied pools. Native C tests exercise
frozen offers and actual rental-ID replacement; script checks place the optional
hook before opponent generation and the selection screen.

These are component checks, not a full linked build, rendered rental selection or
complete three-battle playtest. Maya must verify menu entry/decline, disconnect and
pool revision changes, native rental stats/moves, swaps, losses/prizes, pause/save,
and restoration of the original private party before release.

Based on app #352 / native #48, not released RC12. Preserve released app
f484577b606348d07337387f14f75ab8cf4970b6 and engine
f7a813317d1b9fec803b48b682f5d74245c79037 during Maya's integration. No release or
integration branch is changed here.
