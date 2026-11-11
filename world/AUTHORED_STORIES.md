# Actor-authored public choices with real follow-up actions

The general author can now use `world.publish_story` to publish a small immutable story pack through the existing opportunity engine. This is a general choice/state system, not a supplied plot, mandatory arc, or a model assertion that events occurred. It supports ordinary map names, bounded shared qualities, requirements and alternative world-once player choices. Existing 1,024-character tool-step, 800-character pack, quality, scene and 64-pack limits apply. Large scripts and unlimited continuing stories are not claimed.

Only public place qualities are permitted on this author path. It cannot adopt an existing private/operator pack, expose player qualities, assign another character a decision, depend on private mystery results, or alter normal Emerald story flags. Existing private story packs retain their behavior and are not published to world history.

## Connected player and agent experience

1. An independent character chooses to publish a pack using its configured author and existing runtime.
2. A nearby player on the pack's ordinary map uses `/story` or `/story PACK`. Before the choice commands, the UI says choices and changes are PUBLIC world history visible to agents and players; trainer names are omitted.
3. The displayed `/story pick-public ...` command makes an explicit public choice. The old private `pick` command cannot silently submit a public choice. Stale, remote, repeated or unavailable choices use the existing authority checks.
4. Shared quality changes, the private request-deduplication receipt, the public event and the public result commit in one database transaction. The public record includes author, pack, place, scene, choice and changes, not player identity, save lineage or free-form player speech. An inferred identity is still possible in a small group; this is public fictional play, not anonymous private conversation.
5. `world.await_story_choice(pack, after_cursor)` receives the first actual choice after the saved cursor. Use zero for the first, then the returned cursor. It also sees a choice made before the wait was installed. Cursors are global receipt sequence IDs, not per-map story revisions, so multi-map packs do not collide. Pending waits and committed results survive authority restart.
6. The actor can branch using the returned choice or replan from the new public event, and use any already-supported capability under its unchanged guards. The story's narrative result text is not an execution receipt for an outbreak, journey, battle, construction or reward. Those actions need their own actual executor and result. A player choice does not grant additional permissions or compel the actor to act.

The component example publishes two alternatives, receives a real CHAT selection and changes an actual shared-outbreak table/snapshot only on the corresponding branch. The other branch skips the effect. This is test content, not a preselected campaign. No new native menu, rendering, bag transaction, mandatory player errand or live provider call is added. The entry is the existing chat story interface; canonical project panels are not claimed as a new public-story UI.

## Verification and integration

Focused tests cover actual plan publication, authenticated story UI/disclosure, choice-before-wait, conditional native snapshot effect, decline, restart, duplicate request, rollback, private-pack isolation and ownership. Full component regression is run separately. No live author, rendered player session or full native game QA is claimed.

Based on draft #380 `ac87040b80f1cfbda3c7fc16c213a2e28b899cc3`, retaining native #55 `babbe0e3272120523d509cecf22705f158429586`. This stack is not based on released RC12. Maya owns integration/QA/release; no integration or release branch is changed. All denied uploads and the separate unpublished provider-budget correction remain untouched. The old spectating stream remains app-disabled. Do not run live provider sessions.
