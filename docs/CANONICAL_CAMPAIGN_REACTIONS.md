# Canonical agents can respond to the normal Hoenn campaign

The existing native CORE1 bridge already records the Petalburg Woods ambush,
Rusturf Tunnel goods recovery/Peeko rescue, and Devon briefing completion. Those
reports were previously usable by the pinned core-story adapter but not accepted
as evidence by living-cast authoring. This closes that integration gap.

A player's private REPORT/SYNC remains private. Only an existing explicit SHARE
receipt can inform the cast. Its fixed beat, arc, outcome, summary, native place
and publication source must match the authority's existing beat catalogue.
Interested canonical actors can independently reconsider their retained goals,
normal supplemental dialogue, and supported activities using that receipt. An
actor's unrelated expedition offer does not suppress normal campaign news.

There is no predefined Briney/Rydel/Wally/Steven arc in this change. The configured
author decides whether and how to respond, within the existing canonical-action
contract. Test authors make two different choices from the same actual shared
Peeko rescue, then read the changed dialogue through the normal original-actor
CAST response path. These are deterministic fixtures, not shipped story choices
or a claim that a live model chose them.

An event does not imply an actor personally rescued anyone or witnessed a battle.
It cannot by itself prove another actor's contribution or grant relationship
credit. Native reports remain authenticated client attestations, not server-run
battle simulation. No normal story flags, player rewards, parties, services,
travel, or original scripts are changed. No new NPC is spawned.

The existing Woods rescue, goods recovery, and completed Devon briefing are supported. More Hoenn campaign milestones
need reviewed native safe-point hooks and matching authority beat contracts;
this code does not silently infer them from location or time. Public news changes
the shared supplemental cast, not another trainer's personal progression. The
native pin is unchanged; integration/rendered verification remain Maya's gate.

## Devon delivery request

The paired native candidate adds `/history share devon` to the existing local
preview/confirm commands. It uses the already synchronized third progress bit,
`VAR_DEVON_CORP_3F_STATE >= 1`, without changing scripts or the wire format. The
reviewed original scene sets that state after the Letter/PokeNav and Briney
availability updates. The public claim is only that Devon requested delivery to
Steven, never that Steven received the letter or that another trainer progressed.
Older clients continue unchanged. Older authorities safely refuse the new SHARE
key; the adapter does not retry it or modify the player's story. A save rewind
between preview and confirmation prevents sharing. Native pin remains unchanged
until Maya pairs and verifies the candidate.
