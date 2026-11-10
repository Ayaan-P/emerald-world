# Regional catching tutorial integration

Child of app #442 (3529f8b53ace3ce7707b289bee5b180275a09993), paired with
native #91 (526e4bd45f290676cd09b45dcfb5c4f0d163b0f4). Independent stack,
not Maya #410/#72 or RC12; existing combined-region build options apply.

Viridian's existing Weedle catching demonstration now selects the Old Man's
native controller, matching tutorial windows, menu-return portrait and speaker.
Previously combined builds selected Wally's controller/presentation from the
Emerald executable identity. The shared selector uses the personal source
region only for catch tutorials. Hoenn Wally/Ralts and standalone defaults
remain intact. No new party transaction, save schema or donor assets.

This intentionally does not repair the separate early-rival FIRST_BATTLE
branches (initial enemy setup, AI, Oak guidance and accuracy). It also does not
claim arbitrary cross-region replay support or complete Kanto onboarding.

Validation: 29 focused app tests and two native component tests pass.
Actual tutorial entrypoints, region query and window setup run in three
fixture configurations; real controller/portrait expressions and speaker
wiring are checked. No full native link, controller-driven demonstration,
actual party preservation/save-restart, replay or two-client playtest.
Maya retains integration and gameplay QA. Held operations and live providers
remain untouched.
