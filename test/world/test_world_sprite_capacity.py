"""Production sprite slot and copy-queue functions with disposable stubs."""
from pathlib import Path
import subprocess,tempfile,unittest
from test_save_isolation import function
ROOT=Path(__file__).resolve().parents[2]
PREAMBLE=r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
typedef uint8_t u8; typedef uint16_t u16; typedef int16_t s16;
typedef int bool8;
#define FALSE 0
#define TRUE 1
#define MAX_SPRITES TEST_MAX_SPRITES
#define MAX_SPRITE_COPY_REQUESTS MAX_SPRITES
#define OAM_ENTRY_COUNT 128
#define OAM_SLOT(i) (&gMain.oamBuffer[i])
struct Sprite {int inUse,invisible,oam,subspriteMode;void *subspriteTables;}; struct SpriteTemplate {int value;};
extern int gOamLimit;
struct {int oamBuffer[128]; int sentinel;} gMain;
int gDummyOamData=-1; u8 sSpriteOrder[MAX_SPRITES];
#define SUBSPRITES_OFF 0
int AddSubspritesToOamBuffer(struct Sprite *sprite,int *dest,u8 *index){(void)sprite;(void)dest;(void)index;return 0;}
struct SpriteCopyRequest {const u8 *src;u8 *dest;u16 size;};
struct Sprite gSprites[MAX_SPRITES+1];
struct SpriteCopyRequest sSpriteCopyRequests[MAX_SPRITES];
int sShouldProcessSpriteCopyRequests,sSpriteCopyRequestCount;
int gOamLimit,gReservedSpriteTileCount,gSpriteCoordOffsetX,gSpriteCoordOffsetY;
void ResetOamRange(int a,int b) {(void)a;(void)b;}
void ResetAllSprites(void){memset(gSprites,0,sizeof(gSprites));}
void ResetAffineAnimData(void){} void FreeSpriteTileRanges(void){} void AllocSpriteTiles(int x){(void)x;}
u8 CreateSpriteAt(u8 i,const struct SpriteTemplate *t,s16 x,s16 y,u8 priority){(void)t;(void)x;(void)y;(void)priority;gSprites[i].inUse=1;return i;}
void ClearSpriteCopyRequests(void);
'''
MAIN=r'''
int main(void){
 struct SpriteTemplate t={0}; u8 data=1, dest=0;
 ResetSpriteData();
#if defined(PORTABLE) && WORLD_EXTENDED_SPRITES
 assert(MAX_SPRITES==96 && gOamLimit==128);
#else
 assert(MAX_SPRITES==64 && gOamLimit==64);
#endif
 for(int i=0;i<MAX_SPRITES;i++)assert(CreateSprite(&t,0,0,0)==i);
 assert(CreateSprite(&t,0,0,0)==MAX_SPRITES);
 for(int i=0;i<MAX_SPRITES;i++){sSpriteOrder[i]=i;gSprites[i].oam=7;}
 gMain.sentinel=0x123456;AddSpritesToOamBuffer();assert(gMain.sentinel==0x123456);
 for(int i=0;i<MAX_SPRITES;i++)assert(gMain.oamBuffer[i]==7);
 for(int i=MAX_SPRITES;i<gOamLimit;i++)assert(gMain.oamBuffer[i]==-1);
#if defined(PORTABLE) && WORLD_EXTENDED_SPRITES
 u8 boundary=127; assert(!AddSpriteToOamBuffer(&gSprites[0],&boundary));assert(boundary==128);
 assert(AddSpriteToOamBuffer(&gSprites[0],&boundary));assert(gMain.sentinel==0x123456);
#endif
 memset(gSprites,0,sizeof(gSprites));assert(CreateSpriteAtEnd(&t,0,0,0)==MAX_SPRITES-1);
 for(int i=0;i<MAX_SPRITES;i++)RequestSpriteCopy(&data,&dest,1);
 assert(sSpriteCopyRequestCount==MAX_SPRITES);RequestSpriteCopy(&data,&dest,1);
 assert(sSpriteCopyRequestCount==MAX_SPRITES);ClearSpriteCopyRequests();assert(!sSpriteCopyRequestCount);
 return 0;
}
'''
class SpriteCapacity(unittest.TestCase):
 def test_real_slot_copy_queue_and_oam_initialization(self):
  src=(ROOT/'src/sprite.c').read_text()
  code=PREAMBLE+''.join(function(src,n) for n in ('ClearSpriteCopyRequests','ResetSpriteData','CreateSprite','CreateSpriteAtEnd','AddSpriteToOamBuffer','AddSpritesToOamBuffer','RequestSpriteCopy'))+MAIN
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'t.c').write_text(code)
   for flags in (['-DPORTABLE','-DWORLD_EXTENDED_SPRITES=1','-DTEST_MAX_SPRITES=96'],['-DPORTABLE','-DWORLD_EXTENDED_SPRITES=0','-DTEST_MAX_SPRITES=64'],['-DWORLD_EXTENDED_SPRITES=1','-DTEST_MAX_SPRITES=64'],['-DTEST_MAX_SPRITES=64']):
    subprocess.run(['cc','-std=c99','-Wall','-Werror',*flags,str(p/'t.c'),'-o',str(p/'t')],check=True)
    subprocess.run([str(p/'t')],check=True)
 def test_real_header_and_oam_bounds(self):
  code = r"""
#include "global.h"
#include "main.h"
#include "sprite.h"
_Static_assert(sizeof(gMain.oamBuffer) / sizeof(gMain.oamBuffer[0]) == 128, "oam bounds");
_Static_assert(MAX_SPRITES == EXPECT_SPRITES, "sprite capacity");
int main(void) {return 0;}
"""
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'test.c';path.write_text(code)
   for enabled,expected in ((0,64),(1,96)):
    subprocess.run(['cc','-std=gnu11','-fsyntax-only','-iquote',str(ROOT/'include'),'-iquote',str(ROOT),'-DPORTABLE','-DNONMATCHING','-DUBFIX','-DWORLD_EXTENDED_SPRITES='+str(enabled),'-DEXPECT_SPRITES='+str(expected),str(path)],check=True)
 def test_header_and_build_expose_separate_opt_in(self):
  header=(ROOT/'include/sprite.h').read_text();make=(ROOT/'Makefile').read_text()
  self.assertIn('#define MAX_SPRITES 96',header);self.assertIn('WORLD_EXTENDED_SPRITES ?= 0',make)
  self.assertGreaterEqual(make.count('-DWORLD_EXTENDED_SPRITES=$(WORLD_EXTENDED_SPRITES)'),2)

if __name__=='__main__':unittest.main()
