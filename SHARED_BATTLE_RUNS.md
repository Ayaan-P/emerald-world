# Shared short battle runs

This is an optional cooperative circuit over existing native character battles, not a replacement Emerald campaign or a synchronized multiplayer battle.

## Player journey

A configured author publishes an ordinary branching battle campaign with actual available NPC opponents and optional shop/tutor preparation. The existing native campaign board (Ctrl+B) now offers **Host shared** alongside solo Start. The host receives an invitation code. Up to three other trainers explicitly join using `/guild campaign join CODE`, binding their currently authenticated save lineage. The speaker selects **Begin shared run** on the board after at least two trainers join. Joining makes that run's reported stage outcomes available to its participants, not public world history or model context.

Each trainer independently approaches the current NPC and chooses Battle with their own normal party. They can use the existing preparation options. Real accepted native result reports advance the stage: cancellation/draw does not count, a repeated result cannot count twice, and the first reported win/loss for each member is retained. After all members report, unanimous wins offer the authored win routes; any loss offers the authored loss routes. These are client-attested reports, not independently verified victories.

The board shows progress and route advice. Participants can advise; only the initiating speaker chooses the next route, without unanimity or an advisory veto. Each player retains their own battle history. NPC movement/unavailability does not fabricate a battle. No rewards, recruits, party edits, badges, story flags, or NPC growth are issued by this system.

## Persistence and boundaries

Membership freezes on Begin, maximum four distinct authenticated trainers. Disconnecting or switching saves does not abandon or advance a run; return with the same save to resume. Each member can cancel the run for everyone through the explicitly labelled board option. This clears only the matching active run bindings, never another run that a member started after completion. Offline participants therefore do not permanently trap the others. No leader migration, spectator mode, matchmaking, automatic warp, native join-code entry UI or real-time shared battle rendering is added. Invitation entry currently uses private guild chat. Do not give the code to unwanted participants.

Shared run state, private member progress and final stage resolution commit in the existing SQLite battle-result transaction. Native board action tokens include shared state, so new reports/advice invalidate stale selections. The board refreshes when opened or navigated, not as a live overlay. A save change during an admitted battle retains existing refusal/lineage semantics.

## Source and QA

Based on #365 app a9811d5f229a0162c7000f06d117bea343903343, with unchanged native #53 879b6344aeeb3c4e65d0feb00f98655299225635. This is the cumulative feature stack, **not** the released RC12 pair. RC12 app f484577b606348d07337387f14f75ab8cf4970b6 and engine f7a813317d1b9fec803b48b682f5d74245c79037, Maya's integration branches and the unresolved outdoor region operation remain untouched. No new native protocol or pin.

Tests dispatch actual authenticated authority challenges/results and the native board request handler, with deterministic fixture opponents. They cover 2/4 players, loss routes, advisory versus speaker choices, cancellation/replay, independent saves, SQLite restart and stale board guards. This is component testing, not rendered multiplayer, full native linking or live author testing. Maya owns integration, QA and release.
