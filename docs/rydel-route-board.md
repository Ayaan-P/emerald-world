# Rydel's optional route board

This is a connection between existing original-character conversations, simultaneous field races and consented public history, not a new race engine or a replacement Cycling Road.

## Player path

With living Rydel enabled/authored and the experimental native flag on, speak to the original Rydel in Mauville's Bike Shop. His supplemental greeting offers **L: route board**. SELECT cycles the existing panel pages; A chooses and B returns to ordinary bike service. No native story script, bike ownership, party, money or save flag is modified.

Browse existing authored courses by title and rules, review their start map/tile, then explicitly open a guild race lobby. Alternatively review and join your guild's open lobby. These are the actual existing race operations, not simulated starts. Nobody is teleported or readied. Exit the shop, follow the directions sent to private chat, and use the existing `/guild race status` and `/guild race ready` at the start pad. Existing guild membership, 2–4-player capacity, mount eligibility, countdown, checkpoints, cancellation and disconnect rules still apply. The board does not solve all on-route UI: readiness, progress and leaving remain private chat commands. Course walkability/fairness still requires author playtesting. There are no new prizes or forced costs.

After a real finish is committed to the existing private race-results table, return to Rydel and choose **Share my last finish**. A separate confirmation displays the exact course/time and explains permanent publication to all players and authors. Cancel publishes nothing. Only the requesting authenticated trainer's record is read. No partner result, name, rank, run identifier, save identity, bike ownership, original Cycling Road record or party is published. A previously finished race can be shared even if its other participants later disconnected. An unfinished attempt cannot.

The public receipt can inform Rydel's existing independent author process. He can choose a different route, another supported action, dialogue or no action. Tests demonstrate an author choosing the existing `world.publish_race` capability after a real finish; no fixed follow-up course, automatic reward or model call is installed. Public times are recreational client movement reports, not anti-cheat proof. Historical account-scoped records are not evidence that the current save completed a story beat or met Rydel.

## Safety and compatibility

The board uses the existing authenticated CORE transport and bounded native panel. Every choice is bound to the current connection/save context, fresh exact shop location, a 60-second lease and rotated token/version. Stale choices, native activity conflicts and vanished/full guild lobbies fail without inferred success. A lost response cannot replay the same action token. Opening again shows current state; existing chat commands can inspect/leave a lobby.

Publication and its private dedup key commit in one SQLite transaction; reconnect/restart cannot republish the same finish. No native save is written. Stopping sharing cannot retract an already public event; consent explicitly says permanent. Merely browsing, racing, talking to Rydel or returning to the shop does not publish a result. Original race results stay private by default.

Native default is `EW_RYDEL_ROUTES=0`. Enable only using `scripts/build_expansion.py --development --experimental-rydel-routes` with the matching pair. Existing living-cast host enrollment/authored Rydel response and race courses are prerequisites; this does not start a provider, invent a Rydel plan, or install preset courses. No authored greeting means the original bike service simply continues.

## Ancestry and verification

Separate stack on app #487 (`a9af70cf2b3d1c4acd348bf9a4922f294b49b4b1`) / native #125 (`286f62c04d1fe736a2d7d1f76b198c40c7525053`). Maya's #410/#72 and held/uncertain writes are untouched.

Seven focused tests pass: actual two-client race start/join/ready/checkpoint/finish logic, separately confirmed own-result publication, independent deterministic route authoring, no partner leakage, stale/expired/wrong-location/activity rejection, stale lobby cancellation, transaction rollback, restart dedup, maximum-size panel text and native wiring/default source assertions. Python compilation passes. Native syntax passes in both flag modes only with an explicit test shim supplying three declarations missing from the recovered header set (`gSpecialVar_ItemId`, `BattleSetup_WallyRematchReady`, `WorldCoreStory_CampaignClose`). Without the shim those inherited declaration gaps block this recovered-header check.

No full exact-head native build/link, rendered input/page pacing, four-player race, actual save/reload or live-provider QA is claimed. In particular, source assertions and simulated participants are not a native playtest. Maya owns integration/release.

Paired native draft #126: https://github.com/Ayaan-P/pokeemerald-expansion-native/pull/126 at `bcb77ed4c13a6b937de4a4169b15bea8c81c3c05`. Test command: `python3 -m unittest discover -s test -p test_rydel_routes.py -v`.
