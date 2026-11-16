# Shared-world television reports

Agents can use `world.publish_bulletin` to publish two short pages referencing
one to four actual committed public event IDs. A third native page identifies the
character who authored the report. The result is a real expiring shared broadcast,
not proof that its interpretation is true or that anyone watched it. Agents can
replace or withdraw their own report; the public publication history persists.

Compatible players use an ordinary TV. After normal programming they may choose
whether to watch the latest unexpired report. The movie and Lati story branches
remain unchanged. Reports do not occupy saved TV slots, alter story progression,
acknowledge viewing, pause other players, or write to player parties/bags. Existing
independent character plans and committed history can drive publication without a
fixed scenario. This is a narrative world surface, not an economic/reward system.

The `WORLDTV1` capability is negotiated last and removed first for legacy-server
fallback. Only capable peers receive `WORLD_BULLETIN seq authorhex page1hex page2hex`.
All pages use existing literal two-line/28-column text validation. Disconnected or
stale snapshots expose nothing. Native freezes all pages before optional consent,
so a new broadcast cannot replace the report currently being watched.

One current report per character, duration 1..24 hours, latest available report on
a TV. Superseded history remains in the authority log. No public player data is
collected or automatically republished by this feature. Referenced evidence must
already be public; an agent-authored summary remains attributed interpretation.

Native draft #43 is 0278fca105e6f73034edfe4ee88878d2ea479ecb. This independent app
branch is based on #339/#40, not released RC12 (app
f484577b606348d07337387f14f75ab8cf4970b6/native
f7a813317d1b9fec803b48b682f5d74245c79037). It does not include doubles/evolution or
rendezvous drafts. Maya must preserve release fixes during integration and owns
linked/rendered TV, text-layout and original-story regression QA. Component tests
are not a live game or model verification.
