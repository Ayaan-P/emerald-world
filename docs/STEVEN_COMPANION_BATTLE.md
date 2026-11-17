# One optional wild battle with Steven

This paired candidate uses Expansion's existing Steven partner preset and
multi-battle engine. It does not enable NPC followers, create an overworld Steven,
change save layout, invent a team, or convert campaign trainer battles.

A canonical Steven author may set `companion: "steven_wild_once"` based on normal
public character evidence. The original post-Dive home conversation supplies the
current authenticated actor/run/version context. `/guild cast steven` discovers
the offer. Native `/history companion steven` previews fixed terms;
`/history companion confirm` requests the current invitation, and
`/history companion` checks whether it was acknowledged. `cancel` clears it.
Older servers refuse the optional ALLY action; no public-chat fallback exists.

Once acknowledged, Steven can join one ordinary single wild encounter within
two minutes. This uses his original high-level team without scaling. The native
player's own Dive flag and Steven-house state must still be valid. Normal wild
battle HP, EXP, consumables, catching, defeat and whiteout behavior apply. The
player keeps all six Pokémon: half-team builds refuse. No free healing, forced
catch, original party replacement or earned persistent Steven training is added.

Existing co-op encounters have priority. Followers, active links, pending co-op,
Pike/Pyramid/Hill/Safari encounters and double encounters do not use this adapter.
Any other battle or disconnection cancels the pending invitation. No battle
outcome is uploaded or treated as public actor growth. Acceptance does not mean
an encounter occurred. After a successful acknowledgment, the fixed one-shot
invitation remains valid until used/cancelled/expired; a later author revision
does not retrospectively revoke an already granted invitation.

The normal wild engine creates the actual encountered Pokémon. Only then does
the adapter populate the separate partner party using `FillPartnerParty` and
`TRAINER_PARTNER(PARTNER_STEVEN)`. It saves/restores the previous *partner*
context in RAM around the unchanged wild return callback. It does not call the
script-oriented multi-battle entry, which expects script/party-selection cleanup.
No player-party rearrangement or follower hide flag is used.

Validation compiles production request/state and battle-adapter functions with
explicit engine API doubles. Covers original preset selection, unchanged six
player Pokémon, partner-context restoration across seven outcome codes,
co-op/half-team guards, cancellation/late acknowledgment/expiry/disconnect,
authenticated authority admission and actual CORE reply. These are component
checks, not a full linked or rendered battle. Maya must verify real AI turns,
partner sprite/UI, catching, EXP, consumed items, six-mon ownership, whiteout,
save/reload, and co-op transitions before integrating the native pin or release.
