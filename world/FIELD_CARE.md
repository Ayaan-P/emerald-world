# Experimental learned-move field care

Paired with native #76 at `59d0fb4e70ca5e0b11d80816892ebe7f0e149a84`. This app branch is a child of #416 (`6d591277337a7cfb3387d6126e0ef2ec065e0597`), not Maya #410 or RC12. Native is a child of #75, not Maya #72. This pin includes the existing independent feature stack; integration must preserve release fixes separately.

Use `--development --experimental-field-moves`, disabled by default. In the native party WORLD MOVE chooser select a genuinely learned Recover, Slack Off, Heal Order or Heal Pulse. Select a party slot with left/right and explicitly confirm with Enter. Recover-like moves act on the user; Heal Pulse on another own-party member. The last option retains facing shared-object actions. Escape cancels before execution.

New explicit field rule, not a simulated battle: one real PP restores up to half maximum HP (minimum one), only to conscious non-egg party members. No battle-only ability/item modifiers, revival, status cure, remote player healing, autonomous NPC care or fabricated battle outcomes. Stock Soft-Boiled/Milk Drink HP-transfer menus are unchanged. The native helper changes real HP/PP in one synchronous frame; normal manual saving retains both. Unsaved restart reverts both, with no receipt that can redeliver healing. A Pokémon cry is played; there is no bespoke healing animation.

Entire-party snapshot/owner/location/learned-move and current HP/PP checks protect confirmation. Facilities, Battle Tent challenge rooms, Safari, scripts, link contexts and fades reject care. No new care message/public event is sent; separately consented reporting retains its own behavior.

Validation: five native compiled-source/component tests pass. App field flags, HM launch, move UI, learned-move proof, visuals and selector regressions run against this pin. Full linked native build, rendered/audio UI, save/load and multiplayer checks remain for QA. No live provider sessions. This is a draft, not release-ready or verified live gameplay.
