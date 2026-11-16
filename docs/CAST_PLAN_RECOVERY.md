# Characters can reconsider blocked plans

Separate follow-on to app candidate #286 at f81be46, with its unchanged native #26 pin f5b45730. Does not depend on the cooperative investigation branch or add a player task.

## Actual behavior

An enrolled character can retain an assigned public project action. Another character's real action may change that project's revision or available choices before it executes. Previously, the authority returned a transient waiting result every five seconds without giving the agent evidence to reconsider. The character could remain stuck indefinitely.

The dispatcher now records one durable failed-admission observation per exact actor, intention and action. The existing character reaction queue can deliver it to that actor. Its normal author context contains current available actor actions, allowing an independently authored revision to choose a current action, change its goal or withdraw. The authority still checks assignment, public qualities, prerequisites and revision before executing. No automatic substitution or retry with a guessed revision occurs.

Only actual commits change project state and available player choices. A blocked plan is not completion, a failed battle, proof of another actor's intentions or blame. It does not change a player save or grant anything. The ordinary world journal distinguishes this observation from completed actions.

## Persistence and scope

The failure record survives restart and deduplicates unrelated character revisions. The same request is still checked later: if its real prerequisites become available, it can execute without waiting for another authored turn. The observation itself never creates an intention completion receipt. Existing successful-action receipts remain unchanged. Private player state is never consulted.

This is bounded public shared-story activity, not physical NPC travel or a battle simulator. Existing lifetime intention limits still apply. Real model behavior depends on configured author availability; no response or success is fabricated when it is absent.

## Verification

Tests run two existing cast actors through actual authority actions, interrupted planning, the real reaction queue and response validator, revised action admission, changed player-visible project choices and restart. The authored response in tests is a fixture, not a live model. No new native protocol, rendered playtest, linked build or release is claimed. Maya owns integration and game QA.
