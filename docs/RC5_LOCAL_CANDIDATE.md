# RC5 development evidence — frozen through PR #191

For the published candidate's scope, installation and limitations, see [RELEASE_RC5.md](RELEASE_RC5.md). The records below describe the pre-release development journeys, not additional release acceptance.

## Run

From this worktree:

```sh
./build/rc5-integration/run-rc5.sh
```

The wrapper opens the existing React launcher using this worktree's native binary. It is a local-workspace launcher, not a standalone redistribution package. Use **Expedition workshop** to create/open a local host, generate a cave or outdoor area, and choose a saved area. A model request is an explicit user action. Local host shutdown retains generated areas; trainer progress still requires ordinary in-game SAVE after returning from a generated area.

## Integrated scope

- Existing RC5 cave, co-op, actor/rendering, matched trainer, smooth presence and batched authority stacks.
- #188: persistent local-host generated areas.
- #189–190: opt-in native 63×63 outdoor terrain and authenticated CAVE6 sharing, reconciled with PEER32 negotiation.
- #191: area archive and owner reactivation.
- React controls reuse the actual session authoring/archive implementations; native WORLD labels now say “generated area.”
- Local world keys are short enough for a 24-character trainer at the default Linux worlds root. Existing workshop keys remain recognized.

Only one generated area is active at a time. Outdoor areas use existing Route 101 encounters and art. This is not simultaneous regions, custom outdoor wildlife, authored NPCs or generated artwork. No PR beyond #191 was included.

## Actual execution evidence

- Combined gate-on WERROR native build: `build/rc5-integration/areas-build-final.log`.
- Production React build: `launcher-web/dist/`.
- Two native trainers: `/home/ayaan/projects/emerald-world-research/rc5-areas1/acceptance.json` (`ok=true`). The journey includes a declared controlled cave encounter fixture, shared battle, independent SAVE, actual model-authored outdoor entry/presence/return, occupied switch refusal, reactivation, persisted host restart and native reconnect. Seed and binary remained unchanged; owned processes were reaped.
- Real model outdoor authoring via React bridge, archive switching, host restart and save isolation: `build/rc5-integration/areas-authoring-journey.json`.
- Actual Chromium saved-area activation: `build/rc5-integration/react-areas-browser.json` and `react-saved-areas.png`.
- Actual offline native outdoor walk beyond the old 31-tile boundary, return and unchanged save: `build/rc5-integration/native-wilds-offline/`.

## Preserved baseline and remaining limits

`checkpoint/rc5-shared-caves` and `build/rc5-integration/pre-areas/` preserve the previously passing cave candidate, its binary, launcher build and scoped evidence.

Full six-party rotation, medicine targeting/consumption and catch-to-storage have NOT received complete native acceptance. The earlier six-party controlled run was interrupted by a broken control socket and was closed as incomplete. Shared co-op acceptance here is not proof of all six-party operations. No WAN/capacity benchmark or Windows build was performed for this candidate. RC4 was not modified. No remote merge, push, release or deployment was performed.
