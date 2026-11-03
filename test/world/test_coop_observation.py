"""Authenticated public-mon projection, independent of the slave combat engine."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]

class CoopObservationTests(unittest.TestCase):
    def test_public_projection_is_current_slot_scoped_and_never_contains_enemy_hp(self):
        code = r'''
#define main CoreMain
#include "test/world/coop_engine_core.c"
#undef main
int main(void) {
    struct WorldCoopPublicMon view;
    struct BattlePokemon mon = {0};
    u8 hp[] = {CONTROLLER_SETMONDATA, REQUEST_HP_BATTLE, 0, 7, 0};
    u8 status[] = {CONTROLLER_SETMONDATA, REQUEST_STATUS_BATTLE, 0, 8, 0, 0, 0};
    Reset(1, FALSE); Exchange(); WorldCoop_InitControllers();
    assert(!WorldCoop_GetPublicMon(0, &view));
    mon.species=255; mon.level=5; mon.hp=20; mon.maxHP=22; mon.status1=0;
    WorldCoop_ObserveMonData(0, 0, &mon);
    assert(WorldCoop_GetPublicMon(0, &view));
    assert(view.species==255 && view.level==5 && view.hp==20 && view.maxHP==22);
    /* The slave engine remains uninitialized. No observer mutates it. */
    assert(gBattleMons[0].species==0);
    WorldCoop_ObserveController(0, hp);
    WorldCoop_ObserveController(0, status);
    assert(WorldCoop_GetPublicMon(0, &view) && view.hp==7 && view.status==8);
    /* Reserve updates never overwrite the visible active slot. */
    hp[2]=2; hp[3]=1;
    WorldCoop_ObserveController(0, hp);
    assert(WorldCoop_GetPublicMon(0, &view) && view.hp==7);
    gBattlerPartyIndexes[0]=1;
    assert(!WorldCoop_GetPublicMon(0, &view));
    WorldCoop_ObserveMonData(0, 1, &mon);
    assert(WorldCoop_GetPublicMon(0, &view) && view.hp==20);
    /* Cross-owner slots, absent battlers and inactive generations fail closed. */
    WorldCoop_ObserveMonData(2, 0, &mon);
    assert(!WorldCoop_GetPublicMon(2, &view));
    WorldCoop_ObserveMonData(3, 3, &mon);
    assert(!WorldCoop_GetPublicMon(3, &view));
    mon.species=265; mon.hp=11; mon.maxHP=13; mon.status1=0x123;
    WorldCoop_ObserveMonData(1, 0, &mon);
    assert(WorldCoop_GetPublicMon(1, &view));
    assert(view.species==265 && view.level==5 && !view.hp && !view.maxHP && !view.status);
    hp[2]=0;
    WorldCoop_ObserveController(1, hp);
    assert(WorldCoop_GetPublicMon(1, &view) && !view.hp);
    testGeneration++;
    assert(!WorldCoop_GetPublicMon(0, &view));
    testGeneration--;
    WorldCoop_Abort();
    assert(!WorldCoop_GetPublicMon(0, &view));
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            (path / 'observe.c').write_text(code)
            result = subprocess.run(['cc', '-std=gnu99', '-g', '-fsanitize=address,undefined',
                '-fno-sanitize-recover=all', '-fno-pie', '-no-pie', '-DPORTABLE', '-DUBFIX',
                '-DVER_64BIT', '-DNONMATCHING', '-DMODERN=1', '-iquote', 'include', '-iquote', '.',
                str(path / 'observe.c'), '-o', str(path / 'observe')], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(path / 'observe')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

if __name__ == '__main__':
    unittest.main()
