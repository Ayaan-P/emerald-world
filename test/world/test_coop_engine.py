"""Focused native co-op seam regressions. No game/build launched."""
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]


class CoopEngineTests(unittest.TestCase):
    def test_core_exchange_private_projection_merge_and_rollback(self):
        with tempfile.TemporaryDirectory(prefix='emerald-coop-core-') as temp:
            exe = str(pathlib.Path(temp) / 'core')
            command = ['cc', '-std=gnu99', '-g', '-fsanitize=address,undefined',
                       '-fno-sanitize-recover=all', '-fno-omit-frame-pointer', '-fno-pie', '-no-pie',
                       '-DPORTABLE', '-DUBFIX', '-DVER_64BIT',
                       '-DNONMATCHING', '-DMODERN=1', '-iquote', 'include', '-iquote', '.',
                       'test/world/coop_engine_core.c', '-o', exe]
            compiled = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run([exe], cwd=temp, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('reward ownership passed', result.stdout)

    def test_absent_coop_enemy_never_requests_an_empty_battle_mon(self):
        source = (ROOT / 'src/battle_main.c').read_text()
        start = source.index('static void BattleIntroGetMonsData(void)\n{')
        body = source[start:source.index('\n}', start) + 2]
        code = r'''
#define COOP_TEST_CUSTOM_GETMON
#define main CoreMain
#include "test/world/coop_engine_core.c"
#undef main
u8 gBattleCommunication[8];
const u32 gBitTable[32] = {1,2,4,8};
static int requests;
static void BattleIntroPrepareBackgroundSlide(void) {}
void BtlController_EmitGetMonData(u8 id, u8 req, u8 mask) { requests++; }
''' + body + r'''
int main(void) {
 Reset(0, TRUE); Exchange(); WorldCoop_InitControllers();
 gBattleCommunication[1]=3;
 BattleIntroGetMonsData();
 assert(requests==0 && gBattleCommunication[MULTIUSE_STATE]==1);
 BattleIntroGetMonsData();
 assert(gBattleMainFunc==BattleIntroPrepareBackgroundSlide);
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp)
            (path / 'intro.c').write_text(code)
            result = subprocess.run(['cc', '-std=gnu99', '-DPORTABLE', '-DUBFIX',
                '-DVER_64BIT', '-DNONMATCHING', '-DMODERN=1', '-iquote', 'include',
                '-iquote', '.', str(path / 'intro.c'), '-o', str(path / 'intro')],
                cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(path / 'intro')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_private_party_merge_is_owned_and_precedes_rewards(self):
        path = ROOT / 'src/platform/world_coop.c'
        self.assertTrue(path.exists(), 'missing real co-op engine core')
        text = path.read_text()
        self.assertIn('sCoop.original', text)
        self.assertIn('sCoop.slots[i]', text)
        self.assertIn('WorldCoop_PreparePrivateRewards', text)
        self.assertNotIn('BATTLE_TYPE_BATTLE_TOWER', text)

    def test_native_two_peer_controllers_are_enabled_without_frontier_flag(self):
        text = (ROOT / 'src/battle_controllers.c').read_text()
        self.assertIn('WorldCoop_IsBattle()', text)
        self.assertIn('WorldCoop_InitControllers()', text)

    def test_private_exp_uses_native_script_and_evolution_pipeline(self):
        text = (ROOT / 'src/battle_main.c').read_text()
        self.assertIn('WorldCoop_BeginPrivateRewards', text)
        self.assertIn('sCoopExpScript', text)
        self.assertIn('WorldCoop_NextReward()', text)


if __name__ == '__main__':
    unittest.main()
