# Private opening teams and bilateral preparation

Experimental, default off. Stacked on app #476 / native #114, not Maya's branches. Use `--experimental-coop-preparation --development` only with matching disposable clients pending linked QA. The option changes the native co-op version independently of partner medicine and existing story experiments.

## Player experience

After native link-player admission but **before party staging or the existing timed Pokémon exchange**, both players see a private native window showing their six party nicknames. Select the opening team in order: the first selected Pokémon leads, up to three healthy non-eggs (all available if fewer than three). Selecting an already chosen Pokémon removes it. The numbered choices reveal the opening order; unavailable entries are marked. Ready does not silently rearrange the saved party. Existing full-six private switching remains available after battle begins.

Each player explicitly selects Ready. While waiting, B cancels. Both READY acknowledgements advance to a non-cancellable commitment round, displayed as “Both ready - starting battle”; only a completed bilateral LOCKED round starts the existing exchange. Before that boundary, cancellation is sent and acknowledged rather than immediately jumping into a solo battle. A three-minute preparation limit or broken connection aborts rather than holding the other player forever.

No partner bench or selected-team details are transmitted during preparation. Only generation/round, readiness, role and encounter ownership are exchanged. The ordinary validated battle exchange follows, including its existing staged-team disclosure. Full private-party order, items and saves remain unchanged by preparation.

## Recovery and ownership

The owner retains its captured original trainer/wild encounter until the actual confirmed staging boundary. Pre-staging cancellation or failure resumes that owner's original native encounter callback. A guest without its own captured encounter returns to its own field; no callback, battle win or progression is invented for it. Crossing independent trainer encounters retain the existing authority HOLD exclusion, rather than merging two scripts. This is not new shared reward credit.

Selected Pokémon are snapshotted locally on Ready and revalidated byte-for-byte before staging. An invalid team is not silently substituted. The old timed exchange is unchanged in its sequencing, and receives no blocking selection menu. If exchange fails, it restores the private party first; the activity layer then restores field callbacks without resetting the owner's suspended script and schedules its original native encounter. Once actual battle commitment occurs, normal existing co-op result/recovery semantics apply, not solo fallback.

Round packets have exact size/version, current generation, monotonically ordered round and sender checks. Exactly one encounter owner is required, and the local echoed packet must match the immutable packet sent. A cancellation arriving after a READY packet was sent is transmitted in the next acknowledged round. It cannot be mistaken for consent. No automatic saving, durable preparation journal, new progression or power-loss recovery promise is added.

## Validation and remaining QA

Five focused tests compile production round logic, complete round driver, packet validator and private team-selection code with deterministic link/party doubles. They cover both-ready commitment, peer not ready, crossed ready/cancel, delayed cancellation acknowledgement, disconnect, timeout, stale generation/round/sender/version, invalid/fainted/egg/duplicate slots, original party preservation and source-level callback boundaries. Two existing partner-medicine tests remain passing. Build-option and existing candidate checks also run.

These are component and source tests, not rendered play or a complete native build. Full private native checkout remains unavailable through shell Git authentication; the connector supplies source files but no archive. Window layout/task lifecycle, actual SendBlock timing, both participant roles, original trainer script and wild fallback, switching, and simultaneous interruption need full linking and two-client disposable-save QA. Do not enable for real saves or advertise the complete shared Hoenn journey from these tests. Maya's integration, held payloads and live providers were not used.
