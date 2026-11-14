# Optional live Trick House questions

This draft reuses the original fifth Trick House room, not a new generated place or a replacement story. With the experimental build option enabled and an authored pack available, the first encountered Mechadoll offers that set. No command, lobby, vote or new reward is required. The player can keep the original questions, answer three-choice authored questions through the native menu, or press B to use the current stock question.

Correct answers use the existing gate success path. Wrong answers use the existing laughing dolls and return-to-room-entrance warp. The original scroll, password door, native movement, reward, bag-full handling and subsequent challenge progression remain unchanged. The ordinary sixth-badge/story requirements still apply. This does not add postgame replay, new geometry, co-op shared answers or autonomous Trick Master travel.

## Authoring

`world.trick_questions` accepts expected_revision, title, exactly five question/choices/answer objects, and active. The public catalog shows the current pack. Question text is bounded to 96 plain characters, three distinct choices to 18 each, title to 24, and words to 18 for native rendering. Answer is the author's 0-based selection, not a verified factual claim. No canned question set is installed. The publishing actor owns subsequent revisions. Existing actor runtime transactions persist publication and its attributed history together.

A writer can relate the questions to Hoenn or actual public world history but must not claim this tool verifies those facts. Public pack contents include answers, so this is a casual authored game, not a secure competition. No special prizes are invented.

## Lifetime, failure and privacy

A current authenticated native LINK on this exact map can download the public pack. GET requests are bounded/rate-limited and have a fresh nonce. One BEGIN, five uniquely indexed rows and END of the same revision are required. Every line fits the existing 512-byte receive limit and 16-token parser. Partial, stale and malformed downloads do not enable a question set.

The player must explicitly accept locally. That immutable set then survives a network disconnect for the current attempt; it cannot change under a displayed question. Every native map transition, including the original failure warp, starts a new attempt and clears it. Withdrawal blocks future downloads, not an already accepted attempt. Without a complete set, or after declining, stock questions work immediately. An unavailable/malformed question, canceled menu or stale local context falls back to the original question; none counts as a correct answer.

Question-menu allocations belong to the existing native menu, which frees them and resumes the native script. Trainer identity, map and challenge level are rechecked. No answers, quiz results, party, bag, save identity or completion reports are sent. Ordinary existing presence is unchanged. Nothing writes a new save payload, invokes Save, copies another player's progression or claims a world contribution. Normal in-memory progress saves normally. A restart uses original save/script behavior; it does not promise to restore the unsaved authored set.

## Build and ancestry

Default `EW_TRICK_QUIZ=0`. Explicit development build: `--development --experimental-trick-quiz`. Disabled builds retain all stock question paths and never request a pack. App parent #493 and native parent #131; separate from Maya #410/#72. No held bridge, Cut, collision PR, recovery or relay operation is included or retried. Maya owns integration/release.

## Verification and limits

Seven focused tests pass: author bounds/ownership/revisions/withdrawal, fresh-map/rate/restart delivery, no answer ingestion, actual authenticated server dispatch, actual native C compiled/executed with UBSan for on/off cohorts, and build/script wiring. Native cases cover wrong nonce, partial availability, consent, cancellation, allocation failure, stale player context, replay, timeout and accepted-pack disconnect retention. The original puzzle script is reconstructed by removing only the new hooks and matches its pinned original Git blob exactly.

The actual new native module also passes syntax checks against recovered engine headers with the flag both off and on. These are component tests with fixture dependencies, not a linked script VM, rendered gameplay or a full native build. Native text pagination, menu/controller behavior, save/reload, original failure warp, full gate-to-reward run and two-client coexistence remain unverified. No actual user saves or live providers were used. Keep draft/default-off until that QA.
