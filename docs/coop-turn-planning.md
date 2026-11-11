# Native co-op turn-review candidate

Separate app configuration atop #482, pinning native 414fa149b58b5caa5aa75271fab040e272d6d217 atop #120. No Maya or uncertain relay/recovery changes.

`--development --experimental-coop-turn-plan` enables a matched-client experimental cohort. Default is off. Both humans review their native selections before the turn executes. Each can revise only their own ordinary move or Hold-back choice; both must acknowledge the revised pair. Bag/switch/forced/gimmick choices remain native and are shown as non-revisable, without revealing a private bench. An absent ally uses the original flow.

This is a source-integration draft, not validated playable software. Native focused synthetic tests and syntax checks passed; no full exact-head native build, rendered review screens or linked two-client gameplay. The four-page review may prove too slow in routine encounters and requires playtesting. No real saves, provider calls, changes to rewards/progression or new default enablement.
