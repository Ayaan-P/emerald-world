# Regional Pokédex display

Based on native #94 (`348e39b7047f1868b0126f494d4bea91e4e3e7bc`). This is a separate stacked draft, not Maya's #72 or the RC12 release.

In combined Kanto builds the personal source region is captured when opening the Pokédex or a newly caught entry. Regional list membership/order, list length, seen/owned totals, entry and HGSS stats numbering, search captions, and the regional label use that captured region. Returning from search/entry screens keeps the same display session; reopening after regional travel resets the scroll position. National mode remains national. Default Emerald still uses Hoenn; default FireRed uses Kanto.

The regional Kanto label is a small original pixel-letter sprite with separately allocated image tiles, released through the existing DestroySprite lifecycle. It never overwrites the shared interface tile sheet. Hoenn and national label assets are unchanged. No donor assets are imported.

This changes UI queries only. Global NationalToRegionalOrder, RegionalToNationalOrder, GetRegionalPokedexCount, completion/rating rules, trade eligibility and save flags are unchanged. Seen/caught ownership stays personal and national-indexed. It adds no networking, identity sharing, migration or save format.

Validation: `python -m unittest discover -s tests -p test_regional_dex_ui.py -v` passes two tests: actual UI policy plus actual native order tables/mapping/count functions compiled under vanilla Emerald, combined Emerald/Kanto and FireRed; and source wiring checks across classic/HGSS list/search/entry paths and independent label allocation. Fixtures cover Bulbasaur/Treecko membership, regional counts, frozen sessions, reopening/reset and unchanged global count policy.

Not yet verified: full native link, rendered label readability/palette, controller-driven search/sort/back/caught-entry transitions, sprite allocation exhaustion or repeated screen teardown in the running engine, regional area-map details, or a full Kanto playthrough. The policy test does not execute the complete UI or sprite engine. Combined Kanto remains an experimental build; no claim of campaign completeness or linked QA.

App integration: native pin c9af08f3ec11930b9617d4a40fdf1df5ad910ef8. App parent #446 b88238d3cfcdd0e48243b438261e44b2000bc81e, separate from Maya #410 and not based on RC12. Existing experimental combined-region build flags apply; no new server or save protocol.
