# Private route concealment

A local, optional exploration mechanic in actual Hoenn: use a real learned concealing move to navigate past distant ordinary trainers rather than fight every sight encounter. No trainer is marked defeated, no EXP or reward is invented, and the player can still walk up and talk to fight normally. Other players keep their own detection and progression. No group vote or shared approval is involved.

## Actual interaction

With `--development --experimental-field-concealment`, a connected player whose conscious, non-egg Pokémon knows Smokescreen, Mist, Haze, Camouflage, Double Team or Minimize sees the existing WORLD MOVE party entry. In this mode alone only eligible learned moves appear; ordinary HM/field-skill menus retain their original behavior. Select the move and explicitly choose activation, or cancel (the default).

This is a disclosed NEW FIELD RULE, not simulated execution of those moves' battle effects: one native PP buys at most 24 cardinal steps and 1,800 native frames (about 30 game seconds). Walking within a distant normal trainer's otherwise valid line of sight suppresses that approach; their existing question-mark field effect signals the missed detection. Adjacent trainers still detect the player. All-direction and buried trainers retain stock detection. The native collision/path test still runs before the filter.

Running, bicycle/surf/dive/forced movement, maps, menus, scripts, battles, ownership changes, unexpected coordinate jumps and expiry end concealment. Avatar initialization clears it, including ordinary map/reload transitions. The player receives the Pokémon's native cry on activation. No new smoke/aura artwork or animation is claimed. After the overlay closes there is no new persistent timer HUD; native question-mark effects provide situational feedback.

A player can choose exploration now and revisit the undefeated trainer later, retaining the original fight and its rewards. This does not prevent direct interaction, coordinate-triggered story battles or other scripted events. It changes no story flag, NPC script, trainer range, trainer team, bag item, other player's battle or save layout.

## Boundaries

Native Hoenn route map group/number range and MAP_TYPE_ROUTE are both required, with on-foot stationary activation. Interiors, towns, Kanto, generated maps and linked battle activity are excluded. Actual source Pokémon, HP, egg/bad-egg status, move slot and PP are rechecked at activation; the party UI also rejects stale party/position/facing snapshots. Repeated confirm cannot debit twice.

Only PP changes in the actual own party, synchronously with starting the runtime effect. It is saved through ordinary native saving; no forced disk save, journal or server retry is added. Loading a save does not restore an unsaved concealment effect, even if the PP cost was saved. Canceling before activation spends nothing. Ending an activated effect is not a refund.

The mechanic is private. There is no activation, move, missed-detection or success report, fabricated character memory, shared trainer defeat or world-history credit. The current published app #493 lacks the earlier FM authority handler; this feature deliberately sends no FM requests and does not enable the unrelated authored-profile/facing-object menus when their original feature gate is off. It uses the existing connected native party/chat UI to enter the action. Agents cannot remotely activate it or spend player PP; no new agent-authoring capability is advertised.

## Status and verification

Local independent source work based on native #131 (377a7892e12ebcde149befa33d99c64c3b19342a) and app #493 (555e5c7fe03cb4c62e24b4f64800c02b7769e148). Default EW_FIELD_CONCEALMENT=0. No publication attempted, in accordance with the instruction not to open further PRs against the denied base. The local app builder still pins the old native commit; it is not an installed feature or a working published pair.

Four focused test methods pass. Actual core C and the extracted actual native confirm branch execute under UBSan, covering the disabled cohort, learned-move and PP guards, adjacent/normal/all-direction behavior, exact step/time expiration, question-mark argument restoration, duplicate input, stale party choice, map/save/battle/run/teleport cancellation and no double debit. Guarded trainer/avatar hooks round-trip to their exact original Git blobs. Original HM menu structure is checked.

Core module syntax passes against recovered native headers on/off. Full changed UI syntax also passes on/off with recovered feature headers and opaque SDL type declarations; this is not an SDL implementation or linked build. Compiling the entire current trainer source is blocked by the recovered checkout's absent generated constants/script_commands.h. No full native build, rendered detection/icon/party menu, script VM, disk save/reload or two-client gameplay was performed. No real saves or live providers were used. Maya owns integration and release; all held files/publications and her branches are untouched.
