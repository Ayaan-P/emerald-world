# Experimental sound-move field calls

With WORLD_FIELD_MOVES_EXPERIMENT=1 (default 0), the existing party WORLD MOVE
selector offers an additional explicit choice for a currently learned sound move:
“Call local wild Pokemon (private)” or “Use facing shared object”. Eligibility uses
native IsSoundMove metadata, not a named move list or inferred elemental effect.
Growl, Roar, Sing and Uproar are examples of sound moves in the pinned engine.

A call rechecks the same selected conscious, non-egg Pokemon, learned move, trainer,
map, position and facing. It uses SweetScentWildEncounter's actual local land/water
generator and normal battle entry, not a simulated encounter or minted roster.
The chosen Pokemon's stock cry plays when the generator starts a battle. There
is no new move animation, PP deduction, shared catch, guaranteed species, victory
or captured-individual claim. Catch, bag and ordinary save behavior remain stock.
The engine's existing personal-roamer, outbreak, time-of-day and Sootopolis water
restriction logic remains in that generator. Existing admitted shared outbreaks
can influence it through the already-published mass_outbreak path; this feature
neither configures outbreaks nor uploads the player's call or party.

Special contexts are excluded: generated maps, Safari, Battle Pike/Pyramid,
Trainer Hill, active link, battle, script and palette fade. A tile without an
eligible encounter produces a truthful no-encounter message. Object mode keeps
its existing explicit shared-move/action notice and authority request/receipt.
A call never sends FM GET/USE or emits a new public history report. Other existing
optional reporting systems retain their own consent controls.

Build through the app's existing --development --experimental-field-moves flag.
This native child of #74 c727376a85d9a5dedc5207e435d66417d46a01f5 is separate from
Maya's #72 reconciliation, not an RC12-derived release. No world_bridge.c,
world_activity.c, world_character_worker.c or uncertain operation is changed.

Validation: compiled actual controller source with both flag values, learned-move
and context guards, no-wire private choice, stale selection/cancellation, failure
and no repeated dispatch. A separate compiled test extracts the actual stock
SweetScentWildEncounter function and checks land/water/outbreak/roamer selection,
missing tables and the Sootopolis guard with fixture dependencies. These are
component tests, not a full linked build or rendered encounter/capture playtest.
Full native integration, audio timing, two-client play and save QA remain pending.

Paired native #75 head be9bd71ea4a252837491c269f2bbb9ea2da53366. App child of #415
71533a39ea87d637417729ee634dcde1aad3771f. Other source catalogs remain the
same exact native data; the pin changes only for this new native subsystem.
