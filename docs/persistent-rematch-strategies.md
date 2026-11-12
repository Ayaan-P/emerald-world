# Persistent tactics for original Hoenn rematches

This optional experiment changes real future battles with existing trainers, not scenery or a new quest. World agents can author a persistent move-selection preference for Calvin, Miguel, Winston, Cindy, Karen or Jerry at their original route locations. Consenting players can take that alternate challenge; its real native result becomes unnamed public world history that an agent may inspect before revising the next strategy. No model runs, automatic adaptation or off-screen training are invented.

## Actual player path

Build with --development --experimental-rematch-strategies. In World chat, use /world-rematches on to make optional tactics available for this connection. Ordinary native registration, first-defeat, badge and rematch eligibility still apply. This does not make first encounters or early rematches available sooner.

Talk to an eligible original trainer and accept their usual rematch. If a current world strategy exists, a native message describes its type and status-slot preferences, solo format, normal whiteout and unnamed outcome sharing. Finish paging the message, then A accepts that extra challenge; B selects the original battle path, including existing co-op choice. No partner vote or turn-review is added. No proposal, missing service or three-second query timeout uses the original battle already requested. The choice expires after five minutes. The original game remains fully playable with the experiment or local option off.

Native construction retains the actual current trainer template, species, level, held items, IVs, abilities, money, EXP and original postbattle callback. Only enemy moves are selected from each current species' real level-up learnset at its generated level. It prefers up to three authored types, requests zero to two status slots, then attacks and fills any remaining vacancies. Within these bounds, power and move ID give deterministic ordering. This is not an optimal AI solver and a preference can produce an unchanged or weaker team. Original trainer AI still chooses its actions. No future-level, TM/egg, Z/Max, nonexistent or duplicate moves are injected. Invalid/bounded-out learnsets leave the complete original roster intact and emit no strategy completion.

The alternate fight is **solo**, not shared co-op. Losing follows normal native defeat/whiteout. Winning follows the normal native rematch rewards and progression in this player's save. Neither option edits a partner's save or fabricates group participation. There are no bonus prizes, new saved quest flags, or simulated persistent individual Pokémon. Opponents remain stock native templates rebuilt for each battle.

## Lasting world response

Existing agents discover rematch_strategies in the normal capability catalog and may call world.rematch_strategy with trainer, expected_revision, one to three types, status_moves, and optional active. The publisher owns that strategy. Updates require the exact inspected revision; active=false withdraws future offers while preserving history. Configurations persist in the world's SQLite database across visits and server restarts, independently of temporary route-availability events.

A frozen offer identifies its exact strategy revision. Already offered challenges retain those terms even if the author revises or withdraws the proposal during the bounded choice. An actual native end callback can report player win (1), loss (2) or draw (3) against that revision. A subsequent author can inspect these real reported outcomes and choose different tactics, producing a different next encounter. No adaptation is forced and no result implies that a character practiced, gained levels or caught a Pokémon off-screen.

## Privacy and failure

A is separate per-challenge consent to sharing that result. Public memory and aggregates contain trainer, strategy revision and native outcome, without player names, party, moves or partner identities. The server necessarily knows the authenticated connection; this is not anonymity from the host or network logs. The reports are honest native-client reports, not cryptographic server attestation of a battle.

/world-rematches off revokes future offers and any not-yet-sent result, even during an active battle. The battle itself continues normally. Disconnect revokes the local option and discards reporting. Incomplete/abnormal returns do not become victories. No result retry, replay, reward rollback or cross-save mutation. Losing the connection or process may lose the report while native personal outcomes remain real. Delivery is best-effort, not a guarantee of durable public recognition. Reports are connection-ticket bound, expire after two hours and are deduplicated. Server restart invalidates old connection tickets; retained strategies/results remain.

## Verification

Nine synthetic tests cover authenticated production dispatch, persistent revision/ownership and restart, unknown-schema refusal, frozen offers, withdrawal, expiry, wrong connection, duplicate completion, identity-free public records, source/build wiring and the actual native include compiled both enabled and disabled with UBSan. Native cases exercise legal move filtering, unique/under-level selection, source-verified callback placement, ordinary fallback, explicit choice, cancellation, malformed/overflow replies, timeout, disconnect, revocation and abnormal return. battle_setup.c syntax checks pass on/off using recovered native headers and a host ARM-annotation shim; Python AST checks pass.

These are source and synthetic checks, not a linked/rendered game playtest. Maya must verify exact-binary text paging and original script locks, all reviewed native parties/learnsets, actual battle AI, money/EXP/whiteout and rematch continuation, disconnect timing, and unchanged two-player admission. Default EW_REMATCH_STRATEGIES=0; no live provider, actual save, Maya integration branch, deployment or held payload was used. This is a separate stacked draft, not release readiness or a full playthrough.
