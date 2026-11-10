# Shared world cargo (draft)

Players can now take and place the same portable world props that independent
NPC plans use. An NPC can place a prop, a player can transport it within that
exact generated map, and another NPC can take it afterwards. There is one
custody record and object identity throughout, not copies or new bag items.

## Play

Use the matched native client's existing private command interface:

- `/guild cargo` shows help and cargo belonging to the active save lineage.
- Face an explicitly portable generated prop and use `/guild cargo take`.
- Walk to clear ground, face the intended adjacent tile, and use
  `/guild cargo drop ID`.

The existing native object snapshot removes carried props and displays placed
ones to observers. There is no carrying sprite, native bag entry, resource
quantity, native item delivery or reward. Player position is client-attested,
not anti-cheat evidence. The feature does not need a guild membership.

## Ownership and recovery

Up to four existing props per authenticated trainer/save lineage, within the
existing world-wide custody capacity. Disconnects, process restarts and save
switches retain custody without dropping or duplicating objects. The same
trainer and lineage can resume. Another save or trainer cannot drop them.

This draft supports same-map transport only: after leaving, return to the exact
original map revision to place cargo. It does not implement cross-region cargo
migration, an emergency remote return, or recovery from losing that save lineage.
Held props remain reserved in that case. Do not use cargo for irreplaceable
progression gates. Map revision changes remain subject to existing custody
validation; no guard is relaxed for private saves.

Placements use the existing terrain, object, exit and player collision checks.
Failed placement or receipt commits retain custody and do not alter the native
save. The source projection prevents stale mechanic output from duplicating a
held prop. Public history records the object operation but excludes trainer
identity, save lineage and private custody credentials. Agents can observe the
actual disappearance/placement; no automatic NPC response is promised.

## Ancestry and verification

Independent app draft based on published #390 at
56008c0b8296ce261266a8524125cc588e49b3f4 (local equivalent c22c9a9).
Keeps native #56 pin 739be20ecf1101f84cc2fb272587978350955b6d unchanged.
It is not based on released RC12. No changes to frozen #384/#56, Maya's
integration, or any of the four denied uploads. No recovery-worker dependency.

Six component tests exercise private command routing, real authority custody
and snapshots, source replay, restart, separate saves/trainers, NPC reuse,
collision, stale presence and transactional rollback. Rendered client and
multi-client integration remain Maya's QA; no live provider sessions were run.
