# RC12 progress and release handoff

## Status and priority

This is a progress checkpoint, not a release decision or a playable RC12 claim. The user requested history recovery and publication of current progress. Finish the combined Linux release first. Windows is a downstream friend-access target built from the same accepted app/engine pair, not a prerequisite for fixing or delivering Linux.

RC11.3 is the last recorded accepted installed and hosted baseline. Historical deployment failures were superseded by successful deployment and independent readback. This checkpoint does not reverify current production services, change a running game, deploy content, publish game binaries, or merge main.

## Recovered release history

- App RC11 was promoted through PR 277. Subsequent main CI fixture fixes were merged through PR 278. Local baseline evidence recorded 474 passing tests; that does not establish current hosted CI success.
- RC11.3 installation and hosted rollout were separately verified. The existing baseline includes private trainers/saves, ordinary multiplayer, generated Talk/Tag, authored resident walking/battles and explicit private/public exploration boundaries. Do not replace that baseline with historical vanilla code or repeat its acceptance as if it proved new RC12 features.
- The initial next-Dot source integration added generated-place expedition consent, resident relationship consequences, private geometry-aware guidance, grouped map outputs and opt-in encounter ecology.
- The later RC12 product-finishing effort added isolated adventure, objectives/UI, resident presentation, collection, build, Windows and recovery lanes. Worker completion never completed their parent integration.
- Work drifted into Windows compilation while Linux combined integration remained unfinished. A native Windows executable and local private archive now pass bounded Wine smoke tests, but do not contain an accepted combined RC12 product and do not constitute Windows-device acceptance.
- Newly fetched Dot RC12 branches extend the source landscape beyond the original finishing contract. Earlier instructions to ignore all new Dot increments are historical, not a current settled release inventory. Review dependencies and reconcile the newer work before claiming the final payload is frozen. Do not blindly merge complete older branch trees over released fixes.

## Existing finishing payload

1. Lantern Trail Outpost: a named resident-led adventure with Mira, Ivo and Ren, four landmarks, private survey progress, optional battle, explicit-share consequences, and owner catalogue/review/confirm/install.
2. Player Objectives & recap in the launcher, authenticated own-only activity projection, and native WORLD / My objectives with explicit Start, Guide and Refresh. No automatic survey start or publication.
3. Native generated-place offer negotiation and exact destination/revision/count consent. Authored battle name and portrait presentation with bounded literal selectors, not inferred trainer identity or numeric field graphics.
4. Curated expanded encounter ecology and Rustboro Mart paid collection access. Eleven badge-gated supplies cover both armors, Cracked Pot, Ice Stone, Linking Cord, three lures, Mirror Herb and both apples. Classic behavior remains available.
5. Matched app/engine build configuration, immutable map-generation outputs, standalone closure repairs, exact-pin private engine checkout and truthful release instructions.
6. Private Windows Expansion source adapter/package and native executable work. Existing Python 3.11+, tkinter and the py launcher remain prerequisites. Keep invitations outside extracted immutable payloads. Actual Windows join/save acceptance is unproven.
7. Protected activation-backup extraction and isolated restore rehearsal, distinct from personal-save import or production restoration.
8. Parent integration, one final paired Linux build, bounded acceptance of the new connected adventure, safe local delivery and backed-up hosted content rollout. These are still deliverables, not completed worker tasks.

## Branch checkpoints

Full source commit IDs and exact observed worktree states are in `RC12-PROGRESS.json`. Source is preserved on separate branches; publishing a branch does not mean approval or main promotion.

App branches:
- `integrate/rc12-dot-next`: earlier Dot integration plus this explicitly incomplete parent checkpoint.
- `product/rc12-adventure`: fixed adventure and owner helper, component-tested, spec follow-up required.
- `product/rc12-player-ui`: objective/recap and owner UI, component-tested, authority-target spec fix required.
- `product/rc12-build-gates`: build/cohort/private checkout fixes including SSH adaptation, component-tested, final pair and hosted CI unproven.
- `product/rc12-recovery`: recovery implementation and reported isolated proof, independent review requests changes.
- `product/rc12-windows`: original source packaging lane, superseded for Windows build purposes by the next branch.
- `product/rc12-windows-build`: corrected Windows build/package source and matched Windows engine pointer, not the final combined product.

Private engine branches:
- `integrate/rc12-dot-next`: grouped outputs, opt-in ecology and standalone entry guard integration.
- `fix/rc12-build-closure`: standalone closure and snapshot expectation repairs.
- `product/rc12-collection`: paid normal collection supplies.
- `product/rc12-native-objectives`: journal doorway and explicit survey/guide controls.
- `product/rc12-native-residents`: generated-place offers and authored battle identity consumer.
- `product/rc12-windows-native`: native Windows compile, parser and extended-VRAM layout fixes.

## New Dot RC12 work, not yet integrated

All Dot branches in both repositories were refreshed during this checkpoint. Exact observed RC12 heads are recorded in the JSON inventory. Branches are stacked and may overlap; these are source candidates, not an additive feature count or an automatic release promise.

App branches `dot/rc12-private-commands`, `dot/rc12-field-stories`, `dot/rc12-field-relays`, `dot/rc12-field-flags`, `dot/rc12-activity-board`, `dot/rc12-candidate`, and `dot/rc12-core-story` contain private-command negotiation, cooperative field mysteries/story installation, relays, opt-in flag duels, unified activity/guild entry, mounted racing and canonical story checkpoints backed by explicitly shared history.

Native branches `dot/rc12-private-commands`, `dot/rc12-mounts`, and `dot/rc12-core-story` require exact dependency inspection and consumer pairing. Native mount/story modules and new app activity/story modules are absent from the current integration base. Do not equate branch fetch, commit ancestry, or the similar RC12 label with content integration. Older campaign/rental and regional/wildlife branches remain separate backlog requiring bounded review, not silently enabled release features.

## Parent WIP captured here

The checkpoint preserves existing parent changes to character action/chapter/record portrait validation, CHARIDENT1 negotiation and V2 wire production; owner HTTPS adventure read/preview/apply and launcher adapters; authenticated CONTROL own-activity reads; and their three new test modules.

This is intentionally incomplete source. `world.product_adventure` and `world.player_activity` live on worker branches, not this integration checkout. Earlier component tests temporarily extended `world.__path__` with real peer implementations. That is not clean-checkout integration acceptance and must not become production dependency wiring. The parent tests also follow the existing test/world import setup.

The app's committed engine gitlink and build pin still select the earlier released engine while its local nested checkout has progressed. This checkpoint deliberately does not stage that gitlink alone or claim the mismatched checkout is a reproducible release. Pair the gitlink, build pin, catalogue and all applicable manifests only after the selected engine integration is complete.

## Known unresolved findings

- APP-SPEC-01: the launcher selects the first unvisited landmark, whereas the authority chooses a validated nearby/guide target. Return the authoritative next objective and scope through the own-only activity projection; do not invent a second ordering in React.
- Parent Guide: first-use or reached-note directions must compute useful private guidance from an eligible adjacent resident with exact revision/presence guards. Do not require raw NPC IDs.
- Parent native identity: the producer has pending literal-portrait changes, but the combined native battle-message full-name hook and actual final-wire presentation remain to be integrated and accepted. Preserve legacy negotiation and save/name ABI.
- Recovery R1: service topology parsing must reject unsupported sections, commands, overrides/options and missing/conflicting roots/ports rather than report unsupported semantics as verified.
- Recovery R2: timeout/cancellation must terminate and reap the isolated authority descendants, not just its supervisor. Keep persisted mechanic execution and archive-source boundaries explicit.
- Independent quality review follows repaired spec compliance. Worker self-review and passing components are not equivalent.
- Build/private checkout changes need final pairing and actual hosted CI readback. Existing scoped CI access was configured separately; no credentials are part of this checkpoint.
- Windows runtime, DLL loading, private-save round-trip and authenticated host join on a real Windows computer remain unproven. This does not block Linux integration or Linux release delivery.

## Evidence boundaries

Historical component reports/logs were recovered from the local release evidence directories. The Windows branch records a real x64 PE build and complete DLL closure, with Wine version/controls and 60/600-frame headless runs. The existing Windows suite reported 69 tests with one skip and no failures. Other workers retain component tests and review reports. None establishes a final combined Linux build or connected RC12 journey.

For this checkpoint, existing modified/new parent Python files were parsed with Python AST and `git diff --check` passed. No new implementation was made; no full build, sandbox acceptance, native playtest, restore or production rollout was rerun. Runtime failures and outstanding review requests are not being relabeled as passes.

Do not commit or upload game binaries, ROMs, saves, private backups, account profiles, invitation credentials or private CI keys. The local Windows archive remains local. Preserve personal saves and active human games. Use the one existing daily integration owner; do not create a competing cron.

## Completion order

1. Reconcile the newer Dot stack against released behavior and the finishing payload; record the chosen bounded scope and dependency order.
2. Integrate existing reviewed app/engine components, finish parent glue and repair explicit spec findings without replacing unrelated released fixes.
3. Perform independent review, freeze the actual matched gitlink/build pin/flags/catalogue, then build Linux and run one connected new-feature acceptance with disposable player data.
4. Promote/deliver the accepted Linux candidate safely and verify client, launcher and hosted content readback. Keep the previous release until replacement passes.
5. Rebuild Windows from that same accepted pair and complete intended-device friend acceptance separately. Publish source progress now without misrepresenting any of those future steps as done.
