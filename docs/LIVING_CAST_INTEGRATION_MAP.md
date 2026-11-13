# Living-cast integration map for Maya

Verified 2026-11-09. This is a proposed integration map, not a combined build or release. All listed PRs were open and unmerged at inspection. No integration branch was changed.

## Base and exact heads

App main remains `80b14ebfbfd4dd4da2dc16d886a37f0db1f45516`. The ancestry is app #284 `ddc4760eb94a59ea8e572bdd654c693885a267f8` -> #285 `657ac8ff6f0a12b9dc9dddbaad655328ac60c893` -> #286. Native #25 `9d4635b00ddc0e221fca9e73f4e76ee809dd9303` is the base of #26; #25 itself includes the earlier RC12 native stack, including #24 mounts `488796e4959eb7f9d658abc7e8313e138acb3c87`. Do not treat #286/#26 as standalone patches against current main.

- App [#286](https://github.com/Ayaan-P/emerald-world/pull/286): `f81be46b6d9296e2710563af5878b3d4500b0b4e`; base `dot/rc12-core-story`. RC12: living cast proposals and result-driven growth.
- App [#287](https://github.com/Ayaan-P/emerald-world/pull/287): `cc3cd365405b472b9dfd2919262ec662057be82c`; base `dot/rc12-living-cast`. Connect canonical cast investigations to 2–4 trainer co-op.
- App [#288](https://github.com/Ayaan-P/emerald-world/pull/288): `b6c12cbbcd6bf60c13480ceeec2e6f16aa6dfc3e`; base `dot/rc12-living-cast`. Let canonical actors reconsider obstructed project plans.
- App [#289](https://github.com/Ayaan-P/emerald-world/pull/289): `2c871354db53faa93afea837b4feb2230ac0aeb6`; base `dot/rc12-living-cast`. Share persistent cast projects across original Hoenn locations.
- App [#290](https://github.com/Ayaan-P/emerald-world/pull/290): `c0574ccc3a2dd332f2090838eb68e75796070be4`; base `dot/cast-shared-projects`. Let cast maintain and revise ongoing project commitments.
- App [#291](https://github.com/Ayaan-P/emerald-world/pull/291): `831d950962cd83b8942f7d36a80a7a9b08d5f6af`; base `dot/rc12-living-cast`. Remember Steven's actual partner encounters within the player's save.
- App [#292](https://github.com/Ayaan-P/emerald-world/pull/292): `7490954d73de71f6fda07f2737916c4205f01917`; base `dot/coop-field-mysteries`. Keep canonical investigation credit within each trainer save.
- App [#293](https://github.com/Ayaan-P/emerald-world/pull/293): `679ddfc14a4a5151ed6b1b3d0784bc1aae3ef8a6`; base `dot/rc12-living-cast`. Enable open-ended private conversations with the original cast.
- App [#294](https://github.com/Ayaan-P/emerald-world/pull/294): `41851f028503ede76cf9dcf22c005d68e295a1ec`; base `dot/rc12-living-cast`. Pair reusable original actor movement with Rydel and Steven paths.
- App [#295](https://github.com/Ayaan-P/emerald-world/pull/295): `b6f3d0decafcfb347afa1ffff4177f302700d7f6`; base `dot/cast-native-paths`. Connect actor intentions to native activity and subsequent world decisions.
- App [#296](https://github.com/Ayaan-P/emerald-world/pull/296): `f77a6bf707f984e750a19ed951bd2a5d3b48adfa`; base `dot/rc12-living-cast`. Give living cast retained public experiences with exact source recall.
- App [#297](https://github.com/Ayaan-P/emerald-world/pull/297): `6d24b2d750bf667eb6c0ae401b8f171bc1b41f40`; base `dot/rc12-living-cast`. Connect Wally authored intentions to the original rematch ladder.
- App [#298](https://github.com/Ayaan-P/emerald-world/pull/298): `ea0a1f8640228c7ae6240387c1b676326709d242`; base `dot/rc12-living-cast`. Let real campaign trainer results inform existing cast actions.

- Native [#26](https://github.com/Ayaan-P/pokeemerald-expansion-native/pull/26): `f5b45730ef96debf512f501109b3388ab2342cc6`; base `dot/rc12-core-story`.
- Native [#27](https://github.com/Ayaan-P/pokeemerald-expansion-native/pull/27): `fc563ef178903b781f4812c32001b5892ecdd73f`; base `dot/rc12-canonical-cast`.
- Native [#28](https://github.com/Ayaan-P/pokeemerald-expansion-native/pull/28): `fde183bffe37c0ef8963f15f050782418cbafcb5`; base `dot/rc12-canonical-cast`.
- Native [#29](https://github.com/Ayaan-P/pokeemerald-expansion-native/pull/29): `5c9df043c97b6a998606d11f7aed21beea27d344`; base `dot/rc12-canonical-cast`.
- Native [#30](https://github.com/Ayaan-P/pokeemerald-expansion-native/pull/30): `8f7cc4f4a34cce0619bc3ba74cc35f640bb93abc`; base `dot/rc12-canonical-cast`.
- Native [#31](https://github.com/Ayaan-P/pokeemerald-expansion-native/pull/31): `27672498fcec76574776299af8b9bfb27d0cc768`; base `dot/rc12-canonical-cast`.

## Dependency and pin map

- #286 pairs with native #26.
- #287 -> #292 is the co-op investigation stack. Include #292 with #287 to keep participation credit within each save.
- #289 -> #290 is the cross-town ongoing project stack.
- #294 -> #295 is the original-actor path and intention-driven activity stack; both pair with native #29.
- #288 and #296 are independent app-only follow-ons to #286.
- #291 requires native #27.
- #293 requires native #28.
- #297 requires native #30.
- #298 requires native #31.
- App-only follow-ons retain the native #26 pin. They do not incorporate the sibling native features.
- The paired follow-ons' gitlinks, builder PINs and candidate manifests were checked and agree individually.

**There is no single head with all these features.** Native #27–31 are siblings of #26, not a chain. Taking the last app pin would drop other native features. Compose whichever native slices are selected first, record the resulting full commit, then set that one commit in the final app gitlink, builder PIN and candidate manifest. Do not run mixed binaries from sibling pins and describe them as the combined candidate.

## Recommended coherent first integration scope

For a focused living-cast campaign, start with #286/#26, then app #288, #289 -> #290, #296 and #298 with native #31. This connects ordinary campaign results to retained public experiences, independently maintained cross-town projects and existing original-NPC opportunities. It requires no new private worker and no player errand as the trigger. Standing battle participation is optional and save-specific.

Then add the complete #294 -> #295 / native #29 slice if reviewed reversible physical scenes are in scope. This adds real bounded Rydel/Steven motion and subsequent reactions, not arbitrary travel.

Treat #291/#293 private interactions, #287 -> #292 co-op investigations and #297 original Wally rematch readiness as separable optional packs. They remain useful, but adding them is a product/integration choice rather than an implicit dependency of the campaign loop.

## Runtime seams that require deliberate reconciliation

These are verified overlapping source paths, not claims of reproduced failures in a combined build:

- Native #27, #28, #30 and #31 modify world_core_story.c state, command dispatch, reset, callbacks or response handling. Preserve each feature's exact run/nonce checks and disconnect/new-game cleanup. A textual 'take ours/theirs' is not a valid integration strategy.
- Native #29 replaces the one-path scene controller with reviewed path tables. App #294/#295 must accompany it. Preserve step barriers, collision reservations and original actor restoration; do not convert authority completion into fabricated physical activity.
- App #291 and #293 both extend canonical_reflection.py. Preserve the distinction between explicit private-question snapshots, one-time reflection including approved encounter summaries, and the narrower standing decision-only scope. Do not expose any private input to the public author.
- Most app follow-ons edit canonical_cast.py validators, author contract and evidence routing. Preserve the union of the selected fields and event validators, not merely their records in state.
- #288 and #290 share canonical_world_actions.py. Preserve both obstruction feedback and ongoing action accounting.
- #287/#292 and #289/#290 share opportunity/runtime code. Save-scoped investigation admission must coexist with shared project qualities; shared project state is not personal progression.
- Every selected branch's test-module additions must be included in the consolidated check_living_cast.py list. Passing just the last sibling's list does not exercise the union.
- Builder manifests are per-branch. Reconcile one final native pin; never resolve pin conflicts by selecting the newest-looking hash.

## One connected player journey

1. Build the selected combined native commit with the normal Expansion builder and isolated test saves.
2. In the host launcher, choose an explicit public author provider/model, initialize and follow the original cast, then start the author. Canonical commissioning provides faithful seeds without fabricated history.
3. Meet original actors where that save's normal story makes them available. Supplemental talk returns to untouched story/service scripts. SELECT exposes shared conversation when authored; START exposes real local project choices when present.
4. A player can opt once into future anonymous ordinary trainer-result participation for that save. Continue normal battles. Actual captured results enter public history; other saves and private dialogue do not.
5. The public agent may retain a grounded interpretation, revise a goal, initiate a supported project action, ask another actor to contribute, or wait. The committed action can change available opportunities at original actor locations. There is no guaranteed model response or pre-scripted outcome.
6. If the movement pack is selected, an authored matching scene intention can offer the reviewed reversible local activity. Players join voluntarily; normal story/service control is restored before a completion receipt is admitted.
7. Existing party/save progression remains individual. No feature here claims independently simulated NPC battles, automatic earned evolution, arbitrary canon travel or synchronized whole-campaign cutscenes.

## Actual usability dependencies and readiness

- The public provider worker must be configured and running; published schemas alone do not generate a character plan. The launcher supports OpenAI Responses and Anthropic Messages for this public author. No live-provider behavior has been verified here.
- Private free-form conversations in #293 require the separately enabled existing private worker, currently OpenAI-scoped. Choosing Anthropic for the public author does not start or authorize that private path. This is a real setup boundary, not a claim that private chat works out of the box.
- Original actors are not summoned if vanilla progression hides them. Wally/Briney/Steven availability depends on each trainer's original save. This is intentional preservation of gameplay, not a shared-world spawning failure.
- Authored projects and conversations are optional model choices; examples in regressions are deterministic fixtures, not installed default arcs. First-run commissioning can produce initial greetings without public campaign events; meaningful later actions still need real supported evidence.
- At inspection, both authority-components and fixture-archive-install CI checks passed on every app head #286–298 listed above. Those checks are not full native linking, graphics, save/whiteout or model-quality QA.
- Latest #298 standalone checks: 311 app/component tests and six native/core tests passed. The union of sibling branches has not been built or tested.
- Full linked build, rendered original scripts/panels/movement, normal battle/whiteout cleanup, multiple real clients, save/reload and live model quality remain Maya's acceptance work. This workspace's native sources are partial component fixtures; a prior actual socket test was blocked by EPERM.
- No fundamental unusable wiring was found within the checked standalone pairings. The fundamental release gap is composition plus actual integrated native/model QA, not another small feature. No merges, releases or changes to Maya's branch were performed.

This map records feature heads before this documentation-only update to #298; its native pin and runtime content are unchanged.
