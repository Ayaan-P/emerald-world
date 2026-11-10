# Persistent history-driven world reactions

Separate app-only draft after #388 at a5eb6bac317186affce0292c832ca6fc46ccdf9b. Native remains #56 at 739be20ecf1101f84cc2fb272587978350955b6d. This feature stack is not based on released RC12. Frozen #384/#56, Maya's integration/release, denied uploads and live-provider restrictions remain unchanged.

## What players experience

A configured agent can author a reusable public-world rule through world.publish_reaction. Later a matching actual public record causes an existing authoritative world operation to execute, without another author/model request. The result reaches players through the existing native encounter or weather transport. No scenario or rule is installed automatically.

For example, a test configures a literal rule for a specific public NPC speech, then sends that speech through the actual nearby-player dialogue entry point. The authority commits a real temporary outbreak configuration and produces its native WILD_OUTBREAK packet. This proves the app path and native packet generation, not that a rendered player encountered or caught anything. The text is a trigger selected in the rule, not an instruction parser.

The system complements one-shot world.await_event. A reaction persists beyond the current plan and continues processing future matching events with recurring limits. An NPC may revise its intentions by pausing a rule and registering a new immutable ID. Original public event provenance is retained: a reported battle is still client-attested, and a statement is not assumed true.

## Authoring and execution

Discover history_world_rules in normal actor context. The two capabilities are world.publish_reaction(id,rule) and world.pause_reaction(id). Rule JSON contains event, where, tool, args, cooldown and per_hour.

Supported triggers are public canonical trainer reports, shared landmark discoveries, public story choices, character journey arrivals, directed public NPC speech and spatial public speech. Private event kinds are never scanned. The trigger list excludes rule receipts and the permitted operations' output events, preventing self-amplifying rule chains.

Operations are the existing world.configure_outbreak, world.configure_fishing and world.set_weather. This is intentionally an initial reviewed synchronous effect set, not arbitrary code, all agent tools or new permission. Fixed literal operation arguments are validated again by the original executor at execution time, including actor availability/kind, current location where required, destination/species and ownership guards. Event text is never substituted into arguments or executed. Registration does not assert that a later effect will be valid.

Rules start after the current committed history head. Each rule scans at most 64 public events per authority tick and retains its cursor. At most one matching effect runs per five-second service tick, with durable round-robin fairness. Cooldown is 60–86400 seconds and the recurring limit is 1–12 attempted effects per rolling one-hour window. Both successes and guard failures count. At most two active rules per actor and 32 total are admitted. No model calls or API charges are incurred by the rule service.

Budget-exhausted rules wait; committed events are not dropped and can be handled later. There is no freshness claim for delayed triggers. Rule arguments and current guards, not historical state, determine the effect. Budgets replenish and survive restart; there is no lifetime interaction ceiling. Clock rollback waits conservatively rather than replenishing early.

## Control, history and recovery

The owning actor may pause a rule, preserving all history and already applied state. Retirement or loss of the actor automatically disables its rules. Paused IDs remain immutable and are not silently re-enabled by registration. The existing private owner admin socket accepts {command: world_reactions, action: status} or action: pause_all. Players and model tools do not gain access to that owner command. Stopping the authority stops the service.

Each matched event has one durable rule result linking its original event sequence, actor, rule, operation and exact success or failure. Effect, receipt, consumed budget and cursor commit together. An executor guard failure rolls back any partial effect, records blocked, consumes an attempt and advances past that trigger. A failure to persist the final receipt rolls back the effect and cursor together; the uncommitted event remains eligible. No silent retry of a committed blocked event and no success claimed from a mere registration.

All rule definitions/results are public fictional world-authoring data. They contain no private party histories, trainer IDs or save identities added by this feature. Existing native gameplay, individual saves, encounters, Repel, catches, personal outbreak precedence and fishing special-case rules are unchanged. No simulated migration, victory, capture, NPC growth, physical labor or rendered weather is inferred.

## Checks still required

Component tests cover real capability registration, player speech, native snapshot output, filtering/private-kind exclusion, unrelated public backlog, ownership conflict, recurring budget/restart, retirement/pause, fairness and transactional failure recovery. Model decisions in tests are scripted inputs. No live model session, full linked native build or rendered multiplayer playtest is claimed. Maya owns integration and final QA.
