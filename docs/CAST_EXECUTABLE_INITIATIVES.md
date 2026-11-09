# Cast-owned executable projects

The canonical author can now install a new project, not just choose from a host's
preinstalled story packs. The optional `initiative` field in `canonical_actions`
uses the existing opportunities pack format (`id`, `title`, `qualities`, `scenes`).
It is installed atomically with the actor decision and public publication receipt.
No deployment, command, or player action is needed to finish that installation.

## Real loop

1. An existing actor considers inspected public events and authors an initiative.
   It contains public shared state, choices assigned to existing actors, and at
   least one player-facing scene. The owner must have a supported actor turn.
2. The existing autonomous `world_action` dispatcher executes that actor's retained
   intention against the exact current project revision. It commits actual shared
   qualities, consumed scenes and an attributed public action receipt together.
3. Another followed actor can consider publication or a real action receipt,
   independently choose a later available action, wait, or do something else.
   Being named in the plan never means that actor agreed or participated.
4. Later directional relationship assessments can cite another actor's **committed
   choice**. Merely proposing a project does not qualify. An assessment is not
   mutual affection, a meeting, or a simulated physical event.
5. Players see the resulting current choices through the existing `/story PACK`
   interface at the project location. `/guild cast ACTOR initiatives`, at the
   actor's normal safe location, lists its projects and committed progress. The
   original NPC supplemental reply points to this command when no higher-priority
   objective is present. Quiet players and their private profiles are untouched.

`inspect.cast_initiatives` exposes public ownership, immutable digest, publication
receipt, and actual per-place quality/scene state. `inspect.cast_world_actions`
continues to expose currently executable actor choices. The configured author
chooses goals and actions; this patch does not launch a model or install a fixed
storyline. Existing followed-actor event and bounded quiet-world scheduling apply.

## Limits and persistence

- Eight immutable projects per actor; existing global story/action limits apply.
- Project IDs cannot replace another owner's or host's pack. Removing the field
  from the current actor record does not erase published history or state.
- Only public place qualities and known native places in the actor's interests.
  No private mysteries, trainer qualities, player targeting, rewards or story flags.
- These are executable **shared narrative projects**, not physical construction,
  travel, NPC animation, battles, inventory transfers or Pokémon development.
  Authored text is not proof that any such action occurred.
- Actor intentions are separate from the project specification. A project offers
  possibilities; its actor turns are not automatically assigned as intentions to
  other actors. State revisions and actual requirements gate every execution.
- Normal Emerald services and progression remain unchanged. No engine patch or
  native gitlink change is needed for this app-side slice. Existing paired CAST
  hooks provide its supplemental objective; `/story` remains the current in-game
  chat interface, not a new graphical project screen.

## Verification

`test_canonical_initiatives` uses actual canonical compilation, authority module
admission, autonomous dispatch, shared story state, reaction queue, original CAST
response and SQLite restart. A deterministic author fixture creates a project;
another actor independently contributes; actual choices change both players'
available story interactions and ground later directional assessments. It also
checks transaction rollback, ownership, immutability and rejection of private
inputs/unsupported participation claims. This is not live-model or rendered-game QA.
