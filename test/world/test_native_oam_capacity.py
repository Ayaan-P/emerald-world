"""Test production OAM allocation across the original hardware boundary.

This compiles engine code against disposable stubs, not a graphical client.
"""
from pathlib import Path
import subprocess,tempfile,unittest
from test_save_isolation import function
ROOT=Path(__file__).resolve().parents[2]
PREAMBLE=r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
typedef uint8_t u8;typedef int8_t s8;typedef uint16_t u16;typedef int16_t s16;typedef int32_t s32;typedef int bool8;
#define TRUE 1
#define FALSE 0
#define PORTABLE 1
#define WORLD_NATIVE_OAM 1
#define OAM_ENTRY_COUNT 192
#define MAX_SPRITES 127
#define ALIGNED(n) __attribute__((aligned(n)))
#define SUBSPRITES_OFF 0
#define SUBSPRITES_IGNORE_PRIORITY 2
struct OamData {int shape,size,x,y,tileNum,priority,matrixNum;};
struct Subsprite {int x,y,shape,size,tileOffset,priority;};
struct SubspriteTable {unsigned subspriteCount;const struct Subsprite *subsprites;};
struct Sprite {int inUse,invisible,subspriteMode,subspriteTableNum,centerToCornerVecX,centerToCornerVecY;struct OamData oam;const struct SubspriteTable *subspriteTables;};
struct {struct OamData oamBuffer[128];int sentinel;int oamLoadDisabled;} gMain;
struct OamData gDummyOamData={.shape=-1};
struct Sprite gSprites[MAX_SPRITES];u8 sSpriteOrder[MAX_SPRITES],gOamLimit=192;
struct {int width,height;} sOamDimensions[3][4];
ALIGNED(4) u8 OAM[OAM_ENTRY_COUNT*sizeof(struct OamData)+4];
#define CpuCopy32(src,dst,size) memcpy(dst,src,size)
bool8 AddSubspritesToOamBuffer(struct Sprite *,struct OamData *,u8 *);
'''
MAIN=r'''
int main(void){
 gMain.sentinel=0x123456;memset(OAM,0,sizeof(OAM));memset(OAM+OAM_ENTRY_COUNT*sizeof(struct OamData),0x5a,4);
 ResetOamRange(0,OAM_ENTRY_COUNT);
 for(int i=0;i<128;i++)assert(gMain.oamBuffer[i].shape==-1);
 for(int i=0;i<64;i++)assert(sNativeExtraOam[i].shape==-1);
 sNativeExtraOam[63].shape=3;ResetOamRange(0,128);assert(sNativeExtraOam[63].shape==-1);
 for(int i=0;i<MAX_SPRITES;i++){sSpriteOrder[i]=i;gSprites[i].inUse=1;gSprites[i].oam.shape=2;}
 static const struct Subsprite pieces[]={{0,0,1,0,0,0},{1,0,2,0,0,0},{2,0,3,0,0,0}};
 static const struct SubspriteTable table[]={{3,pieces}};
 gSprites[126].subspriteTables=table;gSprites[126].subspriteMode=1;
 AddSpritesToOamBuffer();
 assert(gMain.oamBuffer[126].shape==1);assert(gMain.oamBuffer[127].shape==2);
 assert(sNativeExtraOam[0].shape==3);assert(sNativeExtraOam[1].shape==-1);
 assert(gMain.sentinel==0x123456);
 u8 edge=191;assert(!AddSpriteToOamBuffer(&gSprites[0],&edge));assert(edge==192);
 assert(AddSpriteToOamBuffer(&gSprites[0],&edge));assert(gMain.sentinel==0x123456);
 LoadOam();struct OamData *output=(struct OamData*)OAM;
 assert(output[126].shape==1 && output[127].shape==2 && output[128].shape==3);
 for(int i=0;i<4;i++)assert(OAM[OAM_ENTRY_COUNT*sizeof(struct OamData)+i]==0x5a);
 gMain.oamLoadDisabled=1;sNativeExtraOam[0].shape=9;LoadOam();assert(output[128].shape==3);
 gMain.oamLoadDisabled=0;gOamLimit=128;AddSpritesToOamBuffer();LoadOam();
 assert(sNativeExtraOam[0].shape==-1 && output[128].shape==-1);
 return 0;
}
'''
class NativeOamCapacity(unittest.TestCase):
 def test_subsprites_cross_hardware_boundary_and_upload_is_bounded(self):
  src=(ROOT/'src/sprite.c').read_text()
  start=src.index('#if defined(PORTABLE) && WORLD_NATIVE_OAM\n// Keep gMain')
  end=src.index('\n\nEWRAM_DATA struct Sprite',start)
  oam_macro=src[start:end]
  funcs=''.join(function(src,n) for n in ('AddSpriteToOamBuffer','AddSubspritesToOamBuffer','AddSpritesToOamBuffer','ResetOamRange','LoadOam'))
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'t.c').write_text(PREAMBLE+oam_macro+"\n"+funcs+MAIN)
   subprocess.run(['cc','-std=gnu99','-Wall','-Werror',str(p/'t.c'),'-o',str(p/'t')],check=True)
   subprocess.run([str(p/'t')],check=True)
 def test_real_headers_keep_main_and_save_layout_identical(self):
  code=r'''
#include <stddef.h>
#include <stdio.h>
#include "global.h"
#include "main.h"
#include "sprite.h"
_Static_assert(sizeof(struct OamData)==8, "OAM entry size");
_Static_assert(sizeof(gMain.oamBuffer)==1024, "original main OAM buffer");
int main(void){printf("%zu %zu %zu %d %d %d\n",sizeof(struct Main),offsetof(struct Main,state),sizeof(struct SaveBlock1),MAX_SPRITES,OAM_ENTRY_COUNT,OAM_SIZE);return 0;}
'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'t.c').write_text(code);outputs=[]
   for enabled in (0,1):
    subprocess.run(['cc','-std=gnu11','-iquote',str(ROOT/'include'),'-iquote',str(ROOT),'-DPORTABLE','-DNONMATCHING','-DUBFIX','-DWORLD_EXTENDED_SPRITES=1','-DWORLD_NATIVE_OAM='+str(enabled),str(p/'t.c'),'-o',str(p/'t')],check=True)
    outputs.append(subprocess.check_output([str(p/'t')],text=True).split())
   self.assertEqual(outputs[0][:3],outputs[1][:3]);self.assertEqual(outputs[0][3:],['96','128','1024']);self.assertEqual(outputs[1][3:],['127','192','1536'])
 def test_nonportable_limits_remain_original_even_if_flag_is_set(self):
  code = """#include "global.h"\n#include "main.h"\n#include "sprite.h"\n_Static_assert(OAM_ENTRY_COUNT==128, "GBA OAM");\n_Static_assert(OAM_SIZE==0x400, "GBA size");\n_Static_assert(MAX_SPRITES==64, "GBA sprites");\n"""
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'t.c';p.write_text(code)
   subprocess.run(['cc','-std=gnu11','-fsyntax-only','-iquote',str(ROOT/'include'),'-iquote',str(ROOT),'-DMODERN=1','-DNONMATCHING','-DUBFIX','-DWORLD_EXTENDED_SPRITES=1','-DWORLD_NATIVE_OAM=1',str(p)],check=True)
 def test_renderer_and_build_use_opt_in_native_count(self):
  renderer=(ROOT/'src/platform/gba_easy_draw.c').read_text();make=(ROOT/'Makefile').read_text()
  self.assertIn('nativeCount = OAM_ENTRY_COUNT',renderer);self.assertIn('WORLD_NATIVE_OAM ?= 0',make)
  self.assertGreaterEqual(make.count('-DWORLD_NATIVE_OAM=$(WORLD_NATIVE_OAM)'),2)

 def test_actual_software_renderer_draws_extended_entry_and_keeps_priority(self):
  source=(ROOT/'src/platform/gba_easy_draw.c').read_text()
  preamble=r"""
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "gba/types.h"
#define DISPLAY_WIDTH 240
#define DISPLAY_HEIGHT 160
#define REG_DISPCNT 0x40
#define REG_BLDCNT 0
#define REG_WINOUT 0
#define BLDCNT_TGT1_OBJ 16
#define WINMASK_WINOUT 64
#define WINMASK_CLR 32
#define applySpriteVerticalMosaicEffect(x) (x)
#define applySpriteHorizontalMosaicEffect(x) (x)
unsigned char VRAM_[0x18000], test_palette[0x400];
#define PLTT test_palette
unsigned char OAM[192*sizeof(struct OamData)] __attribute__((aligned(4)));
struct scanlineData {uint16_t layers[4][DISPLAY_WIDTH],spriteLayers[4][DISPLAY_WIDTH],bgcnts[4],winMask[DISPLAY_WIDTH];char bgtoprio[4],prioritySortedBgs[4][4],prioritySortedBgsCount[4];};
const u8 spriteSizes[][2]={{8,16},{8,32},{16,32},{32,64}};
static bool alphaBlendSelectTargetB(struct scanlineData *s,uint16_t *c,char p,char q,int x,bool b){(void)s;(void)c;(void)p;(void)q;(void)x;(void)b;return false;}
static uint16_t alphaBlendColor(uint16_t a,uint16_t b){(void)b;return a;}
static uint16_t alphaBrightnessIncrease(uint16_t a){return a;}
static uint16_t alphaBrightnessDecrease(uint16_t a){return a;}
"""
  main=r"""
int main(void){
 struct scanlineData row={0};struct OamData *o=(struct OamData*)OAM;
 for(int i=0;i<192;i++)o[i].affineMode=2;
 memset(VRAM_+0x10000,0x11,32);((uint16_t*)(test_palette+0x200))[1]=0x001f;((uint16_t*)(test_palette+0x200))[17]=0x03e0;
 o[150].affineMode=0;o[150].x=10;o[150].y=0;
 DrawSprites(&row,0,false);
#if OAM_ENTRY_COUNT == 192
 assert(row.spriteLayers[0][10]==0x801f);
#else
 assert(row.spriteLayers[0][10]==0);
#endif
 o[5].affineMode=0;o[5].x=10;o[5].y=0;o[5].paletteNum=1;
 memset(&row,0,sizeof(row));DrawSprites(&row,0,false);assert(row.spriteLayers[0][10]==0x83e0);
 return 0;
}
"""
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'t.c').write_text(preamble+function(source,'DrawSprites')+main)
   for count in (128,192):
    subprocess.run(['cc','-std=gnu99','-Wall','-Werror','-Wno-type-limits','-DOAM_ENTRY_COUNT='+str(count),'-iquote',str(ROOT/'include'),str(p/'t.c'),'-o',str(p/'t')],check=True)
    subprocess.run([str(p/'t')],check=True)

if __name__=='__main__':unittest.main()
