# Lantern Trail Outpost

Lantern Trail is a built-in, model-free adventure for the shared outdoor area. Its authored recipe lives in `world/product_adventure.py`. It is not a saved trainer, a test world database, a generated achievement or a paid model request.

## The outing

The four clearings are Lantern Outpost, Wind Lookout, Reed Pool and Field Archive. Mira welcomes visitors near the entry and provides private survey guidance. Ivo keeps the lookout and offers an optional level 4 Wingull practice battle. Ren keeps the archive and can also guide visitors. Mira has a level 4 Taillow and Ren has a level 3 Zigzagoon. No battle is required to finish the survey.

A normal starter is sufficient. Players must be outdoors, on foot, have field control and a conscious non-Egg Pokemon, and finish an active rally before entering. Select Lantern Trail Outpost in launcher Explore, then choose **Explore generated area** in the native WORLD menu. The RC12 consumer doorway is **WORLD > My objectives**, with explicit **Start survey** and **Guide directions** actions. Starting is a player choice, never a side effect of reading the objectives. Internal survey commands remain available for compatibility. Matched native consumer-action implementation and acceptance are release prerequisites, not features implemented by this Python module.

All four discoveries can be completed privately with no guild or chronicle. The existing survey stores visits under the player's own identity and exact revision. Returning later retains those discoveries.

Public story consequences are optional. The first explicitly confirmed discovery share at Wind Lookout or Reed Pool chooses a lookout watch or a quiet-pool project for this world. Mira's dialogue and goals change. Ivo walks two cardinal steps inside the lookout clearing, yielding to ready player occupancy, and offers an optional level 5 rematch. A confirmed Field Archive share finishes the chosen public route notes. Sharing the archive first also works. Later branch choices do not undo the first one. Nothing claims a battle victory, grants an item or publishes any other private visit.

## Owner review and publication

The local launcher uses `AdventureWorkshop.action(session, worlds, action, payload)` with these strict actions:

- `adventure_read`: exactly `world`.
- `adventure_preview`: exactly `world` and `adventure`, with adventure `lantern-trail`.
- `adventure_apply`: exactly `world`, preview `token` and boolean `confirmed` set to `true`.

The parent-owned hosted HTTPS adapter uses the same authority helpers against its already owner-authorized server object:

```python
from world.product_adventure import (
    read_adventures, preview_adventure, apply_adventure,
)

catalogue = read_adventures(server)
review = preview_adventure(server, 'lantern-trail')
# Present the named recipe, guide, prerequisites and validation to the owner.
# After their separate confirmation, while no players are connected:
result = apply_adventure(server, review['token'], confirmed=True)
```

These helpers do not authenticate a transport. The caller must enforce existing world-owner authorization. They accept no source, plan, trainer identity or arbitrary admin command. Do not expose them on player CONTROL connections. The parent supplies the protected hosted endpoints and consumer UI glue. No standalone script should open another SQLite connection against a live authority.

Preview makes no world writes. It returns a server-local, single-use review token valid for 15 minutes, the exact inert route/cast/walk recipe, proposed rows, report, prose guide and prerequisites. Apply rechecks the world ID, event sequence, active revision, verified mechanic source, complete mechanic state, objects, tiles, cursor, archived identities and labels. Any live player or pending mechanic job prevents publication. No game is disconnected automatically.

Apply composes existing chapter compilers over the verified current source and uses the existing kernel mechanic sandbox. It waits for actual stage and run results, never a server-loop callback. The helper releases its own server lock during those bounded sandbox calls, then rechecks the entire checkpoint. Calling under an existing reentrant server lock is supported, though the parent should avoid holding an outer server lock during staging. There is no async polling or speculative Saved response.

The survey and place rows are queued before the existing `_replace_cave(..., character_continuation=...)` transaction. Archive, cast, module state, place identity and survey commit together. A failed module insert rolls everything back, including public history. Existing geography stays archived byte-for-byte under its old label. Existing residents keep their identities, state and revision-scoped objects. Import selects the new shared destination only on the first successful publication.

Repeating a completed import is an idempotent no-op, even after restart or while another archived destination is active. It does not move players, switch maps, reset chapters or replay the public story. A partial installation, conflicting resident identity or a pre-existing unowned identical route revision is refused instead of being adopted or overwritten. Ambiguous HTTP failures must be followed by a new read, not an automatic apply retry.

## Release activation requirements

Before any live publication, the release owner must retain a verified world backup, confirm the intended world and owner consent, ensure no connected games or pending work, and pair the approved app/native cohort. The parent owns hosted publication and actual native acceptance. This worker did not edit a human profile, save or live world, call a model, install a release or connect to the host.

The acceptance session must verify entry with an ordinary starter, the visible Mira welcome, consumer survey start and guidance, private completion/return, an optional explicitly confirmed public branch, short walking and a native optional battle. Python protocol tests exercise authenticated dispatch and kernel sandbox persistence, but are not a substitute for that matched native session.

## Tests

Run from the application checkout:

```sh
PYTHONPATH=test/world:. python3 -m unittest test_product_adventure.Adventure -v
```

The tests use disposable authority roots, real sandbox processes, authenticated native-wire dispatch, explicit survey share confirmation, actual authority commits and authority restarts. They cover private completion, both public choices, archive-first ordering, walking occupancy and restart, optional battle offers, existing-content preservation, exact review binding, failed atomic publication, incomplete-import refusal and owner helper/adapter contracts. They do not simulate a native battle victory or contact a real host.
