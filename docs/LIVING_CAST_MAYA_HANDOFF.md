# Living-cast candidate handoff

## Scope and exact pairing

Use the head of app draft **#286 / dot/rc12-living-cast**, including this handoff
and scoped author-prompt fix, paired with native draft **#26** at
`f5b45730ef96debf512f501109b3388ab2342cc6`. The app gitlink, builder PIN and
`engines/living-cast-candidate.json` all agree. Both drafts target their respective
`dot/rc12-core-story` branches; this is not a standalone main merge or a release.
The consolidation started from app `340b694a218819d146849dc28507631e9943ef9e`
and native `f5b45730`. Reconcile any newer main/Maya work before integration.
Main last verified at `80b14ebfbfd4dd4da2dc16d886a37f0db1f45516`.

## One actual entry path

1. In an isolated integration checkout, initialize the pinned engine and run the
   normal `scripts/build_expansion.py --check` and build. Never use a live save
   for this acceptance run. See `LIVING_CAST_RC_SETUP.md` for prerequisites.
2. Supply the selected provider's key in the host launch environment, not in
   the browser or a checked-in file. Open an Expansion local world, Living cast,
   choose Anthropic Messages or OpenAI Responses and an explicit accessible
   model ID. Review public-context/cost notice. No provider fallback occurs.
3. Choose **Initialize and follow original cast**, then **Start world author**.
   The real host commissioning request can seed only initial goals/greetings.
   Each admitted goal enables bounded independent planning. No fake adventure,
   campaign-sharing switch or private memory worker is needed for first greetings.
4. Continue two separate trainer saves normally. Visit original Rydel in the Bike
   Shop, Wally at Wanda's house where present (or after his Victory Road battle),
   Briney at his house while his original service is available, or Steven at his
   house after the original Dive scene. Presence is governed by each save's
   vanilla scripts. This candidate does not summon absent characters or skip story.
5. After a character has an authored record, talk normally. The supplemental
   response returns to normal dialogue/services. SELECT can enter an authored
   shared conversation with optional listeners/advice; the speaker decides.
   START can open that actor's actual local project choices if one exists.
6. Leave the author running while playing. Characters may choose supported
   projects, independently commit assigned shared actions, invite another existing
   actor into an exact project role, accept or refuse, and reconsider from real
   receipts. This changes available shared scenes, not native rewards or story
   flags. There is no fixed Rydel/Wally scenario shipped, and models may wait.
7. Campaign events affect this shared author only when players use existing
   explicit public-sharing controls. Personal conversation/relationship memory
   remains separate and save-scoped. Anthropic selection here does not authorize
   private reflection processing. Closing/disconnecting the host stops its author.

## Consolidation fix

Canonical turns previously inherited the generic prompt demanding arbitrary
Python source while admission required `canonical_actions`. They now receive one
consistent typed-action contract, canon/evidence limits and isolated test format.
Dynamic-character turns use their own typed contract; general world authoring
keeps its existing source contract. This fixes a real first-run author mismatch,
not a change to native gameplay or a claimed live-model success.

## Verification and acceptance boundary

Run `python3 scripts/check_living_cast.py` for the repeatable authority/component
suite. With exact native source supplied through `EW_NATIVE_SOURCE` and
`EW_RC7_ENGINE`, production C source fixtures also run where supported. Without
those inputs some source fixtures explicitly skip. React: `npm run test:ui` and
`npm run build` under launcher-web. No command calls a model or reads real keys.

The prior green GitHub check on app340b was **Linux player packaging only**;
it was not living-cast or linked-native validation. This batch adds a dedicated
read-only candidate component workflow for the actual draft base branch.

A separate real UNIX-socket GM integration test was blocked here by
`PermissionError: Operation not permitted` on socket creation; no alternate
transport was used to bypass it. The scoped prompt tests run without sockets.

Local builder check is blocked because the full engine submodule is not
initialized in this component workspace. The separate partial native fixture
checkout is not a linked build. Live API access, model content quality and latency,
rendered panels, save/reload safety in a full native run, multiplayer cancellation
and original story/service transitions remain acceptance work for Maya. Current
API codecs match reviewed official endpoints; no live provider call was made.

Do not present this as an RC release or fully autonomous simulated Hoenn.
Canonical physical movement remains the bounded reviewed Rydel scene; arbitrary
cast travel, verified independent Pokémon training and full synchronized campaign
cutscenes are not supplied. Shared project work is explicit authority state,
not proof of physical labor. Maya owns integration, QA, merge and release.
