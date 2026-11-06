# RC4 player scope and compatibility

RC4 extends the existing Emerald World game. It does not launch the Expansion engine or create separate permanent vanilla/expanded trainer saves. Vanilla world settings remain the default. Hosts own gameplay settings; joining trainers retain their own parties, bags and story.

## What the content manifests actually mean

The pinned Expansion source is `bb3fd057061cdd7e6a9e79b76abb41924ee44ecc`, using the recorded Gen 9 data profile. This is a pinned revision, not a claim to be the latest upstream.

The dependency-resolved runtime selection contains **11 added species entries**, of which **10 have implemented acquisition paths**. **Kubfu is data-only and has no implemented acquisition path**. This is not a complete National Dex release. The importer maps and reports unsupported records rather than replacing missing moves/abilities or pretending reserved entries are playable.

Implemented opt-in additions, alongside the original encounters:

- Route 101: Gimmighoul Roaming, Meltan and Cosmoem.
- Route 102: Type: Null.
- Route 103 grass: Turtwig and Chespin.
- Route 103 fishing: Arrokuda, as an additional Magikarp encounter variant.
- Supported level evolutions: Turtwig → Grotle at 18 → Torterra at 32; Chespin → Quilladin at 16. Torterra has its Earthquake evolution-move learning path.

Unlisted later evolutions are not implied. In particular Barraskewda is not selected. Selecting expanded encounters preserves the stock species and adds overlay RNG only for mapped encounters; it is not an identical-RNG replay of vanilla. Intentional DexNav hunts keep their exact selected target.

The move catalog adds **55 moves**, preserving original IDs. The total move-table count is 410. Names, supported normal abilities, complete resolved level-up learnsets, and front/back/icon assets are generated together. Hidden abilities, imported egg moves, all donor TM/tutor coverage, donor cries, followers and arbitrary form-changing mechanics are not included. Front rendering uses the imported static first frame. Native critical-hit behavior and legacy damage rounding remain; this is not a claim of complete Gen 9 battle parity.

Machine-readable coverage and asset provenance are in `tools/expanded/{coverage,assets}.json` and `tools/expanded_moves/coverage.json`; the Linux archive includes copies under `credits/expanded/`. Acquisition support in a manifest is not itself native gameplay evidence.

## Modern rules and Mega Evolution

Modern physical/special categories and Fairy battle typing/effectiveness are world settings. Some out-of-battle presentation follows legacy compatibility policy; do not interpret this release as a complete replacement of every legacy information screen.

Mega Evolution requires modern split in the host configuration. Checking Mega in the launcher visibly enables that dependency. The native build supports Mega without a private capability override, but vanilla worlds still leave it off.

For the ordinary item path: after earning the Mind Badge, enable Mega in the world and inspect Steven's rock collection in his Mossdeep house. The native script grants the Mega Ring and offers the supported stones. Equip the matching stone to an eligible Pokémon. During move selection, START selects Mega and the normal move confirmation continues the turn. Availability is once per trainer per battle. Unsupported forms and non-stone exceptions are not implied by this feature; Charizard X is not in the current native profile table.

Native acceptance uses explicitly controlled level/item fixtures where stated. It does not establish that those test Pokémon or stones were earned through the campaign. The receiving battle client is a native controller/render mirror, not an independent second damage simulation. Form packets and rendering must agree; authoritative stats/damage belong to the primary engine. Temporary Mega state is cleared on return, not written as a permanent species change.

## Saves, multiplayer and updates

Original Pokémon/save structures remain 80/100 bytes. The widened native experience-yield field is a readonly species-table field, not a saved Pokémon field. Expanded Dex state uses a trainer-bound, CRC-checked supplemental journal; legacy saved arrays are not widened.

Current clients negotiate both authoritative world rules and a native content identifier before compatible activities. Nonzero-rule worlds refuse missing/different content. Both-absent legacy vanilla compatibility is retained as an explicit legacy exception, not content attestation. All participants in an expanded session need matching content. Do not assume RC3-hosted services understand the RC4 admission protocol; hosting software must be updated separately, with existing identities and state preserved.

Keep a backup before updating. Do not open expanded saves in older binaries or assume retained installer versions make such a downgrade safe. No separate permanent expanded trainer tree is created.

Native tests that use test-input persistence overrides are labelled private; they do not certify ordinary launcher persistence or Windows behavior. Windows acceptance remains friend-owned. A Linux proof does not establish a Windows result.

## Acceptance status

Release acceptance is recorded separately from catalog generation. Candidate-5 has a clean warning-as-error native build, unchanged vanilla golden/save smoke, and a real two-client Mega Sceptile battle using normal production authority, including actual Grass-to-Grass/Dragon typing, natural completion, idle cleanup and preserved persistent party identities. Its expanded-species multiplayer validators have been corrected. Four native clients completed all twelve directed peer views and movement over an SSH-forwarded, pinned-TLS WAN path; a genuine shared Cosmoem catch, owner-only ball/party changes, ordinary SAVE, cold Continue and re-SAVE passed, as did explicit-consent Cosmoem trade/cold persistence. Idle trainers remained byte-identical. This was an isolated temporary authority, not a production deployment or direct-public-endpoint test.

Arrokuda fishing/capture, Grotle-to-Torterra level-32 evolution with the Earthquake offer/replacement, and five native self-drop/White Herb cases passed on candidate-4; those effect implementations were unchanged in candidate-5. Test item/loadout/persistence controls remain labelled in their evidence. Candidate-4's archive was checksum-verified and installed/updated from the official RC3 archive in an isolated home with byte-identical private save/journal files; this does not certify a later archive automatically.

RC4 remains unpublished: the full pinned-roster scope is not met. Further shared move/ability implementation, faithful metadata resolution and generic acquisition are being integrated as a combined batch. Staged data or a successful native tracer is not full-roster completion.
