"""Exercise the real sprite initializer without constructing absent-mon HP bars."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_save_isolation import function

ROOT = Path(__file__).resolve().parents[2]


class CoopSpriteInitialization(unittest.TestCase):
    def test_absent_coop_battler_never_initializes_an_empty_hp_bar(self):
        source = r'''
#include <assert.h>
typedef unsigned char u8;
typedef unsigned char bool8;
#define PORTABLE 1
#define TRUE 1
#define FALSE 0
#define BATTLE_TYPE_SAFARI 128
#define B_POSITION_OPPONENT_LEFT 1
#define B_SIDE_PLAYER 0
#define HEALTHBOX_ALL 0
static unsigned gBattleTypeFlags;
static u8 gHealthboxSpriteIds[4] = {0,1,2,3};
static u8 gBattlerPositions[4] = {0,1,2,3};
static u8 gBattlerPartyIndexes[4] = {0,0,3,3};
static u8 gBattlersCount = 4, gAbsentBattlerFlags = 8;
static int coop = 1, updates, hidden;
struct Pokemon {unsigned maxHP;};
static struct Pokemon gPlayerParty[6] = {{20},{20},{20},{20},{20},{20}};
static struct Pokemon gEnemyParty[6] = {{13},{0},{0},{0},{0},{0}};
static int WorldCoop_IsBattle(void) {return coop;}
static void ClearSpritesBattlerHealthboxAnimData(void) {}
static bool8 BattleLoadAllHealthBoxesGfx(u8 b) {(void)b;return TRUE;}
static u8 CreateSafariPlayerHealthboxSprites(void) {return 0;}
static u8 CreateBattlerHealthboxSprites(u8 b) {return b;}
static void InitBattlerHealthboxCoords(u8 b) {(void)b;}
static void DummyBattleInterfaceFunc(u8 b, bool8 v) {(void)b;(void)v;}
static u8 GetBattlerSide(u8 b) {return b & 1;}
static void UpdateHealthboxAttribute(u8 sprite, struct Pokemon *mon, u8 kind) {
    (void)sprite;(void)kind;
    assert(mon->maxHP != 0); /* Actual HP bar divides by this denominator. */
    updates++;
}
static void SetHealthboxSpriteInvisible(u8 sprite) {(void)sprite;hidden++;}
static void LoadAndCreateEnemyShadowSprites(void) {}
static void BufferBattlePartyCurrentOrder(void) {}
'''
        source += function((ROOT / 'src/battle_gfx_sfx_util.c').read_text(), 'BattleInitAllSprites')
        source += r'''
int main(void) {
    u8 state = 5, battler = 3;
    BattleInitAllSprites(&state, &battler);
    assert(updates == 0 && hidden == 1 && state == 6 && battler == 0);
    state=5; battler=0;
    BattleInitAllSprites(&state,&battler);
    assert(updates == 1 && hidden == 2 && state == 5 && battler == 1);
    state=5; battler=3; coop=0; gEnemyParty[3].maxHP=10;
    BattleInitAllSprites(&state,&battler);
    assert(updates == 2 && hidden == 3 && state == 6 && battler == 0);
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            c = Path(directory) / 'sprites.c'
            binary = Path(directory) / 'sprites'
            c.write_text(source)
            built = subprocess.run(['cc', '-std=gnu99', '-Wall', '-Wextra', str(c), '-o', str(binary)], capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stderr)
            ran = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(ran.returncode, 0, ran.stderr)


if __name__ == '__main__':
    unittest.main()
