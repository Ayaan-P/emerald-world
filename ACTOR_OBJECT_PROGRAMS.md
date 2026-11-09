# Interactive object programs

`world.program_object` fills a gap between `world.populate` and `world.use_object`:
an autonomous world-owned actor can author actual behavior for a newly created
anchored prop, rather than needing a separate manually written Python handler.
The tool uses an actual nearby observation's `program_revision` and stages code
through the existing mechanic sandbox/admission, returning success only after the
program marker is committed. Existing handlers/controls are never overwritten.

A program is bounded JSON (`initial`, `states`). Each state has native-supported
`text`, `gfx` (rock/boulder 0/1), `on` action-to-state mapping, and `use` identifying
the currently available native A action, or empty for no player action. Up to four
states and four transitions per state fit existing plan limits. These are generic
state-machine instructions, not predefined plots, rewards or named actor roles.
Terminal states and branching agent choices are supported. There are no arbitrary
code snippets, script addresses, bags, currencies, guessed resources or new art.

Both player A and adjacent actor `world.use_object` invoke the same generated
handler, existing staging and exact map/ownership/collision validation. Each real
use persists the phase, changes the rendered prop text/appearance, and updates
advertised/default actions on the next normal mechanic tick. Native text can
briefly show the pre-transition value while admission is pending; no synchronous
animation is claimed. Other objects' existing custom handlers are preserved.

Combine create place -> populate anchored prop -> observe -> program object.
Players can then use it through the existing REGION_PROP/native A path. Combine
public object-use events with `world.await_event` and other supported capabilities
for larger programs. Installed programs are world state; withdrawing the author
plan does not uninstall them. Reprogramming, portable programs and arbitrary
terrain/native item effects are deliberately not advertised.

Object use now employs a verified reusable dispatcher with one replaceable request
and bounded current receipt. Repeated uses do not add source wrappers or hit the
old 32-use limit. Legacy wrappers and their receipts are preserved to prevent
replay. Durable authority events and plan receipts retain causal history. The
existing overall mechanic source size limit still applies to authoring new content,
not cumulative uses of installed programs.

Tests run the actual authority's authenticated generated-map interaction path,
program staging, native-wire player use, agent use, changed available actions and
restart. Rendering itself, linked-engine and live model QA remain unverified here.
