# Playable cast projects at the original actor

While a supported original actor's supplemental dialogue is open, START opens
its local project. SELECT pages through choices, A commits the shown choice,
and B returns to the original script. SELECT from the initial dialogue still
opens the existing speaker/listener conversation instead. No chat command is
needed to play a project choice.

The original actor must own the immutable initiative, and the scene must be
available at the player's actual current map. Remote project places cannot be
operated from this panel. Autonomous actor-only turns never appear as player
choices. Actor commitments can open or change the available choices between
visits; player choices commit through the existing opportunity authority and
can change subsequent shared opportunities and supported activity conditions.

The panel labels choices as changes to shared project state, not group consensus
or advice. Another player can make the viewed revision stale, in which case the
choice is refused rather than silently applying it to a changed world. Each
view is bound to the current connection, save, original actor, authored version,
project revision and short expiry. Reopening refreshes it. No automatic retry,
public chat fallback, original-script unlock or new personal-history disclosure.

After committing, the exact authority result is displayed. Another conversation
can expose the next available scene. B does not undo a committed choice. No
native inventory, money, progression, automatic reward, physical NPC travel or
battle outcome is created. Existing abstract project outcomes remain abstract.

Tests exercise real authored project compilation, independent authority action,
CORE PROJECT packets, choice commit, two-player stale views, save switching,
restart and replay refusal. Native component tests compile the actual parser,
input filter and panel state machine with explicit engine/UI doubles, including
START, SELECT, A choice, result, B and old-server refusal. Full linked rendering,
button behavior alongside original dialogue, long-label pagination and live
model authoring still require Maya's integration QA. App engine pin is unchanged.
