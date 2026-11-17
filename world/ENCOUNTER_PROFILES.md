# Agent-authored move-driven encounter profiles

App child of #417 (`b899764da476cc9b4db900056f5f63c2ce83d050`); pins native #77 `75ce2961d9111e33a7379a822951ba8da8fd20f7`, child of #76. This is the independent feature stack, not Maya #410/#72 or RC12. No denied/uncertain operations retried.

## Authoring and actual player flow

The general capability runtime discovers `world.configure_encounter_profile` and `encounter_profiles.maps/profiles`. An agent selects a reviewed Hoenn route, existing move selector JSON (exact IDs or native type/category families), acceptance 25..99, prefer_move_type 0/1, steps 10..200, and PP cost 1..4. The durable configuration is actor-owned; another actor cannot overwrite it. A committed configuration receipt means configuration only, not player activation, sightings, battle, capture or growth. No preset profile or fixed move mapping is installed.

Start the matched build with `--development --experimental-field-moves` (default off). Select an actual learned move in party WORLD MOVE. Explicitly choose profile lookup after the disclosure that this sends the chosen move ID to the world host. Then inspect and separately select activation/PP cost. The default offer choice is other interactions, not activation. Cancel spends nothing. Existing private call/care and shared object interactions remain available without profile lookup.

## Effect and limits

This is a new optional FIELD RULE, not stock battle simulation. Stock walking odds/abilities/Repel/Lure and personal roamer/outbreak paths run first. Only the initial ordinary land/water candidate is filtered. With prefer_move_type=1, actual FINAL post-shuffle species of the chosen move's native type retain 100% acceptance, others use the configured percent; with 0, all ordinary candidates use that percent. No reroll, extra species, level rewriting or increased encounter rate. A route with no matching species does not acquire them. The second stock double-encounter opponent is unchanged. Scripted encounters, calls/Sweet Scent, fishing, rock-smash, roamers and outbreaks do not use this filter.

Actual PP is deducted synchronously only after native learned-move/current PP/source/map/owner checks and confirmation. Profile is local and temporary: ends at countdown zero or on menu, battle, script, fade, map/identity change or disconnect. Normal saving retains PP cost; restart does not restore profile. No save field or redelivery receipt. Repel/Lure counters and bags are untouched. Generated maps, Safari, Frontier, Battle Tent rooms and Trainer Hill reject activation. No remote player effects or autonomous NPC capture claims. Selecting a new profile replaces the old one and costs PP again.

## Verification

Seven native compiled-source/component tests passed (actual UI, profile controller and generator), including post-shuffle filtering, scope reset, unchanged stock Repel/ability rejection, default off, PP, no repeat and context checks. App tests cover actual agent plan execution, restart persistence, ownership/bounds, authenticated negotiation, selectors and existing UI/move flows; provider tests use fixtures only. Full linked native, rendered UX, save/load and multiplayer QA remain outstanding. No live providers or bespoke animation. Draft, not release-ready.
