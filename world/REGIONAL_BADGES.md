# Experimental personal Hoenn/Kanto badge separation

Independent child of app #437 (`d85bc2c88c08433cf4bd9b3c73827ccbb60c6fed`),
paired with native #86 (`a072d4497dc44775cb6e561f75ec52518735ac4f`). This stack
is not RC12/Maya's #410/#72 integration. Existing combined-world registry stays
unchanged: this is personal native progression, not shared badge ownership.

Build explicitly:

```
python scripts/build_expansion.py --development --regional-state --kanto-content \
  --experimental-combined-presence --experimental-regional-badges
```

The new flag is off by default. At Slateport/Pallet, WORLD -> Regions and personal
badges -> Personal regional badges shows the original shared bits, supported
Hoenn/Kanto sets and unassigned bits. Cancel is selected by default. Choosing
`Back up save + separate` exclusively copies the last disk save to
`<save>.pre-regional-badges` before changing RAM. An existing backup is never
replaced. Missing save or copy failure aborts. Save normally afterward.

Migration only assigns an originally set badge when the corresponding personal
gym completion or leader-defeat evidence exists. Both regions can have evidence;
otherwise the original bit is archived and inactive, explicitly disclosed.
No server, agent or other player's progress supplies evidence or confirmation.
New stock badge writes affect the native region bank; stock reads, including
field-move checks, use that bank. The original shared bits remain retained.

The extended region snapshot is counter-bound with scene flags/vars. Migrated
files use PENSAV3 and older/feature-disabled readers refuse them. A new reader
can recover the previous complete legacy snapshot. To undo, exit the client and
restore the whole pre-migration backup (the last on-disk save), not individual
badge bits. This intentionally rolls back later play too. Never overwrite a
running client's save. An abandoned migration's existing backup requires manual
review before retry; it is not silently replaced.

Native local verification: four compiled component tests pass, including actual
save-module synthetic-file tests, failed replacement, exclusive backup,
counter fallback, fresh-process load, profile reset, invalid data and exact-old-
reader refusal. The dispatch test uses extracted actual native flag functions
with map/trainer boundary stubs. All sixteen gym evidence mappings source-audited.
App focused suite: 29 tests pass.

Not a linked native build, rendered menu/route playtest, all-consumer campaign
playthrough, hardware power-loss test or two-client QA. Native #86 includes the
full limitation/recovery contract. Use synthetic/disposable QA profiles only
until integration verifies UI, full sector-save interruption, field/battle
consumers and both regions. This separates badges, not every shared stat/Dex
system, and does not claim a completed Kanto campaign. No actual user saves,
held actions, donor imports or live providers were used.
