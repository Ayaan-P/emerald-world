# Shared campaign checkpoint regrouping

Independent app-only draft on #389 (44cf70c2629e5de1035051fb54ef562c5e32bfea), not based on the released RC12 pair. Native pin remains frozen #56 (739be20ecf1101f84cc2fb272587978350955b6d). No frozen branch or denied file changed.

## Player journey

Open the existing in-game campaign board and host/join an authored shared campaign. After everyone finishes a stage, other members can volunteer to speak. The current speaker can pass speaking to a volunteer. The new speaker controls subsequent route choices; suggestions remain advisory.

At that checkpoint the speaker can take an available route and reopen the party. Existing members retain their own prior reports, but the next stage is a fresh lobby. Members can withdraw individually without cancelling the remaining party. The speaker must first pass speaking to a volunteer if anyone remains. New players join using the existing invitation code and begin at the chosen stage with no inherited battle results or personal history. Begin still enforces 2–4 participants and the exact role count of split-party campaigns.

All actions are native campaign-board options using the existing state-bound, single-use tokens. The existing chat commands also accept volunteer-speaker, pass-speaker TRAINER, regroup ROUTE and withdraw. Legacy leave still explicitly cancels the shared run; it is distinct from withdrawing yourself.

## Boundaries

Party membership is fixed during active stages: no result substitution, forced replacement, automatic offline takeover or abandonment of an in-progress battle. Regrouping happens after all stage reports, not as a way to skip an unfinished stage. No participant receives another player's prior reports. Withdrawal retains the departing save's inactive history until that player starts or joins another run, matching the existing single-current-run storage model. It is not a permanent campaign archive.

Speaker changes and group updates are durable SQLite transactions. Existing private trainer/save-lineage bindings remain in force. Battles remain normal optional native NPC battles with client-attested results, not server-verified victories. No party/bag/save mutation, rewards, new native protocol, direct model use, or live/rendered verification is claimed.
