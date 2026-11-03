"""Compile the real native co-op entry callback and enforce scene setup order."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_save_isolation import function

ROOT = Path(__file__).resolve().parents[2]

class CoopStartupTests(unittest.TestCase):
    def test_waits_for_bg_dma_then_enables_windows_before_controllers(self):
        code = r'''
#include <assert.h>
#include <stddef.h>
#include <string.h>
#define MULTIUSE_STATE 0
#define SPRITES_INIT_STATE1 2
#define SPRITES_INIT_STATE2 3
#define BATTLE_TYPE_LINK_IN_BATTLE 16
static unsigned char gBattleCommunication[8], gEnigmaBerries[8];
static unsigned gBattleTypeFlags;
static struct {void (*callback1)(void);} gMain;
static void (*gPreBattleCallback1)(void);
static int busy=1, active=1, backgrounds, windows, controllers, sprites, aborts;
static void RunTasks(void) {}
static void AnimateSprites(void) {}
static void BuildOamBuffer(void) {}
static int NativeLink_IsActive(void) {return active;}
static void WorldCoop_Abort(void) {aborts++;}
static void FreeAllWindowBuffers(void) {}
static void FreeRestoreBattleData(void) {}
static void WorldActivity_ReturnToField(void) {}
static int IsDma3ManagerBusyWithBgCopy(void) {return busy;}
static void ShowBg(int bg) {assert(bg==backgrounds++);}
static void FillAroundBattleWindows(void) {assert(backgrounds==4);windows++;}
static void InitBattleControllers(void) {assert(windows==1);controllers++;}
static int BattleInitAllSprites(unsigned char *state, unsigned char *battler) {
    (void)state;(void)battler;assert(controllers==1);sprites++;return 1;
}
static void BattleMainCB1(void) {}
static void BattleMainCB2(void) {}
static void SetMainCallback2(void (*cb)(void)) {assert(cb==BattleMainCB2);}
'''
        code += function((ROOT / 'src/battle_main.c').read_text(), 'CB2_HandleStartCoopBattle')
        code += r'''
int main(void) {
    CB2_HandleStartCoopBattle();
    assert(!backgrounds && !windows && !controllers && !sprites);
    busy=0;
    CB2_HandleStartCoopBattle();
    assert(backgrounds==4 && windows==1 && controllers==1);
    /* Whether setup deliberately takes another frame is not material. */
    if (!sprites) CB2_HandleStartCoopBattle();
    assert(sprites==1 && gMain.callback1==BattleMainCB1);
    assert(gBattleTypeFlags & BATTLE_TYPE_LINK_IN_BATTLE);
    active=0;
    CB2_HandleStartCoopBattle();
    assert(aborts==1);
}
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'entry.c').write_text(code)
            result = subprocess.run(['cc', '-std=gnu99', '-Wall', '-Wextra', str(path / 'entry.c'), '-o', str(path / 'entry')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(path / 'entry')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

if __name__ == '__main__':
    unittest.main()
