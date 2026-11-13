# Agent-authored ordinary retail services

A recurring world-owned character can choose `world.configure_shop` with a JSON
list of up to eight IDs from the discovered reviewed retail catalog. Empty closes
the service. This is a general service primitive, not a named-character scenario:
agents may open, revise or close it in response to committed events and plans.

The paired native client advertises CHARSHOP1. After the usual NPC greeting,
R Shop opens the **existing Expansion Poké Mart** with the chosen catalog.
Purchase confirmation, prices, money, bag capacity, quantities, sale behavior and
item eligibility remain the engine's normal logic. Neither the model nor server
sets prices, grants items, edits saves or reports that a purchase happened.
Original shops and canonical scripts are unchanged.

The allowlist is ordinary balls, recovery medicine, repels and Escape Rope.
It excludes key items, Master Balls, TMs and arbitrary item/script identifiers.
Native independently checks count, identities, duplicates and bounds. Unknown
clients receive no shop rows; new clients peel CHARSHOP1 first on old-server
authentication refusal without discarding existing capabilities.

Catalogs are persistent authority state. Opening requires the same character
version, exact region and stationary original interaction position. Once opened,
the item list is frozen in native-owned memory until exit, even if the network
disconnects or the agent changes its service. The new entry callback unlocks
field controls rather than resuming a stale vanilla script context.

This is **unlimited ordinary retail**, not a finite shared inventory or a
player-to-NPC trade. Money does not become NPC income; retail balls do not
replenish the separate experimental capture ledger. Sales are not public history
because there is no trusted purchase-report bridge. Only actual catalog changes
are committed to history. Personal player bags and money remain independent.

Validation: actual app author-plan admission and negotiated snapshot feed the
actual C parser/menu/native-shop entry functions with platform fixtures. Tests
also cover closing, restart, unsupported clients and invalid catalogs. Full
linked/rendered shop focus, buying/selling, save/reload, shop criteria filtering,
disconnect and two-client QA remain for Maya. No live model call is claimed.

Paired native draft #38: 160100b8c906429f2c4a61fc3366907b81463e8d.
