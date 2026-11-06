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
are not yet ported. Expansion maps whose IDs collide with vanilla generated
worlds are intentionally not advertised as presence.
