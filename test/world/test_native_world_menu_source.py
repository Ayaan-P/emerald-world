"""Source contracts for the native handoff. Run with the integrated RC3 suite.

Integrated controller scenarios (not run by this source-only worker):
* At a full nine-row Start menu, WORLD opens Friends/Story rally/DexNav/Back.
  Check keyboard bindings and controller D-pad/A/B, including offline DexNav.
* ASK invite: inspect roster/status with Left/Right, choose Not yet, then Ready.
  Confirm menu-time presence stays busy and no guest moves before owner Go on.
* Owner at Roxanne (5,3): choose nearby/world, request, Cancel, re-request,
  then Go on with an invited/not-yet guest. Only fresh ready guests travel.
* Badge, uncleared Gym trainers, fainted party, wrong approach, offline server
  each produce an honest unavailable reason. No personal boss credit is shared.
* Guest arrival: Return leaves the rally. Owner Finish exposes Return/Stay for
  returning guests. Stay clears only the spatial return record, not party/items.
* While focused on Go on, change a remote roster/state. Focus must remain on
  that action or Back if it disappears, never jump onto a different command.
* A queued command interrupted by Start, movement, script, battle, native link,
  trade or Fly must not consume input, unlock that owner, or warp through it.
* Reject a stale rally ID after confirmation. Exhaust window slots, reset the
  scene, disconnect, and restore a return anchor without touching another UI.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class NativeWorldMenuSource(unittest.TestCase):
    def test_start_menu_reuses_existing_row_capacity(self):
        source = (ROOT / 'src/start_menu.c').read_text()
        self.assertIn('sCurrentStartMenuActions[9]', source)
        self.assertIn('MENU_ACTION_WORLD', source)
        self.assertNotIn('MENU_ACTION_FRIENDS', source)
        self.assertNotIn('MENU_ACTION_DEXNAV', source)
        self.assertNotIn('MENU_ACTION_RALLY', source)

    def test_uses_real_backends_and_no_readiness_forgery(self):
        source = (ROOT / 'src/platform/world_menu.c').read_text()
        for api in ('WorldRally_GetSnapshot', 'WorldRally_Status',
                    'WorldRally_HasReturn', 'WorldRally_Request',
                    'WorldRally_Choose', 'WorldTravel_RequestMenu',
                    'DexNav_RequestOpen', 'DexNavNative_Available'):
            self.assertIn(api + '(', source)
        for forbidden in ('WorldBridge_RallySend(', 'SetWarpDestination(',
                          'DoWarp(', 'WORLD_RALLY_REPORT', 'SDL_PollEvent(',
                          'InitMenuNormal(', 'Menu_ProcessInput'):
            self.assertNotIn(forbidden, source)

    def test_hook_runs_even_without_world_config(self):
        source = (ROOT / 'src/platform/world_bridge.c').read_text()
        hook = source.split('void WorldBridge_AfterFrame(u32 frame)', 1)[1]
        self.assertLess(hook.index('WorldMenu_Update();'),
                        hook.index('if (!sWorld.enabled) return;'))

    def test_integrated_core_defers_autoreturn_during_menu_dispatch(self):
        # Parent-owned core integration. Without this guard an offline recovery
        # can warp in the gap between closing the menu and dispatching Stay.
        source = (ROOT / 'src/platform/world_rally.c').read_text()
        field_ready = source.split('static bool8 FieldReady(void)', 1)[1].split('static bool8 Eligible', 1)[0]
        self.assertIn('!WorldMenu_OwnsFieldInput()', field_ready)

    def test_stateful_native_controls_and_guarded_translation_unit(self):
        source = (ROOT / 'src/platform/world_menu.c').read_text()
        self.assertTrue(source.startswith('#ifdef PORTABLE\n'))
        for guard in ('JOY_NEW(', 'JOY_REPEAT(', 'ScriptContext_IsEnabled()',
                      'WorldActivity_OwnsFieldInput()', 'NativeLink_IsActive()',
                      'WorldTravel_OwnsFieldInput()', 'ArePlayerFieldControlsLocked()',
                      'sMenu.pendingId', 'sMenu.freeFrames'):
            self.assertIn(guard, source)
        self.assertIn('memcmp(&screen, &sMenu.drawn', source)


if __name__ == '__main__':
    unittest.main()
