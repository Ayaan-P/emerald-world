# Native elevator warp safety

Child of app #444 (cdcc200bb37ec09c0f78c4c8306ca15798b45df8), paired with
native #93 (34a83a9419f18d485ff1b57669ff159f2b927e0c). Separate from Maya
#410/#72 and RC12; no new build flags or save migration.

Exact current Silph Co map metadata exposed an invalid native lookup:
source warp 9 enters elevator warp 0, but the return setup read destination
slot 9 from a one-entry array. The correction consistently uses the destination
index and checks its bounds. Existing source return location, native warps,
escape handling and personal save format remain unchanged. Hoenn elevator
paths using different source/destination indices benefit from the same fix.
Because the incorrectly read argument is unused by SetDynamicWarp, this is
not evidence that players actually returned to the wrong floor.

Also fixes #92's omitted party-menu Oak guidance selector using the existing
regional tutorial policy, without adding party/storage operations.

Two native tests pass, including actual SetupWarp under AddressSanitizer/UBSan
with source/destination mismatch and boundary fixtures. 29 focused app tests
pass. No full native build, controller elevator round-trip, party guidance,
save/restart or two-client QA. No full campaign claim; actual saves, held
operations, Maya branches and live providers were untouched.
