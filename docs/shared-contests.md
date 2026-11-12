# Experimental shared original Emerald Contest

Default off: EW_SHARED_CONTEST=0. Development option `--experimental-shared-contest` requires `--development`. Native source parent #122 and app parent #484. Maya's integration/release branches are not changed.

## What players do

Two tagged friends go to the original Lilycove Contest Lobby. Each uses the existing link-contest receptionist, chooses Emerald cable mode, accepts the stock save prompt and selects their own Pokémon and category. Reaching that counter is individual consent to this activity; joining a tag alone does not enter a contest. Both must choose the same category, confirm the frozen private choice through their native client, and remain at the same lobby in the same world/region scope. Otherwise admission cancels. The original waiting/B-cancel text remains.

The experiment then starts the real stock two-player linkup and `contestlinktransfer`, original Hall movement/warp, five appeal rounds and native scoring. The existing native engine fills the other two slots with its ordinary NPC entrants and synchronizes them. It is a shared competitive side activity, not cooperative victory and not four-human play. It does not invent new trainers or fixed quests. The existing link contest result/artist path remains distinct from ordinary NPC rank ribbons and prizes.

## Outcomes and failure

Before stock `Task_ShowContestResults` makes any result/stat/fan/painting/save changes, both authenticated clients must report the same native standings and the exact public contestant identities (species/personality/OT ID, not a cryptographic attestation). The server does not score the contest or certify native execution. Each player then runs the original local save tail exactly once. A reported local save failure stops the tail; it is not retried by re-incrementing records. One successful local save is never rolled back because the partner's save failed.

Before native linkup starts, cancel/timeout resumes the original counter failure branch. **After native linkup starts, a disconnect or failed result/save agreement uses Emerald's native communication-error/reset recovery. It is not a seamless lobby return.** The original counter's pre-contest save is the recovery point. A successful result already saved remains a successful local save; closure alone cannot authorize one. No actual save was used in development.

No party data is copied into the other player's save. The local selected Pokémon remains native-owned. Enrollment binds connection, tag, visit, choice revision and identity; the dedicated mode cannot be entered through generic battle/trade offers. Original modes1..4 keep their admission and transport rules. The feature's source remains inert when disabled.

## Verification and outstanding QA

14 focused tests pass: admission, result/save acknowledgment, actual native C lifecycle/controller under UBSan, ordering of the pre-mutation stock hook, authenticated server admission and genuine native session OPENs, scope rejection and generic-offer rejection. 31 existing session/protocol regression tests pass. The controller, lifecycle and native transport source pass syntax checks with recovered headers enabled/disabled. Python modules/build configuration compile.

These are component/source-integration checks, **not a linked or rendered contest playtest**. Full exact-head native build/link, original reception flow through all appeals and artist return, actual save-sector failure/restart tests, two-client latency/disconnect, animation/menu rendering and regression play remain outstanding. No claim of release readiness or safe seamless recovery. Keep disabled until Maya's integration and linked QA.

The controller relinquishes activity ownership only after the saved stock contest has returned to ordinary free field control in the lobby, with the native cable closed. Losing the connection while still inside results is an error/reset path even if that player's result has already saved; it does not leave a dead waiting task or falsely announce a clean return. Measured recovered native structure sizes (ContestPokemon60 bytes, two NPCs120, four statuses112, appeal results18, excitement3) fit the existing bounded256-byte link-block path; no block limit or command-family relaxation was added.
