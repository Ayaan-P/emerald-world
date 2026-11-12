# Generated Trainer Hill mazes (experimental)

This is new playable geometry for the existing four-floor Trainer Hill, not shared co-op progression or another region. Agents publish immutable seed offers through `world.maze_courses`; players inspect `/guild mazes page 0` and `/guild mazes show ID`, then explicitly arm `/maze load ID REV yes`. Start a NEW challenge with the ordinary receptionist and choose the stock trainer mode. `/maze status` and `/maze off` inspect or cancel pending admission.

Build with `--development --experimental-maze-courses`. Default builds refuse new admissions. The feature uses stock trainers, parties, battles, scripts and graphics. It generates four connected 16-by-16 mazes for any seed 0–4095; trainers occupy side alcoves. It suppresses vanilla final prizes and best-time writes for custom runs. It does not promise particular encounters, rewards, shared progress or synchronized player positions.

## Persistence and recovery

Hoenn variable 0x40FB stores a version-1 marker and seed. Geometry regenerates from that marker, including when new admissions are disabled. A new ordinary challenge clears it. Canceling an armed offer does not change an active course. Pending offers expire and are trainer-ID-bound; disconnect clears pending admission. No player party replacement, e-Reader storage, custom save-sector writes or automatic disk save is introduced.

Do not downgrade a save inside a custom course to an engine lacking this resolver: stock geometry may differ around the saved position. Retain version-1 generation unchanged for existing markers. Actual disk-save, timed-run resume, loss, rendering and return behavior still require linked native QA. These component tests do not establish crash-safe timed-run recovery.

## Verification and ancestry

Component tests exhaust all 4096 seeds on four floors, including connectivity with both trainer tiles occupied, and compare compiled C generation against Python preview. Compiled adapter/protocol fixtures cover admission, owner binding, timeout, cancellation, saved-marker regeneration and adjacent-variable preservation. Source assertions check the real map-loader and reward/record hooks. Full native linking, rendered tiles/camera, actual save/restart and multiplayer coexistence have not been tested.

Independent draft stacked on app #406 and native #68, not RC12. Frozen #384/#56 and Maya's integration are unchanged. Native `maze_variable_audit.json` records the source reservation audit and its limits.
