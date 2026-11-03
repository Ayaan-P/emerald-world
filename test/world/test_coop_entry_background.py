"""Run the real entry loader against instrumented VRAM, without a game build."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from test_save_isolation import function

ROOT = Path(__file__).resolve().parents[2]


class CoopEntryBackground(unittest.TestCase):
    def test_shared_wild_does_not_seed_pvp_bg2_or_reserve_vs_obj_tiles(self):
        body = function((ROOT / 'src/battle_bg.c').read_text(), 'DrawBattleEntryBackground')
        # Asset addresses identify writes without needing to decompress game assets.
        assets = sorted(set(re.findall(r'\bg(?:Battle\w+|VsLettersGfx|MultiBattleIntroBg_\w+)\b', body)))
        assets = [a for a in assets if a not in ('gBattleTypeFlags', 'gBattleEnvironment', 'gBattle_BG1_Y', 'gBattle_BG2_Y')]
        constants = sorted(set(re.findall(r'\b(?:BATTLE_TYPE_|TRAINER_CLASS_|TRAINER_STEVEN_|MAP_BATTLE_SCENE_|BG_ATTR_|REG_OFFSET_|WININ_|WINOUT_)\w+', body)))
        code = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#define PORTABLE 1
typedef uint8_t u8;
static unsigned gBattleTypeFlags, gBattleEnvironment, gPartnerTrainerId, gTrainerBattleOpponent_A;
static unsigned gBattle_BG1_Y, gBattle_BG2_Y;
static int coop, sheets;
static int WorldCoop_IsBattle(void) {return coop;}
static unsigned char vram[0x20000];
#define BG_CHAR_ADDR(n) (vram+(n)*0x4000)
#define BG_SCREEN_ADDR(n) (vram+(n)*0x800)
#define OBJ_VRAM0 (vram+0x10000)
#define BG_PLTT_ID(n) (n)
#define PLTT_SIZE_4BPP 32
static struct {int trainerClass;} gTrainers[1];
static struct {const void *entryTileset, *entryTilemap;} sBattleEnvironmentTable[10];
static unsigned char wildTiles[1]={0x11}, wildMap[1]={0x22};
static int sVsLettersSpriteSheet;
static void LZDecompressVram(const void *src,void *dst) {memset(dst, *(const unsigned char *)src, 0x800);}
static void LoadCompressedPalette(const void *p,int o,int n) {(void)p;(void)o;(void)n;}
static void LoadCompressedSpriteSheetUsingHeap(void *p) {(void)p;sheets++;}
static void SetBgAttribute(int b,int a,int v) {(void)b;(void)a;(void)v;}
static void SetGpuReg(int r,int v) {(void)r;(void)v;}
static void CopyToBgTilemapBuffer(int b,const void *src,int o,int n) {(void)o;(void)n;memset(BG_SCREEN_ADDR(b==1?28:30),*(const unsigned char *)src,0x800);}
static void CopyBgTilemapBufferToVram(int b) {(void)b;}
static int GetCurrentMapBattleScene(void) {return 0;}
'''
        for i, name in enumerate(constants):
            # Distinct battle bits; the rest are merely call arguments here.
            value = (1 << i) if name.startswith('BATTLE_TYPE_') else 0
            code += f'#define {name} {value}u\n'
        for name in assets:
            code += f'static const unsigned char {name}[1]={{0x77}};\n'
        code += body
        code += r'''
int main(void) {
    sBattleEnvironmentTable[0].entryTileset=wildTiles;
    sBattleEnvironmentTable[0].entryTilemap=wildMap;
    for (int peer=0;peer<2;peer++) {
        memset(vram,0,sizeof(vram)); sheets=0;
        coop=1;gBattleTypeFlags=BATTLE_TYPE_LINK;
        gBattle_BG1_Y=gBattle_BG2_Y=0;
        DrawBattleEntryBackground();
        /* Wild slides retire screen28 only. Screen30 must never receive the
         * PvP frame, whose tiles would later be read from charbase0. */
        for (int i=0;i<0x800;i++) assert(BG_SCREEN_ADDR(30)[i]==0);
        assert(BG_CHAR_ADDR(1)[0]==wildTiles[0]);
        assert(BG_SCREEN_ADDR(28)[0]==wildMap[0]);
        assert(gBattle_BG1_Y==0 && gBattle_BG2_Y==0 && sheets==0);
        assert(OBJ_VRAM0[0]==0);
        assert(gBattleTypeFlags==BATTLE_TYPE_LINK);
    }
    /* PvP still owns both frame maps, V/S OBJ allocation and offsets. */
    coop=0;DrawBattleEntryBackground();
    assert(BG_SCREEN_ADDR(30)[0]==gBattleVSFrame_Tilemap[0]);
    assert(OBJ_VRAM0[0]==gVsLettersGfx[0]);
    assert(sheets==1 && gBattle_BG1_Y==0xFF5C && gBattle_BG2_Y==0xFF5C);
    /* Ordinary wild entry retains its existing environment assets. */
    memset(vram,0,sizeof(vram));gBattleTypeFlags=0;sheets=0;
    DrawBattleEntryBackground();
    assert(BG_CHAR_ADDR(1)[0]==wildTiles[0] && BG_SCREEN_ADDR(28)[0]==wildMap[0]);
    assert(BG_SCREEN_ADDR(30)[0]==0 && sheets==0);
    return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='coop-entry-bg-') as directory:
            c = Path(directory) / 'entry.c'
            binary = Path(directory) / 'entry'
            c.write_text(code)
            built = subprocess.run(['cc', '-std=gnu99', '-Wall', '-Wextra', '-Werror', '-Wno-unused-function', '-fsanitize=address,undefined', '-fno-pie', '-no-pie', str(c), '-o', str(binary)], capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stderr)
            ran = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(ran.returncode, 0, ran.stderr)


if __name__ == '__main__':
    unittest.main()
