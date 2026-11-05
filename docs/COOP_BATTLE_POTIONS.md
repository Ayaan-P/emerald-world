# Co-op battle medicine: focused candidate

This source candidate adds the following items for the acting trainer's active Pokémon in shared wild and trainer battles:

- Potion, Super Potion, Hyper Potion and Max Potion.
- Fresh Water, Soda Pop, Lemonade and Moomoo Milk.
- Antidote, Burn Heal, Ice Heal, Awakening, Paralyze Heal, Full Heal and Full Restore.

The ordinary Gen 3 HP amounts and status effects are preserved, including removing Nightmare when Awakening cures sleep. The in-bag confirmation explicitly says the target is the active Pokémon. Fainted targets and items with no effect are rejected. Revives, PP items, other medicines and selecting reserve Pokémon are not included. Full Heal and Full Restore also cure battle confusion.

Selection does not consume the item. At execution the authoritative engine validates the requested item, active HP and status, then sends a session-scoped command to the owning controller. Only that controller can validate its pending selection and debit its own bag. The engine waits for its reply and uses the standard battle HP-bar, status and update scripts. It never reads or debits the partner's bag. Medicine debits are tracked separately per trainer and refunded if an uncommitted shared battle aborts or its private party merge is rejected; a valid bilateral completion retains them. A failed refund leaves its ledger intact and prevents a new co-op battle until a retry succeeds.

Co-op exchange protocol version increases from 3 to 6. Both players must use the updated build; older peers, including the earlier version-4 and version-5 drafts, are rejected at the initial exchange rather than failing halfway through a battle. This is a compatibility change that must be included in the combined candidate and release coordination. Solo and ordinary non-co-op battles retain their existing item behavior.

Focused tests compile the production ownership/action and medicine code against disposable stubs, including both owner slots, malformed or stale commands, no-effect cases, status updates, Nightmare cleanup, repeat consumption, ordered acknowledgements and abort refunds. Existing co-op and battle payload regressions also run. These are not a native game build or live two-client battle, graphical bag confirmation, disconnect/WAN, real save/reload or proof that every item or party target is supported. Test the combined candidate on disposable profiles before release.

On the stacked reserve-target branch, this active-only scope is extended as described in `docs/COOP_BATTLE_MEDICINE_RESERVES.md`; the combined co-op version there is 7.
