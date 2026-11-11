# Combined-region Safari gameplay

Child of app #441 (2576bb3bee9524e455bdf818af28def7f3e448ca), paired with
native #90 (a328f3acd00f66af05c75ef6f464f69efbfe1dd7). Independent stack,
not Maya #410/#72 or RC12. Existing combined-region build options apply.

Corrects the native Fuchsia Safari path used to reach Surf and the Gold Teeth:
- Existing Kanto 600-step budget and 30 balls; Hoenn retains 500 steps.
- Consistent native bait/rock menu, action selection and action callbacks in
  Kanto, with Pokeblock/go-near behavior retained in Hoenn.
- Retirement, time-out and out-of-balls scripts return to their own region's
  entrance and set the existing regional scene state, rather than sending
  Kanto players to Route 121.

Uses the engine's existing FRLG mechanics, not a new retail-accuracy model.
Payments, catches, inventory, Surf/Gold Teeth scripts, personal save formats
and existing opt-in outing reporting are unchanged. No new shared Kanto
reporting support or authority-owned captures are claimed.

Validation: 29 focused app tests and four native component tests pass.
Six native fixture executables exercise actual entry/selector and bait/rock/
watch callbacks across three build cohorts; bounded script traces verify both
exit routes. This is not the real script VM or a complete native link.
Rendered/controller Safari, Surf/Gold Teeth traversal, save/restart and
two-client QA remain outstanding. No held operations, real saves, donor assets
or live providers touched.
