# Player trade board

The trade board helps trainers find one another. It is an optional, world-local advertising system, not a trading engine: the server never inspects or transfers Pokémon, items, money or saves. Listings are player-written, public and unverified. Players must use the existing in-game trade flow and give its normal consent to perform a trade.

Choose WORLD > Trade board or open in-game chat. First send `/trade help`; the updated client requires the private `Trade: protocol 1` reply before sending other trade-board commands. On an older server the harmless help probe may appear in public chat, but the updated client blocks the other commands. Older game clients do not have this guard and should only use trade-board commands on a known compatible server.

- `/trade offer DESCRIPTION` publishes a 1–60 character description, such as `Torchic for Treecko`. A trainer can have one active listing. It expires after seven days.
- `/trade list` or `/trade list PAGE` shows public listings; `/trade mine` shows your listing; `/trade remove` removes it.
- `/trade contact ID` privately tells an online listing owner that you are interested. It does not open a trade, convey consent, reserve a Pokémon or guarantee the listing is accurate. If the owner is offline or chat is unavailable, no contact request is sent.

The World authority stores listings separately from trainer saves. A world can hold up to 512 active listings. Expired listings are removed when the board is next used. A connection failure can make the result of a command uncertain; check `/trade mine` before repeating an offer.

The current implementation uses the existing chat protocol and is independent of Pokémon species IDs and game save layout. It can carry over to Expansion when the existing chat protocol is supported there, but Expansion-client compatibility and real two-client gameplay are not yet verified. There is no cross-world board, escrow, currency, automated trade, or proof that a player owns what they advertise.
