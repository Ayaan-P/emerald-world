# Optional future co-op history sharing

Existing `/history battle` still previews and shares one result. The solo
`/history battle on` setting is not widened to cover co-op. Instead:

- `/history coop on` previews the exact scope.
- `/history coop confirm` saves a separate opt-in for this player and save.
- `/history coop status` shows acknowledged ON/OFF or unconfirmed status.
- `/history coop off` stops local automatic capture/sending immediately, clears
  queued co-op results, and requests persistent OFF. If the request cannot be
  sent, the UI explicitly asks to retry before reconnecting.
- `/history coop cancel` cancels an enable preview.

Only future captures after ON acknowledgment are eligible for automatic sharing.
Acknowledgment clears any older cached co-op result, so enabling does not share
a backlog. Reconnect queries the saved choice and waits for acknowledgment;
disconnect/save switch discard volatile captures. Unsupported servers leave
sharing unconfirmed and disabled. There is no automatic retry after a sent
report, since delivery can be uncertain. The single-slot result buffer is not a
durable event archive: a newer result can replace one waiting to be sent.

Each shared event says only that one anonymous local participant reports a
co-op win or loss against the named original trainer at the capture map. It is
a client attestation, not a verified unique battle count, shared save progress,
partner consent/identity, party roster or reward claim. Native capture still
comes from existing validated co-op completion/private-party reconciliation.
The server requires the current negotiated connection, active save, fresh idle
presence, and the separate setting at ingestion. Serial deduplication prevents
same-session replay or relabelling.

The existing canonical-character relevance path accepts the new provenance so
characters may respond through existing supported actions. No response, new
relationship or story outcome is forced. Game scripts, battles, parties, rewards
and save formats are unchanged. Preferences are private server settings scoped
to the player's connection identity and save lineage. Revoking stops future
automatic reports; already sent reports may remain in world history. Separate
explicit one-result sharing remains available.

## Verification limits

Production authority functions are tested with SQLite and synthetic connections;
production native capture, command, acknowledgment and send functions are
compiled against a small deterministic harness. Tests cover distinct solo/co-op
consent, acknowledgment boundaries, no backlog, revocation/late acknowledgment,
wrong save/stale presence, duplicate serials, source relevance and privacy.
No linked native build, rendered controller/chat UX, real multiplayer session,
live provider call or real save test was performed. Do not claim playtesting.
