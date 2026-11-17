# Public opportunities on the original Hoenn map

The original PokéNav region map gains an optional **SELECT WORLD** view. Move its ordinary cursor to a Hoenn town/route, then inspect currently configured land encounters, rod populations or optional mart stock. L cycles details; SELECT returns to the ordinary place/landmark panel. A zoom, B exit and the existing R Fly eligibility/behavior remain unchanged. There is no teleport, enrollment, reward, party selection or shared progression operation in this feature.

This is a read-only connection to actual existing `shared_outbreaks`, `shared_fishing` and `hoenn_market_shelves` state. It does not create another event schema, install a preset, start a provider, fabricate sightings or promise an encounter. Characters can already change those systems through their existing capabilities. The player can now inspect a relevant place in the game's own map and decide whether to travel, fish, explore or shop normally.

Pages report configured species/levels/base slot weights, or ordinary visiting-stock items. The first page says these are world settings, not sightings, and personal rules apply. Personal saved outbreaks take priority; special fishing checks, ordinary rod eligibility, species shuffle and native capture ownership remain unchanged. Mart pages require the client build's existing market feature and purchases still occur through the original mart at stock prices. No private party, Pokédex, save progress, location history or other player's result is queried or published. Long labels are clipped to the existing panel width; this is informational, not a transaction confirmation.

## Scope and lifecycle

Only the original 16 Hoenn towns/cities and Routes101–134 are mapped. Native named section constants and compile-time range assertions bind the cursor to these names; selected-build authority map membership is checked again. Kanto, caves, event islands and unsupported sections are not mapped to invented places. Event-island zoom-disabled behavior is unchanged. The existing map and game remain available with no active authored configuration.

The authenticated link channel accepts a separate WM query with selected place, page, nonce and supported-feature mask. Each response is an atomic four-line bounded snapshot with a maximum five-second lease. Nonce changes on a new request, cursor change or page selection; replies to old selections cannot repaint the current one. Empty, unavailable and expired states are distinct. Existing connection/session guards reject requests during native link activities. Disconnect/menu cleanup cancels queries. There is no new native save state.

While the view is open, requests refresh every120 link pumps. Pausing also pauses this local clock; closing/expiry may take that interval/lease to display. A source can change between viewing and arrival, and an already opened mart keeps its existing frozen-visit rules. This is not a reservation or a guarantee that a personal save will produce the displayed encounter. Fresh authenticated presence remains required; if the existing client stops presence updates in a menu, the panel fails closed rather than claiming stale offers.

`EW_MAP_OFFERS=0` by default. Experimental build: `--development --experimental-map-offers`; existing visiting-stock pages also require the separate `--experimental-hoenn-markets`. Land/fishing pages are filtered by the connection's existing native capabilities. No new author capability or automatic configuration is required.

## Verification and integration

Six focused tests pass: public read-only projection, actual fishing weights/slot pages, capability/scope/expiry checks, authenticated server dispatch, compiled actual native sender/cache under UBSan in both flag modes (including stale selection/replay/session checks), and source checks for renderer/navigation wiring. Python compilation passes. These tests use fixture world configuration and simulated engine dependencies; they are not a rendered map or a live encounter/shop test.

Full native compilation is blocked in the recovered checkout by generated `INCGFX` assets and `data/region_map/city_map_tilemaps.h`. The panel's zoom/background placement, help-bar width, text clipping, original A/B/R behavior and live menu presence refresh need exact-binary rendered QA. No full build/link, real save, multiplayer or provider QA is claimed. All default-off source work is a draft for Maya, not release-ready gameplay.

Separate stack on corrected app #489 `49ea17944bdd815ff29b86277201db0314744c93` and native #127 `adcb97a611132eacc5aac2729b4410004d570b92`. Preserves the corrected GET2 rematch sender, prior features, Maya #410/#72 and all held/uncertain operations. Maya owns integration/release.

Paired native draft #128: https://github.com/Ayaan-P/pokeemerald-expansion-native/pull/128 at `4c3a5bbb38198f8b5c74d265b03da4a22e0be257`. Test command: `python3 -m unittest discover -s test -p test_map_offers.py -v`.
