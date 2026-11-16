# Active-partner medicine (experimental, default off)

Independent stack on app #475 / native #113. Enable `--experimental-partner-medicine --development` only for a matching pair of disposable native clients. It changes the co-op wire version; incompatible peers reject exchange before mixed parties are staged. Other experimental save/story options remain independent and disabled unless explicitly selected.

## Player interaction

Selecting supported medicine in a co-op battle asks whether to use it on the partner's active Pokémon or choose from the player's own party. YES selects partner support; NO, including the standard yes/no menu's B behavior, opens the existing own-party selection, where the player can back out normally. The target is explicitly the partner's active Pokémon **when the item action resolves**, not a secretly frozen selection from an earlier turn. Partner switching before that turn therefore changes the active target. No partner bench is displayed or selectable.

The spender uses one normal battle item action. The target's native owner validates its current active slot, HP, maximum HP, status and battle generation before the spender's controller is asked to consume anything. A stale/invalid/absent/fainted target or failed/no-effect action does not consume medicine. The spender must still have the selected item. The existing native healing/status script addresses the partner controller; no direct writes to another player's save or bench are introduced.

Supported: Potion, Super Potion, Hyper Potion, Max Potion, Fresh Water, Soda Pop, Lemonade, Moomoo Milk, Antidote, Burn Heal, Ice Heal, Awakening, Paralyze Heal, Full Heal and Full Restore. Effects use Expansion's existing configured medicine helper. Revive and Max Revive remain own-party actions; partner revival is unsupported. No PP recovery, stat items or other medicines added.

## Transaction and interruption

A distinct EXPUPDATE tag 250 and item reply family 0xE000 carry bounded support CHECK/SPEND requests. Existing own-party medicine ownership guards are unchanged. The target owner checks its own active Pokémon; only the spender validates local intent and debits the private bag. Clearing that intent prevents duplicate SPEND. No turn or switch advances between target CHECK and spender ACK. Status/HP effects then use the target battler, while attribution remains with the spender.

The existing private medicine ledger refunds on ordinary co-op abort or invalid private-party reconciliation and is consumed only by the existing committed-result path. This is not a new durable cross-save transaction or a promise of power-loss recovery. Existing interrupted-link/reset limitations remain. The feature adds no automatic save, new receipt or progression credit.

## Verification

- Compiled production support transaction and refund function with deterministic controller/bag/effect doubles. Both player roles cover correct target, stale generation/slot/HP, wrong controller, duplicate debit, failed target check, missing item, fainted target, correct target-only HP/status scheduling and one-time refund. All 15/2 allow-list inclusions/exclusions checked.
- Source wiring checks cover default-off, distinct wire version throughout header/mon/completion exchange, abort cleanup, native controller handler, action dispatch and bag choice.
- Build-option checks require explicit development and propagate the same feature flag to native and pointer-reference builds.

These are component checks, not a full engine build or rendered playtest. Configured medicine effect calculations are reused unchanged; the new state-machine test doubles their arithmetic and does not certify every configured effect. Native linking, string assembly, bag windows, both actual player roles, partner switching, healing/status animations and interruption during real controller exchange remain unverified. Full private native checkout is blocked by current shell Git authentication; the connector offers no archive. Keep default off until matched two-client QA using disposable saves. No real saves or live providers were used. Maya's integration and held payloads are untouched.
