# Coordinated wild retreat (experimental)

Default off. Build both clients with EW_COOP_RETREAT=1. The app switch is
--experimental-coop-retreat --development. A distinct co-op wire version rejects
mixed retreat behavior before private party staging. Competitive link battles,
ordinary solo battles and original save formats are unchanged.

In a co-op wild encounter, each trainer chooses Run in the ordinary action menu.
Every living player-side active Pokémon must choose Run and pass the native
escape/trapping checks. An absent/fainted active partner does not veto retreat.
One deterministic first runner makes one native speed/RNG escape attempt. Other
Run actions are consumed, including on failure; a second runner never gets an
extra escape roll. A non-running partner's selected action is not overwritten.
A lone Run request spends that trainer's turn and currently uses the stock
failed-escape message. This is not a new agreement dialog, and the message does
not yet distinguish a partner's different choice from trapping/RNG failure.

Smoke Ball, Run Away, configured Ghost escape, trapping abilities/status and
no-running/first-battle rules are checked through existing native code. Trainer
co-op encounters cannot use competitive-link forfeiture. Genuine wild opponent
flight keeps its native MON_FLED path. Successful party retreat produces RAN,
not WON/LOST plus LINK_BATTLE_RAN. Existing co-op completion matching and private
party reconciliation remain responsible for closure; no trainer victory receipt,
reward or story credit is added. Disconnect/abort continues existing restoration,
not a fabricated successful escape.

Validation: an extracted production coordinator is compiled and exercised over
choice, active-party, trapping and success/failure combinations; source checks
cover independent selection and trainer restrictions. App checks cover default-off
configuration and existing regional/Rusturf build contract. This is not a full
native build or a two-client/rendered playtest. Private native checkout is still
unavailable through shell Git authentication. Required linked QA: both Run,
mismatched actions, single surviving trainer, trapping/item/ability exceptions,
failed escape followed by enemy actions, opponent flee, competitive link and
trainer restrictions, disconnect during completion and private party restoration.
No actual user saves or live providers were used.
