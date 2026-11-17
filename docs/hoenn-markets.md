# Living Hoenn marts (experimental)

An existing town can offer something different on the next visit without becoming a generated side map. The normal mart clerk retains Buy, Sell and Quit. When a current world-authored shelf is available, **Visiting stock** opens the same native shopping screen with a separate small catalog. Players see native item descriptions and prices, choose quantities and confirm normally. Buy still opens the original stock. No command, purchase, travel or battle is forced.

This reuses the existing actor runtime and its ordinary retail item catalog. `world.arrange_market_shelf(site, items, minutes)` lets an enrolled canonical or world actor open, revise or close a bounded shelf at one of eleven original Hoenn marts. Existing world evidence, goals and plan dependencies can inform that choice; no automatic story or scripted supply event is installed. The capability is an authored retail opportunity, **not** evidence that an original clerk agreed, a character travelled, goods were delivered or revenue was earned. Other actors cannot overwrite a still-active shelf. Publication is an ordinary durable world receipt. A later author may respond to it through existing world mechanisms, but this feature does not manufacture customer or purchase history.

## Actual boundaries

- Oldale, Petalburg, Rustboro, Slateport, Mauville, Verdanturf, Fallarbor, Lavaridge, Fortree, Mossdeep and Sootopolis marts. Exact native map IDs are checked against the existing app catalog. Lilycove department store, decorations, original bazaar vendors, Kanto and generated character shops are unchanged.
- Up to eight items from the already reviewed ordinary ball/medicine/repel/rope retail catalog. No key items, evolution items, rare candy, custom price, sale discount or finite shared stock. Availability can differ from the ordinary mart's progression stock; native prices still apply. This is an intentional optional balance change, not claimed stock Emerald pacing.
- Duration up to 24 hours; owner may revise/close. Requests use the authenticated native LINK and fresh current-map presence. No private bag, money, party, save lineage or purchases are uploaded.
- Native clients poll every two seconds. A response leases a shelf for at most 15 seconds of native pump time. Offline or unavailable leaves the ordinary shop. A visitor arriving and talking before the first response may see only the ordinary menu; speaking again after a refresh can expose the shelf. No blocking wait or forced reopening.
- Entering a shop copies the current shelf into visit-owned storage. Expiry, closure, refresh or disconnect does not change an already opened checkout. Leaving ends that snapshot. Reopening uses a currently valid cache, so closure may take a poll/lease interval to disappear. Pausing the client pauses pump timers.
- Existing native price calculation, quantity/affordability, bag-full checks, item obtained flags, purchase history, bonus ball logic and money deduction are unchanged. Normal saves remain normal; there is no new transactional save format or claim of crash-atomic purchase beyond the original game.
- Buy, Visiting stock and Sell can be used in the same visit without leaking the supplemental list into ordinary or decoration shops. Original script resumes on Quit as before.

## Build and QA

Default `EW_HOENN_MARKETS=0`. App switch `--development --experimental-hoenn-markets` enables only this optional native UI/cache. No shelf exists until an authorized actor configures one. This is a separate stack on app #485/native #123; Maya's #410/#72 are untouched.

Nine focused tests pass: real catalog map identities, fresh-map wire scope, author ownership, expiry/close, invalid items, SQLite restart/outer transaction rollback, authenticated dispatch ordering, compiled production native cache/lease/snapshot/disconnect behavior, disabled no-wire behavior, and extracted actual shop-entry/Buy/Visiting-stock/decoration callbacks under UBSan. Source comparison confirms five stock checkout/price functions are byte-for-byte unchanged from native #123. Native shop source passes syntax checks with actual text preprocessing both enabled and disabled against recovered headers; existing portable pointer-cast warnings remain.

These are component and source checks. Full exact-head native linking, rendered menu layout, actual shopping/bag-full/insufficient-money play, two-client world updates, save/reload and integration regression QA have **not** been run. No real saves, live provider calls, shared-money mutations, release or merge. Maya owns final integration and gameplay/balance review.

Paired native draft: https://github.com/Ayaan-P/pokeemerald-expansion-native/pull/124 at `b4b3fc0851d8bf9ffd279b7f913818d9917020bb`. Run `python3 -m unittest discover -s test -p test_hoenn_markets.py -v` with that native submodule materialized.
