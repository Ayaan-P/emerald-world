# Sustainable object interaction dispatch

Object uses no longer append a wrapper per interaction. The first use installs a
single reusable dispatcher; later uses replace only its literal request and empty-
state bootstrap snapshot. Exact AST checks ensure the helper and wrapper still
match the known implementation. Changed/ambiguous source fails closed instead of
rewriting arbitrary authored code. Existing sandbox/admission is still used for
every request; no validation bypass or direct player-save operation is added.

One current receipt is retained in mechanic state. The authority atomically
archives every new validated transition with module admission, checking its before,
after and state digest against actual objects/state. Public causal history and a
unique durable transition record survive rotation and a crash before player feedback.
Agent plan receipts and existing player feedback events remain separate.

Old append-only wrappers and their old receipt map are preserved, so their requests
cannot replay. They are not unsafely stripped or guessed at. The old 32-use ceiling
does not affect new dispatcher requests. Existing total source-size limits can
still require consolidation of an already oversized legacy mechanic; repeated new
uses do not grow the source. History/archive disk space naturally grows with real
world activity rather than imposing a lifetime use cap.

Regression executes 40 actual authenticated player uses against an installed
program, verifies one dispatcher/bounded source/current receipt, 40 durable causal
records and restart state. A retained old wrapper test proves its effect does not
replay when new dispatch is added. Existing agent/player object tests pass.
No full rendered-native or live-provider claim; Maya retains integration/QA.
