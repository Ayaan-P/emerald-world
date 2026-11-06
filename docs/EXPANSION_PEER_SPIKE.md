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
