"""Execute actual intro selection and link-wild loader, no full build/game."""
from pathlib import Path
import sys
import tempfile
import subprocess
import unittest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'test/world'))
from test_save_isolation import function

class CoopIntroRegressions(unittest.TestCase):
    def run_c(self, code):
        with tempfile.TemporaryDirectory(prefix='coop-intro-regression-') as directory:
            path = Path(directory)
            (path/'test.c').write_text(code)
            built = subprocess.run(['cc','-std=gnu99','-Wall','-Wextra','-Werror','-Wno-unused-function','-g','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-pie','-no-pie',str(path/'test.c'),'-o',str(path/'test')], capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stderr)
            ran = subprocess.run([str(path/'test')],capture_output=True,text=True)
            self.assertEqual(ran.returncode, 0, ran.stderr)

    def test_shared_wild_never_schedules_pvp_vs_letter_animation(self):
        code = r'''
#include <assert.h>
#include <stdint.h>
#define PORTABLE 1
#define BATTLE_TYPE_INGAME_PARTNER 0x400000
#define BATTLE_TYPE_LINK 2
#define BATTLE_TYPE_FRONTIER 0x80
#define BATTLE_TYPE_KYOGRE_GROUDON 0x100
#define TRAINER_STEVEN_PARTNER 1
#define VERSION_RUBY 1
#define BATTLE_ENVIRONMENT_UNDERWATER 3
#define tState data[0]
#define tEnvironment data[1]
typedef uint8_t u8;
typedef uint16_t u16;
static unsigned gBattleTypeFlags, gPartnerTrainerId, gGameVersion;
static int coop;
static int WorldCoop_IsBattle(void) {return coop;}
static struct {int data[16];} gTasks[1];
static void BattleIntroSlidePartner(u8 t) {(void)t;}
static void BattleIntroSlideLink(u8 t);
static struct {struct {int objMode;} oam; void (*callback)(void *);} gSprites[64];
static struct {u8 linkBattleVsSpriteId_V, linkBattleVsSpriteId_S;} battleStruct, *gBattleStruct=&battleStruct;
static uint16_t gBattle_BG1_X, gBattle_BG2_X, gBattle_WIN0V;
static unsigned gIntroSlideFlags;
static struct {int state,srcBuffer;} gScanlineEffect;
static int gScanlineEffectRegBuffers[2][160];
#define DISPLAY_HEIGHT 160
#define DISPLAY_WIDTH 240
#define ST_OAM_OBJ_WINDOW 2
#define BG_SCREEN_ADDR(n) (n)
#define BG_SCREEN_SIZE 0
#define BG_ATTR_CHARBASEINDEX 0
#define REG_OFFSET_WININ 0
#define REG_OFFSET_WINOUT 0
#define REG_OFFSET_BG1CNT 0
#define REG_OFFSET_BG2CNT 0
#define WININ_WIN0_BG_ALL 0
#define WININ_WIN0_OBJ 0
#define WININ_WIN0_CLR 0
#define WINOUT_WINOBJ_BG_ALL 0
#define WINOUT_WINOBJ_OBJ 0
#define WINOUT_WINOBJ_CLR 0
#define WINOUT_WIN01_BG1 0
#define WINOUT_WIN01_BG2 0
#define BGCNT_PRIORITY(n) (n)
#define BGCNT_CHARBASE(n) (n)
#define BGCNT_16COLOR 0
#define BGCNT_SCREENBASE(n) (n)
#define BGCNT_TXT256x512 0
#define BGCNT_TXT512x256 0
static void CpuFill32(int v,void *p,int n) {(void)v;(void)p;(void)n;}
static void SetGpuReg(int r,int v) {(void)r;(void)v;}
static void SetBgAttribute(int b,int a,int v) {(void)b;(void)a;(void)v;}
static void SpriteCB_VsLetterInit(void *s) {(void)s;}
static void BattleIntroSlideEnd(u8 t) {(void)t;}
static void BattleIntroSlide3(u8 t) {(void)t;}
static void BattleIntroSlide2(u8 t) {(void)t;}
static void WildSlide(u8 t) {(void)t;}
static void (*sBattleIntroSlideFuncs[10])(u8) = {WildSlide,WildSlide,WildSlide,WildSlide,WildSlide,WildSlide,WildSlide,WildSlide,WildSlide,WildSlide};
static void (*selected)(u8);
static u8 CreateTask(void (*f)(u8), u8 p) {(void)p;selected=f;return 0;}
'''
        code += function((ROOT/'src/battle_intro.c').read_text(), 'BattleIntroSlideLink')
        code += function((ROOT/'src/battle_intro.c').read_text(), 'HandleIntroSlide')
        code += r'''
int main(void) {
    /* The shared entry never allocated V/S sprites. Their zero IDs alias
     * healthbox0. Scheduling the PvP slide corrupts that live healthbox. */
    coop=1; gBattleTypeFlags=BATTLE_TYPE_LINK;
    HandleIntroSlide(0);
    for (int frame=0;frame<33;frame++) selected(0);
    assert(gSprites[0].oam.objMode==0 && gSprites[0].callback==0);
    assert(selected == WildSlide);
    assert(gBattleTypeFlags == BATTLE_TYPE_LINK);
    /* Ordinary solo and PvP task selection must be exactly stock. */
    coop=0; HandleIntroSlide(0); assert(selected == BattleIntroSlideLink);
    gBattleTypeFlags=0; HandleIntroSlide(0); assert(selected == WildSlide);
    gBattleTypeFlags=BATTLE_TYPE_FRONTIER; HandleIntroSlide(0); assert(selected == BattleIntroSlide3);
    return 0;
}
'''
        self.run_c(code)

    def test_shared_wild_slave_loader_records_actual_sprite_species(self):
        code = r'''
#include <assert.h>
#include <stdint.h>
#define PORTABLE 1
#define DISPLAY_WIDTH 240
#define MON_DATA_SPECIES 1
#define BATTLER_COORD_X_2 2
typedef uint8_t u8;
typedef uint16_t u16;
static int coop;
static int WorldCoop_IsBattle(void) {return coop;}
static struct Pokemon {u16 species;} gEnemyParty[6]={{286}};
static u8 gActiveBattler=1, gBattlerPartyIndexes[4], gBattlerSpriteIds[4], gBattleMonForms[4];
static int gMultiuseSpriteTemplate;
static struct Sprite {int x2, data[8]; int sDontFlip; void (*callback)(struct Sprite *); struct {int paletteNum;} oam;} gSprites[64];
#define TRUE 1
#define FALSE 0
#define ARRAY_COUNT(a) (sizeof(a)/sizeof((a)[0]))
#define tState data[0]
#define tAnimId data[3]
#define tBattlerId data[4]
#define tSpeciesId data[5]
typedef uint32_t u32;
static struct {int data[16]; union {struct Sprite *spritePtr;} ptr;} gTasks[1];
static int sIsSummaryAnim, taskDestroyed;
static void SpriteCallbackDummy(struct Sprite *s) {(void)s;}
static void AnimRunning(struct Sprite *s) {(void)s;}
static void (*sMonAnimFunctions[])(struct Sprite *)={AnimRunning};
static void DestroyTask(u8 t) {(void)t;taskDestroyed++;}
static struct {int active;} gPaletteFade;
static u16 consumedSpecies;
static void BattleAnimateFrontSprite(struct Sprite *s,u16 species,int noCry,u8 pan) {
    (void)noCry;(void)pan;consumedSpecies=species;
    gTasks[0].ptr.spritePtr=s;
}
static void (*gBattlerControllerFuncs[4])(void);
static u16 GetMonData(struct Pokemon *m, int f) {(void)f;return m->species;}
static void BattleLoadOpponentMonSpriteGfx(struct Pokemon *m,u8 b) {(void)m;(void)b;}
static u8 GetBattlerPosition(u8 b) {return b;}
static void SetMultiuseSpriteTemplateToPokemon(u16 s,u8 b) {(void)s;(void)b;}
static int GetBattlerSpriteCoord(u8 b,int t) {(void)b;(void)t;return 200;}
static int GetBattlerSpriteDefault_Y(u8 b) {(void)b;return 52;}
static int GetBattlerSpriteSubpriority(u8 b) {(void)b;return 40;}
static u8 CreateSprite(int *t,int x,int y,int p) {(void)t;(void)x;(void)y;(void)p;return 7;}
static void StartSpriteAnim(struct Sprite *s,u8 a) {(void)s;(void)a;}
static void SetBattlerShadowSpriteCallback(u8 b,u16 s) {(void)b;(void)s;}
static void TryShinyAnimAfterMonAnim(void) {}
'''
        code += function((ROOT/'src/battle_controller_link_opponent.c').read_text(), 'LinkOpponentHandleLoadMonSprite')
        code += '#define sSpeciesId data[2]\n'
        code += function((ROOT/'src/battle_main.c').read_text(), 'SpriteCB_WildMonAnimate')
        code += '#undef sSpeciesId\n'
        code += function((ROOT/'src/pokemon_animation.c').read_text(), 'Task_HandleMonAnimation')
        code += r'''
int main(void) {
    coop=1; LinkOpponentHandleLoadMonSprite();
    assert(gSprites[7].data[0]==1);
    assert(gSprites[7].data[2]==286);
    assert(gSprites[7].x2 == -DISPLAY_WIDTH);
    assert(gBattlerControllerFuncs[1] == TryShinyAnimAfterMonAnim);
    /* The real wild reveal callback consumes species before the front task
     * borrows data[] as scratch, then the real task restores the marker. */
    SpriteCB_WildMonAnimate(&gSprites[7]);
    assert(consumedSpecies==286);
    Task_HandleMonAnimation(0);
    assert(gSprites[7].callback==AnimRunning && gSprites[7].data[2]==0);
    assert(!taskDestroyed);
    gSprites[7].callback=SpriteCallbackDummy;
    Task_HandleMonAnimation(0);
    assert(taskDestroyed==1 && gSprites[7].data[0]==1 && gSprites[7].data[2]==286);
    /* PvP frames retain the stock zero field. */
    coop=0; gSprites[7].data[2]=0; LinkOpponentHandleLoadMonSprite();
    assert(gSprites[7].data[2]==0);
    return 0;
}
'''
        self.run_c(code)

if __name__ == '__main__':
    unittest.main()
