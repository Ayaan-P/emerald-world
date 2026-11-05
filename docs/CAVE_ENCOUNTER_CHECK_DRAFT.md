# Native generated-cave encounter check

On top of the verified offline entry/walk/return check, this draft adds a second disposable native test-mode run. It enters a validated organic cave, walks between two known floor cells until a wild battle starts, waits until the opponent is visibly revealed in the existing public battle-state telemetry, and checks the species/level against the generated cave's Granite Cave 1F encounter table. It then ends test mode and verifies the disposable save bytes were not written. It never uses a world connection, account or model.

The fake-driver tests check harness control flow only; they do not establish that a native encounter occurred. The first real native run is pending on the exact CI head. A pass would cover one deterministic encounter, not battle completion, catches, blackouts, save/reload, encounters across all layouts, multiplayer, a human visual playthrough or balance. The feature and parent cave stack remain experimental.
