# Campaign experiences can inform optional recurring-trainer battle formats

This explicitly combines #363 and #340. It reuses the existing sharing boundary,
character author queue, owned-roster system and optional native doubles adapter.
There is no predetermined story reaction, new consent toggle, forced encounter,
replacement vanilla trainer battle or automatic Pokemon growth.

## Connected experience

A player who enabled the existing standing battle-sharing setting on the current
save may share an ordinary native single-trainer result. The public event remains
an anonymous client attestation, not a verified victory. A recurring generated
trainer interested in that place can independently choose a new optional format
through world.set_battle_format. An original cast member can also request this
supported work from a generated trainer, which independently accepts or declines.

A later player approaching that trainer sees and explicitly chooses the optional
challenge. The native adapter uses ordinary single/double trainer machinery with
usable-party and field/co-op/link guards. Doubles requires two identified owned
NPC teammates and two usable player Pokemon. Accepted format revision and team
are frozen. A changed future preference cannot rewrite an admitted fight. Legacy
clients refuse unsupported doubles rather than silently converting to singles.

This is one player versus an NPC, not two-player multi battle. Short battle
campaigns still bind the accepted fight to the same private save-specific run.
No campaign progress is inferred from public speech or a character decision.
Results are private client reports, not trusted earned NPC training.

## Exact pairing and ancestry

App parents: #363 8dec17280a4cfd0360d1f9ff8cc724d7506c9ec0 and
#340 efb6211470a582cc820b611ee38c90ca4ea56b40.
Native parents: #52 d209d94393086ceda8a5f63de5c3cfe4732ac432 and
#41 e0e071078bd4f3fde671818dc87eae9bde745170.
Paired native #53: 879b6344aeeb3c4e65d0feb00f98655299225635.

Resolved conflicts by retaining the cumulative capability catalog and tests,
combining campaign binding with format freezing, and peeling CHARFORM1 before
WORLDTV1/rentals/contests/outbreaks in authentication. Both native HELLO paths
append that suffix and remove it first for legacy fallback. The existing TV
fixture now isolates its own parser block from the adjacent format parser.

Not based on released RC12 app f484577b606348d07337387f14f75ab8cf4970b6 /
engine f7a813317d1b9fec803b48b682f5d74245c79037. Maya's release and integration
branch are untouched. She owns reconciliation and final QA.

## Evidence and limits

Connected test uses actual standing-setting rejection/approval, public report,
reaction queue, response validation/action compiler, authority commit and generic
executor. It verifies unchanged individual identities/team, no forced challenge,
real V4 descriptor and retained short-campaign binding. Other tests exercise
stale/legacy refusal, frozen acceptance, restart and paired native parsing/launch
with explicit engine doubles. The model decision is a deterministic fixture,
not a live-provider test. Five compiled native component tests also preserve
ordinary TV behavior.

Full linked battle, rendered consent/layout, save-return, multiplayer and live
provider QA are not claimed. Actual player save files were not accessed.
