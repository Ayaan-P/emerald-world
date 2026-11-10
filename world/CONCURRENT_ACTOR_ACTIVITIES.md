# Independent activity and conversation

This app-only draft follows frozen app #384 (97426ba75db71b3bd10619019afbe453893d9d83), with identical native #56 pin 739be20ecf1101f84cc2fb272587978350955b6d. It is not based on released RC12, and does not modify either frozen branch, Maya's integration, or any denied upload. No native or provider changes.

## Player experience

A recurring NPC need not abandon a pending activity just to answer a public question. An author can compose a long-running supported activity, an independent world.await_event subscription filtered to player_addressed_character for that NPC, and world.reply_player depending on the subscription's event_seq. The actual existing player speech command/interaction and nearby group delivery are reused. The original pending activity retains its own eventual receipt. This is not automatic dialogue, physical multitasking, a model playtest or a new permission to reveal private information.

Only reviewed non-physical operations advertise during_activity: public event waits, public player replies, canonical correspondence, public-history reads, received-report recall, species reference inspection and own-blueprint inspection. Every other current and future capability remains exclusive by default. Existing dependencies, argument/result validation, actor kinds, public/private boundaries and chat-session/proximity checks remain intact. A moving NPC's public reply may be committed without being delivered live if the original audience is no longer eligible; no new audience is invented.

Plans remain immutable and bounded to six steps. This enables one explicitly composed conversational opportunity alongside work; it does not append spontaneous replies to an already-running plan or provide unlimited conversations. Authors must use actor-scoped event filters and choose subsequent plans from actual results. A pending operation is never represented as complete just because social work succeeded.

## Scheduling and recovery

Authority ticks still admit at most one transition every five seconds. A durable round-robin cursor prevents an actor with a long chain of immediately-ready steps from monopolizing the runtime. Existing pending operations are polled before their actor starts an independent safe step. A safe action failure blocks new plan work, but no longer prevents already-admitted operations from settling. It does not cancel or roll back their physical effects. Cursor, effects and receipts commit together; restart preserves waits and does not replay completed replies. Capability discovery supplies the concurrency metadata and limitations to existing configured author backends without live calls.

## Verification

Component tests execute the real authority, two independent public event subscriptions, actual public player speech and nearby native-chat queue, reply receipt, original wait completion, restart, failed-side-action settlement, dependency/exclusivity checks, and two-actor fairness across restart. These do not establish rendered native behavior or live provider planning. Maya retains paired integration and gameplay QA.
