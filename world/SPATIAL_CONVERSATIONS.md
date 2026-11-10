# Public conversations among nearby recurring characters

App-only follow-up on #386 at a7b982694698bb393c65ba78f2932eca4f8d989a. Native #56 remains 739be20ecf1101f84cc2fb272587978350955b6d. Frozen #384/#56, RC12, Maya's integration and denied uploads are untouched. This stack is not based on RC12. No live provider calls.

## The player experience

A world-owned recurring NPC may choose `world.speak(text,radius)` from the normal capability catalog. The authority determines actual available NPC recipients and nearby ready player sessions. Public text is offered through the existing in-game World chat, so players can hear an NPC ask a question, independently see another NPC respond, and join with `/guild npc speak-public MESSAGE`. The existing `/guild npc` help explains that this enters public world history for all players and agents. No new native file or slash-command-only viewing panel is required to overhear speech; input uses the existing chat interface.

Each recipient decides independently through the existing configured reaction/author lifecycle. No automatic reply, agreed plan, relationship, completed action or truth of a statement is inferred. The ordinary public history/result loop allows subsequent validated capabilities. This feature does not automatically convert existing directed `world.address` messages, letters or private conversation into group speech. Agents choose the new public operation explicitly.

## Scope and boundaries

Only already-rendered world-owned characters participate, not unresolved canonical actor positions. Speakers and NPC recipients must be active, stationary and outside pending player battles. Generated places use the exact immutable revision and cardinal connected-ground distance of at most four cells; walls prevent delivery across disconnected ground. Native maps use explicitly documented same-map proximity of at most two cells, not a claim of wall-aware acoustics or full map geometry. Both paths are authority-position rules, not proof that an actual sound or animation occurred.

NPC speech has a durable 30-second per-character cooldown; player group speech retains a five-second session cooldown. Runtime and provider budgets remain unchanged. There is no background model or API call in the speech operation itself, and no forced player pause.

Human audience membership is frozen at publication in private authority storage, without putting trainer IDs, sessions or save identities into public history. Live chat is attempted at most once, only within 15 seconds and only while the same authenticated session is still ready and in range in the exact place. New sessions, late arrivals, distant players and expired messages receive no replay. Mark-before-send favors avoiding duplicate output over guaranteed delivery. Public history remains public even if nobody saw the chat. Public fictional speech is not suitable for secrets.

## Verification limits

Tests exercise real runtime receipt creation, actual public speech and native-chat queue, independent recipient author queue, player group participation, three NPC recipients, normal-map proximity, generated revision/geometry, actual pending movement, cooldowns, restart, stale session, expiry, no replay and private audience omission from public records. Decisions in tests are scripted test inputs, not live model behavior. No rendered client, audio, native animation or two-client gameplay playtest is claimed. Maya owns integration and final QA.
