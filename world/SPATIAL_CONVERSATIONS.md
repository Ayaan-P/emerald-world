# Public conversations among nearby recurring characters

App-only follow-up on #386 at a7b982694698bb393c65ba78f2932eca4f8d989a. Native #56 remains 739be20ecf1101f84cc2fb272587978350955b6d. Frozen #384/#56, RC12, Maya's integration and denied uploads are untouched. This stack is not based on RC12. No live provider calls.

## The player experience

A world-owned recurring NPC may choose `world.speak(text,radius)` from the normal capability catalog. The authority determines actual available NPC recipients and nearby ready player sessions. Public text is offered through the existing in-game World chat, so players can hear an NPC ask a question, independently see another NPC respond, and join with `/guild npc speak-public MESSAGE`. The existing `/guild npc` help explains that this enters public world history for all players and agents. No new native file or slash-command-only viewing panel is required to overhear speech; input uses the existing chat interface.

Each recipient decides independently through the existing configured reaction/author lifecycle. No automatic reply, agreed plan, relationship, completed action or truth of a statement is inferred. The ordinary public history/result loop allows subsequent validated capabilities. Public speech is indexed by actual place, spoken words and each NPC recipient so long-term actor history retrieval can find it. No private audience identity is added to the index. This feature does not automatically convert existing directed `world.address` messages, letters or private conversation into group speech. Agents choose the new public operation explicitly.

## Scope and boundaries

Only already-rendered world-owned characters participate, not unresolved canonical actor positions. Speakers and NPC recipients must be active, stationary and outside pending player battles. Generated places use the exact immutable revision and cardinal connected-ground distance of at most four cells; walls prevent delivery across disconnected ground. Native maps use explicitly documented same-map proximity of at most two cells, not a claim of wall-aware acoustics or full map geometry. Both paths are authority-position rules, not proof that an actual sound or animation occurred.

NPC speech has a durable 30-second per-character cooldown; player group speech retains a five-second session cooldown. Runtime and provider budgets remain unchanged. There is no background model or API call in the speech operation itself, and no forced player pause.

Human audience membership is frozen at publication in private authority storage, without putting trainer IDs, sessions or save identities into public history. Live chat is attempted at most once, only within 15 seconds and only while the same authenticated session is still ready and in range in the exact place. New sessions, late arrivals, distant players and expired messages receive no replay. Mark-before-send favors avoiding duplicate output over guaranteed delivery. Public history remains public even if nobody saw the chat. Public fictional speech is not suitable for secrets.

## Verification limits

Tests exercise real runtime receipt creation, actual public speech and native-chat queue, independent recipient author queue, player group participation, three NPC recipients, normal-map proximity, generated revision/geometry, actual pending movement, cooldowns, restart, stale session, expiry, no replay and private audience omission from public records. Decisions in tests are scripted test inputs, not live model behavior. No rendered client, audio, native animation or two-client gameplay playtest is claimed. Maya owns integration and final QA.

## Showing a changed place

`/guild npc show-place NPC` lists up to four locally demonstrable mechanisms. `/guild npc show-place NPC NETWORK` reviews an optional public demonstration of an existing shared mechanism. The player must be beside the active character on connected ground, and every mechanism member must be within the character's connected four-tile observation. Confirmation names the character, mechanism and phase. A one-use session token expires after 60 seconds and revalidates the character version, current objects, definition and original transition before publication.

This connects actual play to the existing independent character response path. Players can use authored moves or choices to change a shared mechanism, bring a character near it later, and explicitly show the result. The public speech carries the current visible objects and the exact committed transition receipt. The normal enrolled character queue can then choose dialogue or other ordinary validated actions. No reply, gratitude, relationship improvement, attribution to this visitor, or eyewitness memory is manufactured. The character may decline to respond. No new provider is started.

The mechanism must have changed phase through an admitted object action. Its archived state digest must still match the current control state. Initial declarations, failed actions, subsequent unmatched changes and spatial-only transitions do not qualify. This intentionally does not guess which intervening action caused a current state. Ordinary conversations remain available when a demonstration cannot be verified.

The demonstration is public world history. It contains no trainer ID, private party, cooperator ledger or save state. Unlike ordinary explicitly remembered speech, this operation never adds a personal-memory link, even if the player previously enabled remembering. Existing public dialogue delivery is reused, including same-session nearby audience checks and at-most-once replies. Reconnecting does not replay a pending live reply; the durable public record remains. The operation changes no world object, campaign, save or native item by itself: it demonstrates changes that already happened through normal gameplay.

Validation uses actual authority co-op move admissions, shared object changes, public conversation publication, an independently enrolled recipient queue and a fixture-authored reply executed through the ordinary capability runtime. This is an app-only connection, not a rendered playtest or evidence of live model behavior. Native #100 is unchanged. No held native actions are retried.


## Receipt-first resident decisions

`world.inspect_place_change(network, definition)` gives a world-owned resident a fresh local view reconciled against an already admitted transition. Obtain the exact definition from `world.discover.campaign_mechanisms`. All mechanism members must be on connected ground within the resident's four-tile observation. Definition changes and out-of-range inspections fail. An initial declaration, missing archive or mismatched current control digest returns `committed=false`, without replaying or inventing the missing action. A verified result includes `committed=true`, current `phase`, public object appearances and the original `transition_receipt`. It never identifies a contributing player, exposes the cooperative ledger, or says the resident witnessed the action.

This is an alternative to future-only event subscriptions when the relevant change may predate the resident's plan. It does not automatically subscribe, respond or run a provider. A resident chooses whether to inspect and what to do with the result through the existing author/runtime lifecycle. An authored dependent step can use the existing `when` condition on `/phase` or `/committed` and call an ordinary capability such as `world.offer_tutoring`. A later response reflects the recorded observation; it is not a continuously enforced condition or a guarantee the place has remained unchanged. Reinspect before making a decision that requires current state.

### Reference composition

The executable reference in `test_place_conversations.py` deliberately uses existing mechanisms rather than introducing a quest format:

1. Players encounter and use an authored shared object without joining a campaign or registering witnesses. Existing learned-move validation and actual mechanic admission change its visible phase. Prop appearance/movement is not represented as walkable traversal.
2. Only afterward, a resident receives a plan to inspect the place. The receipt-first capability discovers the prior action instead of waiting forever for a repeat.
3. An independently authored conditional decision offers Substitute tutoring through the existing native service. The test restarts the authority between inspection and offering to verify durable execution without replay. This is a useful shared opportunity: each player must still choose an eligible Pokemon and replacement in the native UI. Nobody receives an automatic move, personal reward claim or relationship increase.
4. A separate optional battle campaign can coexist with the same resident and place. It discloses ordinary whiteout/money-loss stakes and has an explicit decline route. Declining does not revoke the tutoring opportunity or fabricate battle participation.
5. A returning player can find the unchanged persistent place and tutor offer. The resident remains free to close/change its service later through its existing capability. The reference does not prescribe a character arc or require authors to use this response.

The test's resident decisions are explicit fixture-authored plans, not evidence of live model autonomy. This app-only change builds on #464 and leaves native #101 unchanged. Authority tests verify prior receipts, no initial-state credit, exact definitions, current digest mismatch, range, restart, ordinary service advertisement, no party mutation and independent campaign decline. Native party selection, animations, eligibility, whiteout/return, and the complete rendered loop still require a linked native gameplay session. The checkout's Expansion submodule is uninitialized, so no rendered playable-loop claim is made.
