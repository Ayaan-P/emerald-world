# Player-responsive Hoenn markets (experimental)

This extends the existing real Hoenn mart capability rather than creating a simulated economy or another agent executor. Default OFF: `EW_MARKET_REACTIONS=0`. Build only with `--development --experimental-hoenn-markets --experimental-market-reactions` and the matching authority/native pair.

## Actual player loop

An agent can already arrange up to eight reviewed ordinary items in an original mart's Visiting stock. It can now independently author a bounded future-history rule using the existing `world.arrange_market_shelf` capability and `hoenn_market_purchase_reported` trigger. That rule may choose another valid shelf for later visits after a genuine reported purchase. No response, fixed merchant personality, quest, scarcity or economy is installed by this feature. Actors retain creative control, ordinary ownership checks and existing limits.

With this option enabled, Visiting stock is labelled **Community stock**. Players still choose native item quantities and see native prices. The **existing** purchase confirmation discloses the anonymous item/count report and asks whether to buy. There is no second approval menu, team vote or mandatory settings task. Normal Buy and Sell retain ordinary private behavior. Players can decline or buy the usual stock instead.

Only the actual successful bag-credit → money-debit callback sends a report. Bag-full, cancelled selection, declined purchase, insufficient funds, ordinary stock, decorative shops, generic NPC retail and sale transactions do not. Bonus Premier Balls are not purchased goods and are not reported. Existing prices, discounts, affordability, bag capacity, owned inventory, money, purchase stats, bonus logic and normal save behavior stay native.

The report refers to the exact frozen shelf revision used by this shop visit. A successful authority receipt persists in anonymous world history. Existing actor inspection shows recent reports. If an agent authored a matching valid reaction, its real shelf executor changes the catalog in SQLite; a later visitor gets the changed catalog in the actual native shop. Current shoppers retain their admitted snapshot. Nobody's existing checkout is silently swapped or cancelled by someone else's choice.

`/market status` distinguishes the last acknowledged report from sent/unconfirmed. A receipt is not a promise that a character will react. New shelves use the existing publication duration (up to 24 hours), and history remains available afterward. There is no automatic profit, stock depletion, delivery, inflation, purchase reward, NPC agreement or retroactive attribution.

## Truth, privacy and failure

Reports contain site, author of the shelf, shelf revision, purchased item ID and quantity, **not** buyer/partner identity, bag contents, money, party, save lineage or account information. Confirmation discloses sending that item/count into the world. Previously committed public history remains after leaving. This is a consenting native **client report**, not cryptographic proof or a transaction signed by a save file. A modified client can lie; a later save rollback may restore private items/money. Do not use these reports as verified economic settlement or limited-stock accounting.

The native item and money operations remain the original local operations. Reporting can fail after the purchase. There is no refund, automatic resend, replay of the purchase or cross-save atomicity claim. Interrupted native checkout retains stock engine save semantics; this feature does not fix or change them. Disconnect clears report/cached-visit ownership and falls back to the admitted local shop; it cannot undo purchases.

Authority reports require the current authenticated channel, fresh presence at the same reviewed mart, no active encounter/link session, an issued shelf revision and an item in that frozen catalog. At most 16 issued revisions per connection are retained for at most two hours since their last issuance. Very long visits/extreme catalog churn can therefore lose reporting without losing their local purchase. Repeated sequence numbers cannot duplicate a receipt on the same connection. Disconnect/restart invalidates unsubmitted witnesses; no cross-connection report retries occur. SQLite commits the report and history atomically; failure returns unconfirmed.

The original legacy `MK GET 1` protocol remains unchanged. The opt-in native cohort uses `MK GET 2` with revision-bearing shelves and `MK BUY` reports. Personal purchases are not sent by older clients. No new save payload, provider call, real-save test, integration-branch modification or deployment.

## Agent reuse and current validation

The existing history-rule system continues to enforce literal arguments, future-only triggers, two active rules per actor, 32 globally, cooldowns, attempt budgets, actor availability, ownership and atomic effect/result receipts. A purchase does not authorize stealing another actor's active shelf. Rules can respond to exact item/site/author/revision/quantity filters; they do not interpolate arbitrary event code. The feature adds an operation and trigger to that system, not another scheduling framework.

Run `PYTHONDONTWRITEBYTECODE=1 python test/test_market_reactions.py` with the exact native submodule initialized. Ten synthetic tests pass, including:

- Actual completed native checkout callbacks, with credit before debit before report; bag-full and ordinary purchases excluded.
- Enabled/disabled production native cache/report code under UBSan; frozen old revisions, owner/map/session checks, malformed revisions and disconnect reset.
- Actual server dispatcher, issued revision/item validation, replay and lifetime rejection, legacy wire compatibility.
- Real purchase report → existing history scheduler → **actual shelf configure executor** → changed native wire catalog, plus persistence across SQLite reopen and old frozen checkout validity. Map identity lookup is isolated in this fixture; it is not a live shop or a claim of rendered play.
- Failed receipt transaction rollback and blocked attempted takeover of another actor's shelf.

Native text preprocessing and shop/core syntax checks pass on/off using recovered headers and host shims. Existing host pointer-size cast warnings remain. Development-only configuration guard is tested. Full exact native link, rendered confirmation pagination, real in-game timing, two-client shopping, long pause/resume and save reload are **not tested**. Keep default off pending Maya's integration, balance and linked gameplay QA.
