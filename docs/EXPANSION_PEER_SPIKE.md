# Experimental Expansion multiplayer integration

This draft adapts the existing Emerald World authority and native LINK stack to
the pinned Expansion engine. It is incomplete and not a release candidate.
Expansion profiles are separate; vanilla saves are not migrated or reinterpreted.
Never use valuable saves for this experiment.

The switches are deliberately nested and all default off:

- `EW_EXPERIMENTAL_EXPANSION_PEERS=1` projects server presence as overworld peers.
- `EW_EXPERIMENTAL_EXPANSION_LINK=1` starts the existing LINK transport and
  virtual cable, mounting only this Expansion world's transport directory.
- `EW_EXPERIMENTAL_EXPANSION_ACTIVITIES=1` additionally requires the preceding
  switches and exposes explicit single/double battle invitations.
- `EW_EXPERIMENTAL_EXPANSION_TRADE=1` additionally requires all three switches
  and exposes party-only trade. It is not ready for user testing.
- `EW_EXPERIMENTAL_EXPANSION_CONTROL=1` with `--agent-control` opts into
  a separate player-control endpoint. It reports frame, map, position, battle
  flag, field objects, own party and screenshots using a limited Expansion schema; it is not
  the full vanilla observation ABI and is not yet ready for use.

Expansion LINK channels use the `LINKEXP1` compatibility label. A new server
rejects invitations between that label and vanilla LINK before consent. This
label is client-provided compatibility metadata, not proof of executable
integrity. Incompatible Expansion ABI revisions must use a different label;
older servers reject the new role instead of silently pairing incompatible games.

The build generates donor link, cable and trade overlays without modifying the
pinned submodule, and fails closed if expected source anchors change. The trade
overlay checks received Pokémon and mail/ribbon blocks, bounds and exact-pair
consent; the final save signature is flushed to the donor's atomic save file
before acknowledging completion. These are implementation steps, not a proof
that a real trade or crash recovery is safe.

Two independent donor games have exchanged trainer positions through the real
world authority and client parser in an in-memory relay. This does not exercise
sockets or TLS. The battle/trade state tests use mocks, and real client-to-client
battle, trade, disconnection and save behavior remain unverified. Generated
worlds, co-op, complete launcher integration, map catalog and save migration
are not yet fully ported. An offline-only 31×31 EWGMAP01 cave experiment is
under development and not ready for user testing. A donor replay entered and
left a 31×31 cave; a forced save attempt inside was rejected without a flash
write. Another replay saved after returning and reloaded the original map and
party. It does not enable shared worlds, encounters, wilds or authored events.
Expansion map IDs that collide with vanilla generated worlds are withheld from
presence.

Control frame scheduling and launcher scoping have only been tested with fakes.
A donor replay inspected actual party data and the field-observation schema; no
live player-control socket has been exercised. Replay and control are
mutually exclusive; vanilla world and battle observations still require porting.

The cave adapter reserves donor-local group 75 only after verifying that the
pinned donor has 75 groups; it uses a separate synthetic header and refuses
saves while inside. This is experimental and not a save-safety proof.

An additional test-only build substitutes a file relay for the link transport
and drives two real donor games through the in-memory LINK coordinator. It
creates no sockets and cannot establish actual network, TLS, or transport
correctness. The two-game battle test is experimental until it passes.

The optional `EW_TEST_PLAY_TURN=1` extension did not observe a completed turn
before a donor process exited; investigate the gameplay state and termination
before claiming battles work end-to-end. The normal CI gate checks battle entry
only. Both paths use the file-only test relay, not real transport.

The donor's DexNav is an opt-in experiment behind
`EW_EXPERIMENTAL_EXPANSION_DEXNAV=1`. Its menu unlock is transient, and the
adapter gates search hooks when the switch is off. It uses reserved donor
flags/variables; per-species search levels stay disabled to avoid changing the
save layout. Donor GUI and gameplay validation are pending.
