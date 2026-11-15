# Optional Hoenn practice circuit

A concrete demonstration of the generic battle-campaign system, not a replacement
Emerald run. Install it from the launcher's **Host controls → Install practice
circuit** button. Confirmation explains that it adds a separate venue and four
new practice coaches. Refresh host controls until it says ready. No model/API key
is needed to install this bundled example; configured agents remain free to author
other campaigns through the generic capability.

## Requirements and play

- Use this exact paired candidate, with a native build made using
  `python scripts/build_expansion.py --generated-regions`. Selectable regions are
  independent of experimental regional saves and Kanto. This does not change the
  default build or switch a running client's binary automatically.
- Host persistent generated-area archival, with four free world NPC/object slots
  and one free opened-region slot. Existing venues, NPCs and mechanics are retained.
- Bring your own ordinary party, roughly level 5–8, and normal money/supplies.
  No starter, level boost, healing, recruitment or inventory grant is supplied.
- Select **Hoenn Practice** through the existing generated-cave place picker,
  then enter via its ordinary entrance. It is an actual archived 31×31 plain cave,
  not a new Hoenn town, outdoor region or seamless map extension.
- Press **Ctrl+B**, select **Hoenn practice circuit**, and approach Gate Coach.
  The board shows actual coordinates and preparation. Visit the selected coach's
  **R Shop / L Tutor** menus if desired, then choose Battle normally.
- A reported win at Gate Coach offers Sky or Meadow. Either route leads to Final
  Coach: three battles for a successful run. A reported loss ends that attempt;
  the player can start another. No forced battle, revival, permadeath or extra campaign reward.
- Preparation changes with the route: ordinary Potion retail, then optional Fury
  Cutter, Rollout or Substitute tutoring through actual native eligibility and
  move-replacement menus. Tutoring is the existing repeatable free service.
- Each trainer/save has independent choices and progress. Native battle results
  are client attestations, not a trusted server simulation. No public achievement
  or NPC growth is inferred from them.

## Source grounding

The included source excerpts are pinned from Expansion
2abe34bd2b39ec9085e1d1aa5eda4cd5e65b8ed6 `src/data/trainers.party`:

- Gate: Calvin's Poochyena, level 5.
- Sky: Allen's Zigzagoon level 4 and Taillow level 3.
- Meadow: Tiana's Zigzagoon and Shroomish, both level 4.
- Final: Haley's Lotad and Shroomish, both level 6.

These are **new practice coaches**, not clones or relocated versions of those
canonical trainers. Only source species and levels are reused. The generic dynamic
adapter supplies its ordinary stable individual identity, IV15 and level-up moves;
it does not reproduce the originals' IV0, AI, music, sprites or trainer flags.
All four original story encounters remain unchanged. No prior catches or victories
are invented for the practice individuals.

## Installation and recovery

The host installer archives/pins the new venue, then stages a normal validated
mechanic extending the current source. The four records pass ordinary collision,
region, identity and companion validation. Gate Coach's one-time generic capability
plan publishes the graph only after real admission. Staged is not ready. A retry
reuses the exact staged source only if its original mechanic base is unchanged;
it never overwrites intervening work. Completed installation is idempotent across
restart. Existing source/identity conflicts refuse instead of replacing content.
The venue may already be archived if later deployment is blocked; this is not
claimed as successful population. Consult normal mechanic status in that case.

The example and its sources are inspectable and composable, not an enforced
future story. It occupies four of the current eight NPC slots, so it is best used
in a disposable playtest world before considering integration into an active one.

## Verification and ancestry

Tests install through the actual host action, admit through the real mechanic
commit path, execute the discovered campaign capability, select/transfer/ACK the
actual region, receive persistent native opponent descriptors, select preparation,
process three exact battle reports and reopen the authority to check identity.
Reported test victories are fixtures, not a rendered playthrough.

Stacked on app #347 and native #44. Still divergent from released RC12; Maya owns
reconciliation, linked/rendered multiplayer/balance QA and release. No merge/deploy.

The additional socket-based host suite could not run here: eight tests stop at
AF_UNIX socket creation with PermissionError before exercising host behavior.
The installer and full connected dispatcher flow use the existing in-memory
authority fixture; this does not substitute for launcher-window or live hosting QA.
