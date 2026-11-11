# Optional co-op Hold back build candidate

App parent: #481, b2ed08efc2fc96405ab86a196fb7d36813b2123a.
Native pin: d9fc88c076b617b1781ea926a4387fcbac0f7790, independent atop native #119. No four-human relay changes included.

This config exposes --experimental-coop-hold-back only with --development. EW_COOP_HOLD_BACK defaults to 0 and is exported to the native and recursive reference builds. All participating clients must match. Existing regional reader switches remain unchanged; this feature changes no save format.

The native cooperative action menu advertises SELECT: Hold. A default-No confirmation explains that foes still act and there is no protection. Confirming uses a dedicated action that does not attack or spend an item/PP; it returns through normal action cleanup/end-turn dispatch. Existing catch and private reward ownership remain unchanged. Forced-action states and ordinary solo/competitive play do not offer it. See native docs/hold-back.md for exact exclusions.

App checks: two focused tests verify the explicit development gate, default-off flag propagation and exact native pin. Native component checks pass, but no exact-head full native build, rendered UI, linked co-op battle or saved-game playtest has been performed. This is a disabled integration draft, not release readiness. Run poison/burn/weather, foe-first faint, catch success/failure, disconnect and repeated-turn QA with synthetic saves before considering enablement.
