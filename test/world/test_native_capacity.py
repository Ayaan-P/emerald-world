"""Capacity boundary regressions. Run only in the parent's integrated candidate.

The C fixture executes actual function bodies, not a Python copy of save logic.
It does not validate the complete native renderer or replace headless baselines.
"""
from pathlib import Path
import unittest
import test_save_isolation as save_fixture

ROOT = Path(__file__).resolve().parents[2]


class NativeCapacity(unittest.TestCase):
    compile_and_run = save_fixture.SaveIsolation.compile_and_run

    def test_high_campaign_and_player_slots_survive_without_overwriting_save_tail(self):
        self.compile_and_run(r'''
    struct ObjectEvent player = gObjectEvents[0], npc = gObjectEvents[1];
    memset(gObjectEvents, 0, sizeof(gObjectEvents));
    gObjectEvents[OBJECT_EVENTS_COUNT - 1] = player;
    gObjectEvents[SAVED_OBJECT_EVENTS_COUNT + 3] = npc;
    save.mapView[0] = 0xa55a;
    SaveObjectEvents();
    assert(save.mapView[0] == 0xa55a);
    assert(save.objectEvents[0].isPlayer);
    assert(save.objectEvents[1].scriptState == npc.scriptState);
    memset(gObjectEvents, 0x55, sizeof(gObjectEvents));
    LoadObjectEvents();
    assert(gObjectEvents[0].isPlayer);
    for (unsigned i = SAVED_OBJECT_EVENTS_COUNT; i < OBJECT_EVENTS_COUNT; i++)
        assert(!gObjectEvents[i].active);
''')

    def test_transients_filtered_by_identity_in_low_and_high_slots(self):
        self.compile_and_run(r'''
    /* No bridge ownership record: both a follower and an orphaned remote. */
    memset(&sWorld.remotes, 0, sizeof(sWorld.remotes));
    sWorld.enabled = FALSE;
    gObjectEvents[2].localId = 200;
    gObjectEvents[OBJECT_EVENTS_COUNT - 1] = gObjectEvents[2];
    gObjectEvents[OBJECT_EVENTS_COUNT - 1].localId = WB_LOCALID;
    SaveObjectEvents();
    for (unsigned i = 0; i < SAVED_OBJECT_EVENTS_COUNT; i++)
        assert(!save.objectEvents[i].active || save.objectEvents[i].isPlayer
               || save.objectEvents[i].localId == 1);
    assert(gObjectEvents[2].active); /* Filtering does not compact the live pool. */
''')

    def test_full_campaign_snapshot_reserves_player_and_bounds_destination(self):
        self.compile_and_run(r'''
    struct ObjectEvent player = gObjectEvents[0];
    for (unsigned i = 0; i < OBJECT_EVENTS_COUNT; i++)
        gObjectEvents[i] = (struct ObjectEvent){1, 0, 1, 0, 9, 1, 0, (int)i};
    gObjectEvents[OBJECT_EVENTS_COUNT - 1] = player;
    save.mapView[0] = 0xbeef;
    SaveObjectEvents();
    assert(save.objectEvents[0].isPlayer);
    assert(save.mapView[0] == 0xbeef);
    for (unsigned i = 0; i < SAVED_OBJECT_EVENTS_COUNT; i++)
        assert(save.objectEvents[i].active);
''')

    def test_save_array_and_oam_contract_are_explicit(self):
        global_h = (ROOT / 'include/global.h').read_text()
        self.assertIn('objectEvents[SAVED_OBJECT_EVENTS_COUNT]', global_h)
        sprite = (ROOT / 'src/sprite.c').read_text()
        self.assertIn('gOamLimit = MAX_SPRITES;', sprite)
        self.assertIn('NativeSpritesFitOamBuffer', sprite)
        movement = (ROOT / 'src/script_movement.c').read_text()
        self.assertIn('sMovementObjectIds[OBJECT_EVENTS_COUNT]', movement)
        self.assertIn('sMovementFinished[OBJECT_EVENTS_COUNT]', movement)


if __name__ == '__main__':
    unittest.main()
