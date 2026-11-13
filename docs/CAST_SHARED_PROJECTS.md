# Persistent projects shared across original cast locations

Separate follow-on to consolidated app #286 at f81be46. Native #26 remains pinned to f5b45730. No dependency on #287 or #288 and no changes to the consolidated branch.

## What changes for players

An agent can author one persistent project with distinct actor turns at existing locations. Rydel can make his own project decision at the Bike Shop; Steven can subsequently decide what to contribute from his house. Their actual committed project facts can jointly enable an existing activity such as Steven's optional companion invitation, or change the choices shown in the original NPC's existing project panel. Players need not carry messages or complete a quest to make these actor turns happen.

This is authority-executed shared project activity, not physical movement, a claim of a private meeting or a simulated battle. The regression uses fixture-authored decisions and the real reaction queue; it does not claim a live model chose them. No fixed project or character arc is installed automatically.

## Reusable state semantics

Story qualities now support three explicit scopes:

- `project`: one durable value shared across every scene location in that immutable pack.
- `place`: existing local values, independent at each scene location.
- `player`: existing private values, independent per trainer and never readable by actor actions.

Project-wide state is isolated by pack ID and persisted in `story_projects`. Packs using it use a project-wide revision for all choices. An intervening action in another town invalidates stale choices instead of overwriting or applying them under old assumptions. A project change, local change, scene completion and receipt commit together. Existing packs without project qualities retain their per-place revisions and behavior.

An actor still needs an explicitly assigned scene, satisfied requirements and a current action revision. Authored interests must include scene locations. No remote player interaction, player turn consumption, inventory grant, save flag change or fabricated outcome is introduced.

## Existing runtime connections

The normal canonical author contract explains the new scope. Initiative inspection, actor-action availability, original-actor activity admission and project-panel choices all read the same combined public state. Activity rules still require an actually committed actor scene; high initial values alone cannot unlock them.

## Verification boundary

Tests cover a real Rydel action at the Bike Shop, Steven's queued reaction and independently authored action at his house, and the actual existing `CORE ALLY` admission path becoming available. They also cover restart, cross-town stale requests, independent local state, private trainer isolation and project isolation. Native pin/protocol are unchanged. Maya owns linked build, rendered co-op and companion-battle/save QA; this branch is not a release.
