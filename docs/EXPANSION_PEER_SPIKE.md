# Experimental Expansion peer projection

This draft explores projecting authenticated Expansion-world presence into the donor's native overworld. It does not replace or integrate the vanilla game, migrate saves, enable link battles/trades, or port the other multiplayer and generated-world systems. Keep it off for normal play. It is not a release candidate.

The sidecar serializes at most eight server peers to an atomically replaced, bounded text file. The donor adapter reads it as untrusted data, validates positions against the active map and spawns temporary object events. The opt-in environment variable `EW_EXPERIMENTAL_EXPANSION_PEERS=1` enables projection in the sandboxed launcher. Test only with disposable profiles.

Before this is safe to use: compile and exercise against the actual pinned donor, run two native clients together, establish that transitions and every save path cannot persist temporary objects, and adapt map catalogs/identity across engines. Only the original Hoenn map-group numbering matches; Expansion's group 34 is FRLG while this repository uses group 34 for generated worlds. The current server still validates against the vanilla catalog. Do not claim Kanto or cross-engine interoperability.

The local component tests use mock donor structures and do not establish ABI, rendering, save safety or multiplayer correctness:

```
python3 -m unittest discover -s test/expansion_projection -p 'test_*.py'
gcc -D_POSIX_C_SOURCE=200809L -std=c11 -Wall -Wextra -Werror -Itest/expansion_projection/stubs engines/expansion_peers.c test/expansion_projection/test_projection.c -o /tmp/expansion-projection-test
/tmp/expansion-projection-test
```

The Expansion join command can reuse the existing pinned-TLS broker with a
trainer invitation (`--remote HOST:PORT --invitation FILE --pin SHA256`). The
broker operates in the Expansion engine's separate world/profile namespace;
no vanilla save is copied or reinterpreted. The routing and credential reuse
have mock tests only. An actual remote session, hosting UI, and feature parity
are not verified. This is not safe for real saves or ready for playtesting.

An additional opt-in, `EW_EXPERIMENTAL_EXPANSION_LINK=1`, compiles and starts
Emerald World's existing authenticated LINK transport and virtual cable state
machine in the donor process, mounting only that world's transport directory.
This is the protocol transport, not the Expansion battle or trade integration:
no game menu issues invitations, and the donor's engine link hooks have not yet
been ported. Real socket connections and LINK traffic have not been tested.

The experimental build also generates an overlay of the donor's link engine
with the existing world's virtual-cable command validation and frame hooks.
The donor checkout is not modified and generation fails if expected source
anchors change. This is a work-in-progress engine port, not a claim that battle,
trade, consent flows or co-op work; no real LINK session has been tested.

Experimental LINK channels identify the Expansion ABI as `LINKEXP1`. A new
server rejects battle/trade/tag offers between that label and legacy vanilla
LINK channels before consent or command handling. This is a compatibility
label supplied by the client, not authentication or proof of executable
integrity. Incompatible Expansion ABI revisions must use a new label. Older
servers do not recognize the label, so experimental LINK remains unavailable
there rather than silently negotiating a potentially incompatible session.

The dual-engine replay can also exercise the real world authority and client
snapshot parser using in-memory protocol delivery. It does not open sockets or
establish that networking, matchmaking, battle or trade work end to end.

A further `EW_EXPERIMENTAL_EXPANSION_ACTIVITIES=1` opt-in (requiring both
experimental peer projection and LINK) adds single- and double-battle invitations and
explicit accept/decline menu using the donor's own cable-battle task. Other
activities, including trade and tagged encounters, remain
disabled. This new flow has not been exercised between real clients and must
not be used with valuable saves. Engine labels prevent accidental mixed-engine
pairing but are not protection against a malicious peer.

Trade remains disabled. An Expansion-specific pair validator is being added to
check the actual 100-byte donor ABI, checksums, species, moves, items, modern
form attributes and names before any received Pokémon enters game state. This
alone is not a complete trade-safety or consent implementation.
