# Experimental guest contest results

App work starts at #395 (remote 639c2e64ee18c1ccabb3a9fe321d51a259ac8f57;
local equivalent 7f82d1d5e4062522b8716874992d4a3ee39f4700). It is not based on
RC12. Native draft #58, commit 8db71c37086fec1139f6e0919c1d7a7ca9b9a889,
is an independent child of #57 at 84ec1023888b616f163b9e1b82e60450cb07639a.
All four modified native source files were compared against that exact remote base.
Its existing src/*/*.c wildcard includes the new report module without a build-list edit.
The app pin and unchanged map/species catalog pins use this native head.
No asset, map, species or roster-layout data changed. Linked build and playtest remain
pending; this is a paired draft, not an available or verified release.

Player path: before choosing the optional existing NPC guest, enter
`/contest-report yes`. Help discloses that the guest placing goes to ALL world
players/agents. This is one contest only; `/contest-report stop` cancels reporting.
Stock contest selection, AI, scoring, human rewards and saves remain unchanged.
The result hook runs after stock CalculateFinalScores and excludes linked contests.
A separate C channel on authenticated link transport admits the actor, entry
revision and category and binds the actual owned individual on the authority.
The native reporter retries the same result until acknowledged, then stops.
Disconnect clears local participation; there is no automatic opt-in after restart.

Authority retains the result once per lease, bound to authenticated trainer/save
lineage. Replays acknowledge the same placing; conflicting replays fail. Admission
expires after one hour. Reporting publishes no human participant name, save identity,
party, placing or private Pokemon data. The host DB retains the private lease binding.
An unchanged digest records whether the offered individual still matches authority
state. Changed ownership/state is NOT overwritten. A report is a client attestation,
not verified contest execution. Registered NPC agents may independently react through
the existing bounded reaction system; no model is invoked by the report handler.

Stock GiveMonContestRibbon updates ONLY the human party Pokemon. The NPC guest is
ContestPokemon presentation data, not a finalized Pokemon. Consequently this feature
never imports a client Pokemon blob, grants a ribbon, changes condition/friendship,
or manufactures training. That is deliberate truthful reconciliation, not missing
ribbon emulation.

Local component tests exercise the actual small native reporting module with a fake
transport, source hook placement, authority leases/replay/save isolation/restart,
unchanged state and changed-individual reporting. No full native build, rendered
contest, linked end-to-end session or live model call has been performed.
Frozen #384/#56 and all denied/uncertain operations are untouched.
