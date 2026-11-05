"""Experimental native extra sprite tile bank component tests."""
from pathlib import Path
import subprocess,tempfile,unittest
from test_save_isolation import function
ROOT=Path(__file__).resolve().parents[2]

PRE=r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
typedef uint8_t u8;typedef uint16_t u16;typedef int16_t s16;typedef int bool8;
#define TRUE 1
#define FALSE 0
#define PORTABLE 1
#define WORLD_NATIVE_TILEBANK 1
#define MAX_SPRITES 127
#define OAM_ENTRY_COUNT 192
#define SUBSPRITES_OFF 0
struct OamData {int tileNum,affineParam,x,y,shape,size,paletteNum,affineMode;};
struct Sprite {int inUse,invisible,subspriteMode;void *subspriteTables;struct OamData oam;};
struct {struct OamData oamBuffer[128];int guard;} gMain;
struct OamData sNativeExtraOam[64],gDummyOamData;
#define OAM_SLOT(i) ((i)<128?&gMain.oamBuffer[(i)]:&sNativeExtraOam[(i)-128])
struct Sprite gSprites[MAX_SPRITES+1];u8 sSpriteOrder[MAX_SPRITES],gOamLimit=192;
int AddSubspritesToOamBuffer(struct Sprite *s,struct OamData *o,u8 *i){(void)s;(void)o;(void)i;return 0;}
'''
ALLOC_MAIN=r'''
int main(void){
 assert(NativeSpriteTileAllocate(&gSprites[0],16)==-1);
 NativeSpriteTileScope(TRUE);
 assert(NativeSpriteTileAllocate(&gSprites[0],16)==1024);
 assert(NativeSpriteTileAllocate(&gSprites[1],16)==1040);
 assert(NativeSpriteTileNumber(&gSprites[0])==1024);
 NativeSpriteTileClone(&gSprites[0],&gSprites[2]);assert(NativeSpriteTileNumber(&gSprites[2])==1024);
 NativeSpriteTileRelease(&gSprites[0]);assert(sNativeTileUsed[0]);
 assert(NativeSpriteTileAllocate(&gSprites[3],16)==1056);
 NativeSpriteTileRelease(&gSprites[2]);assert(!sNativeTileUsed[0]);
 assert(NativeSpriteTileAllocate(&gSprites[5],16)==1024);
 assert(NativeSpriteTileAllocate(&gSprites[4],0)==-1);
 assert(NativeSpriteTileAllocate(&gSprites[4],1025)==-1);
 NativeSpriteTileRelease(&gSprites[1]);NativeSpriteTileRelease(&gSprites[3]);NativeSpriteTileRelease(&gSprites[5]);
 assert(NativeSpriteTileAllocate(&gSprites[6],1024)==1024);
 assert(NativeSpriteTileAllocate(&gSprites[7],1)==-1);
 NativeSpriteTileClone(&gSprites[6],&gSprites[8]);NativeSpriteTileClone(&gSprites[8],&gSprites[9]);
 NativeSpriteTileRelease(&gSprites[6]);NativeSpriteTileRelease(&gSprites[8]);assert(sNativeTileUsed[0]);
 NativeSpriteTileRelease(&gSprites[9]);assert(!sNativeTileUsed[0]);
 assert(NativeSpriteTileAllocate(&gSprites[7],1)==1024);
 NativeSpriteTileScope(FALSE);assert(NativeSpriteTileAllocate(&gSprites[4],1)==-1);
 return 0;
}
'''
OAM_MAIN=r'''
int main(void){
 gMain.guard=0x123456;
 for(int i=0;i<MAX_SPRITES;i++)sSpriteOrder[i]=i;
 gSprites[0].inUse=1;gSprites[0].oam.tileNum=4;
 NativeSpriteTileScope(TRUE);assert(NativeSpriteTileAllocate(&gSprites[1],8)==1024);
 gSprites[1].inUse=1;gSprites[1].oam.tileNum=0;
 AddSpritesToOamBuffer();
 assert(gMain.oamBuffer[0].tileNum==4 && gMain.guard==0x123456);
 assert(sNativeExtraOam[0].tileNum==0 && sNativeExtraOam[0].affineParam==0x8001);
 assert(sNativeExtraOam[1].affineParam==0);
 assert(sNativeExtraOam[63].affineParam==0x4101);
 assert(gOamLimit==192);
 return 0;
}
'''
RENDER_PRE=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "gba/types.h"
#define DISPLAY_WIDTH 240
#define DISPLAY_HEIGHT 160
#define OAM_ENTRY_COUNT 192
#define REG_DISPCNT 0x40
#define REG_BLDCNT 0
#define REG_WINOUT 0
#define BLDCNT_TGT1_OBJ 16
#define WINMASK_WINOUT 64
#define WINMASK_CLR 32
#define applySpriteVerticalMosaicEffect(x) (x)
#define applySpriteHorizontalMosaicEffect(x) (x)
unsigned char VRAM_[0x20000], test_palette[0x400];
#define PLTT test_palette
unsigned char OAM[192*sizeof(struct OamData)] __attribute__((aligned(4)));
struct scanlineData {uint16_t layers[4][DISPLAY_WIDTH],spriteLayers[4][DISPLAY_WIDTH],bgcnts[4],winMask[DISPLAY_WIDTH];char bgtoprio[4],prioritySortedBgs[4][4],prioritySortedBgsCount[4];};
const u8 spriteSizes[][2]={{8,16},{8,32},{16,32},{32,64}};
static bool alphaBlendSelectTargetB(struct scanlineData *s,uint16_t *c,char p,char q,int x,bool b){(void)s;(void)c;(void)p;(void)q;(void)x;(void)b;return false;}
static uint16_t alphaBlendColor(uint16_t a,uint16_t b){(void)b;return a;}
static uint16_t alphaBrightnessIncrease(uint16_t a){return a;}
static uint16_t alphaBrightnessDecrease(uint16_t a){return a;}
'''
RENDER_MAIN=r'''
int main(void){
 struct scanlineData row={0};struct OamData *o=(struct OamData*)OAM;
 for(int i=0;i<192;i++)o[i].affineMode=2;
 memset(VRAM_+0x10000,0x11,32);memset(VRAM_+0x18000,0x22,32);
 ((uint16_t*)(test_palette+0x200))[1]=0x001f;((uint16_t*)(test_palette+0x200))[2]=0x03e0;
 o[150].affineMode=0;o[150].x=10;o[150].affineParam=0x8001;
 DrawSprites(&row,0,false);
#if WORLD_NATIVE_TILEBANK
 assert(row.spriteLayers[0][10]==0x83e0);
#else
 assert(row.spriteLayers[0][10]==0x801f);
#endif
 o[150].affineParam=0;memset(&row,0,sizeof(row));DrawSprites(&row,0,false);assert(row.spriteLayers[0][10]==0x801f);
 o[150].affineMode=2;o[5].affineMode=0;o[5].x=10;o[5].affineParam=0x8001;
 memset(&row,0,sizeof(row));DrawSprites(&row,0,false);assert(row.spriteLayers[0][10]==0x801f);
 return 0;
}
'''
class NativeTileBank(unittest.TestCase):
 def compile_run(self,code,flags=()):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'t.c').write_text(code)
   subprocess.run(['cc','-std=gnu99','-Wall','-Werror','-Wno-type-limits','-Wno-unused-function','-iquote',str(ROOT/'include'),*flags,str(p/'t.c'),'-o',str(p/'t')],check=True)
   subprocess.run([str(p/'t')],check=True)
 def helpers(self):
  src=(ROOT/'src/sprite.c').read_text();start=src.index('#if defined(PORTABLE) && WORLD_NATIVE_TILEBANK\n#define NATIVE_TILE_BASE');end=src.index('\nEWRAM_DATA static u16 sSpritePriorities',start)
  return src,src[start:end]+'\n'
 def test_real_extra_allocator_scope_clone_and_release(self):
  src,helpers=self.helpers();self.compile_run(PRE+helpers+ALLOC_MAIN)
 def test_real_oam_emitter_places_marked_extra_sprite_after_stock_slots(self):
  src,helpers=self.helpers()
  functions=''.join(function(src,n) for n in ('AddSpriteToOamBuffer','AddSpritesToOamBuffer'))
  self.compile_run(PRE+helpers+functions+OAM_MAIN)
 def test_actual_renderer_uses_extra_bank_only_for_marked_native_oam(self):
  src=(ROOT/'src/platform/gba_easy_draw.c').read_text();code=RENDER_PRE+function(src,'NativeTileBankOamOrder')+function(src,'DrawSprites')+RENDER_MAIN
  for gate in (0,1):self.compile_run(code,['-DWORLD_NATIVE_TILEBANK='+str(gate)])
 def test_animation_copy_paths_use_full_tile_number(self):
  src=(ROOT/'src/sprite.c').read_text();self.assertEqual(src.count('RequestSpriteFrameImageCopy(imageValue, SPRITE_TILE_NUMBER(sprite), sprite->images)'),3)
 def test_real_vram_header_limits_and_invalid_combinations(self):
  code='#include "global.h"\n_Static_assert(VRAM_SIZE==EXPECTED_VRAM,"vram");\n_Static_assert(OBJ_VRAM0_SIZE==EXPECTED_OBJ,"obj");\n'
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'t.c';p.write_text(code)
   base=['cc','-std=gnu11','-fsyntax-only','-iquote',str(ROOT/'include'),'-iquote',str(ROOT),'-DPORTABLE','-DNONMATCHING','-DUBFIX','-DMODERN=1']
   for flags in (['-DWORLD_NATIVE_TILEBANK=0','-DEXPECTED_VRAM=0x18000','-DEXPECTED_OBJ=0x8000'],['-DWORLD_NATIVE_TILEBANK=1','-DWORLD_NATIVE_OAM=1','-DWORLD_EXTENDED_OBJECTS=1','-DEXPECTED_VRAM=0x20000','-DEXPECTED_OBJ=0x10000']):
    subprocess.run(base+flags+[str(p)],check=True)
   bad=subprocess.run(base+['-DWORLD_NATIVE_TILEBANK=1','-DWORLD_NATIVE_OAM=0','-DWORLD_EXTENDED_OBJECTS=1','-DEXPECTED_VRAM=0','-DEXPECTED_OBJ=0',str(p)],capture_output=True)
   self.assertNotEqual(bad.returncode,0)

 def test_real_sprite_creation_animation_and_refcounted_clone(self):
  src,helpers=self.helpers()
  pre=r"""
#include <assert.h>
#include <string.h>
#include "global.h"
#include "sprite.h"
#define NATIVE_TILE_BASE 1024
#define MAX_SPRITE_COPY_REQUESTS MAX_SPRITES
struct Sprite gSprites[MAX_SPRITES+1];
unsigned char VRAM_[VRAM_SIZE] __attribute__((aligned(4)));
static const struct Sprite sDummySprite={0};
struct SpriteCopyRequest {const u8 *src;u8 *dest;u16 size;};
static struct SpriteCopyRequest sSpriteCopyRequests[MAX_SPRITES];static u8 sSpriteCopyRequestCount;
static int stock_frees;
#define FREE_SPRITE_TILE(n) do {(void)(n);stock_frees++;} while (0)
static s16 AllocSpriteTiles(u16 count){(void)count;return 5;}
static void ResetSprite(struct Sprite *);
static void RequestSpriteFrameImageCopy(u16,u16,const struct SpriteFrameImage *);
static void SetSpriteOamFlipBits(struct Sprite *s,u8 h,u8 v){(void)s;(void)h;(void)v;}
void CalcCenterToCornerVec(struct Sprite *s,u8 a,u8 b,u8 c){(void)s;(void)a;(void)b;(void)c;}
u16 GetSpriteTileStartByTag(u16 tag){(void)tag;return 0;}
void SetSpriteSheetFrameTileNum(struct Sprite *s){(void)s;}
void InitSpriteAffineAnim(struct Sprite *s){(void)s;}
u8 IndexOfSpritePaletteTag(u16 tag){(void)tag;return 0;}
"""
  body=r"""
int main(void){
 static const u8 pixels[64]={[0]=0x5a};static const struct SpriteFrameImage images[]={{pixels,64}};
 static const struct OamData oam={0};static const union AnimCmd anim[]={{.frame={.imageValue=0,.duration=1}}};
 static const union AnimCmd *const anims[]={anim};
 static const struct SpriteTemplate t={.tileTag=TAG_NONE,.paletteTag=TAG_NONE,.oam=&oam,.anims=anims,.images=images};
 NativeSpriteTileScope(TRUE);assert(CreateSpriteAt(0,&t,0,0,0)==0);NativeSpriteTileScope(FALSE);
 assert(NativeSpriteTileNumber(&gSprites[0])==1024 && gSprites[0].oam.tileNum==0);
 BeginAnim(&gSprites[0]);assert(sSpriteCopyRequestCount==1);
 assert(sSpriteCopyRequests[0].dest==VRAM_+0x18000);
 memcpy(sSpriteCopyRequests[0].dest,sSpriteCopyRequests[0].src,sSpriteCopyRequests[0].size);
 assert(VRAM_[0x18000]==0x5a && VRAM_[0x10000]==0);
 u8 copy=CreateCopySpriteAt(&gSprites[0],0,0,0);assert(copy==MAX_SPRITES-1);gSprites[copy].usingSheet=TRUE;
 DestroySprite(&gSprites[0]);assert(sNativeTileUsed[0]);DestroySprite(&gSprites[copy]);assert(!sNativeTileUsed[0]);
 assert(CreateSpriteAt(1,&t,0,0,0)==1);assert(NativeSpriteTileNumber(&gSprites[1])==5);
 DestroySprite(&gSprites[1]);assert(stock_frees==2);return 0;
}
"""
  names=('ResetSprite','CreateSpriteAt','DestroySprite','RequestSpriteFrameImageCopy','BeginAnim')
  self.compile_run(pre+helpers+''.join(function(src,n) for n in names)+function((ROOT/'src/event_object_movement.c').read_text(),'CreateCopySpriteAt')+body,
   ['-DPORTABLE','-DNONMATCHING','-DUBFIX','-DMODERN=1','-DWORLD_EXTENDED_OBJECTS=1','-DWORLD_EXTENDED_SPRITES=1','-DWORLD_NATIVE_OAM=1','-DWORLD_NATIVE_TILEBANK=1','-iquote',str(ROOT)])

 def test_world_spawn_scopes_extra_allocation_even_on_failure(self):
  src,helpers=self.helpers()
  event=(ROOT/'src/event_object_movement.c').read_text()
  stub=r"""
#define WORLD_EXTENDED_OBJECTS 1
static bool8 sWorldObjectAllocation;
static u8 SpawnSpecialObjectEventParameterized(u8 g,u8 m,u8 l,s16 x,s16 y,u8 e){(void)g;(void)m;(void)l;(void)x;(void)y;(void)e;assert(sWorldObjectAllocation && sNativeTileScope);return 48;}
"""
  main=r"""
int main(void){assert(SpawnWorldObjectEventParameterized(7,0,160,1,1,1)==48);assert(!sWorldObjectAllocation && !sNativeTileScope);return 0;}
"""
  self.compile_run(PRE+helpers+stub+function(event,'SpawnWorldObjectEventParameterized')+main)

 def test_actual_renderer_preserves_priority_across_the_native_bank(self):
  src=(ROOT/'src/platform/gba_easy_draw.c').read_text()
  body=r"""
static void sentinel(struct OamData *o){
 o[191].x=511;o[191].y=255;o[191].shape=3;o[191].size=3;o[191].tileNum=1023;o[191].paletteNum=15;o[191].affineMode=2;o[191].affineParam=0x4101;
}
int main(void){
 struct scanlineData row={0};struct OamData *o=(struct OamData*)OAM;
 for(int i=0;i<192;i++)o[i].affineMode=2;
 memset(VRAM_+0x10000,0x11,32);memset(VRAM_+0x18000,0x22,32);
 ((uint16_t*)(test_palette+0x200))[1]=0x001f;((uint16_t*)(test_palette+0x200))[2]=0x03e0;
 o[0].affineMode=0;o[0].x=10;
 o[128].affineMode=0;o[128].x=10;o[128].affineParam=0x8000;sentinel(o);
 DrawSprites(&row,0,false);assert(row.spriteLayers[0][10]==0x83e0);
 o[128].affineParam=0x8001;memset(&row,0,sizeof(row));DrawSprites(&row,0,false);assert(row.spriteLayers[0][10]==0x801f);
 o[191].tileNum=0;memset(&row,0,sizeof(row));DrawSprites(&row,0,false);assert(row.spriteLayers[0][10]==0x801f);
 return 0;
}
"""
  self.compile_run(RENDER_PRE+function(src,'NativeTileBankOamOrder')+function(src,'DrawSprites')+body,['-DWORLD_NATIVE_TILEBANK=1'])

 def test_real_emitter_and_renderer_preserve_cross_bank_order(self):
  sprite,helpers=self.helpers();renderer=(ROOT/'src/platform/gba_easy_draw.c').read_text()
  pre=r"""
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "gba/types.h"
#define TRUE 1
#define FALSE 0
#define PORTABLE 1
#define WORLD_NATIVE_TILEBANK 1
#define MAX_SPRITES 127
#define OAM_ENTRY_COUNT 192
#define SUBSPRITES_OFF 0
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
struct Sprite {int inUse,invisible,subspriteMode;void *subspriteTables;struct OamData oam;};
struct {struct OamData oamBuffer[128];int guard;} gMain;
struct OamData sNativeExtraOam[64],gDummyOamData={.affineMode=2};
#define OAM_SLOT(i) ((i)<128?&gMain.oamBuffer[(i)]:&sNativeExtraOam[(i)-128])
struct Sprite gSprites[MAX_SPRITES+1];u8 sSpriteOrder[MAX_SPRITES],gOamLimit=192;
int AddSubspritesToOamBuffer(struct Sprite *s,struct OamData *o,u8 *i){(void)s;(void)o;(void)i;return 0;}
unsigned char VRAM_[0x20000], test_palette[0x400];
#define PLTT test_palette
unsigned char OAM[192*sizeof(struct OamData)] __attribute__((aligned(4)));
struct scanlineData {uint16_t layers[4][DISPLAY_WIDTH],spriteLayers[4][DISPLAY_WIDTH],bgcnts[4],winMask[DISPLAY_WIDTH];char bgtoprio[4],prioritySortedBgs[4][4],prioritySortedBgsCount[4];};
const u8 spriteSizes[][2]={{8,16},{8,32},{16,32},{32,64}};
static bool alphaBlendSelectTargetB(struct scanlineData *s,uint16_t *c,char p,char q,int x,bool b){(void)s;(void)c;(void)p;(void)q;(void)x;(void)b;return false;}
static uint16_t alphaBlendColor(uint16_t a,uint16_t b){(void)b;return a;}
static uint16_t alphaBrightnessIncrease(uint16_t a){return a;}
static uint16_t alphaBrightnessDecrease(uint16_t a){return a;}
"""
  body=r"""
static void upload(void){memcpy(OAM,gMain.oamBuffer,sizeof(gMain.oamBuffer));memcpy(OAM+sizeof(gMain.oamBuffer),sNativeExtraOam,sizeof(sNativeExtraOam));}
int main(void){
 struct scanlineData row={0};
 for(int i=0;i<MAX_SPRITES;i++)sSpriteOrder[i]=i;
 gSprites[0].inUse=1;gSprites[0].oam.x=10;
 NativeSpriteTileScope(TRUE);assert(NativeSpriteTileAllocate(&gSprites[1],1)==1024);NativeSpriteTileScope(FALSE);
 gSprites[1].inUse=1;gSprites[1].oam.x=10;
 memset(VRAM_+0x10000,0x11,32);memset(VRAM_+0x18000,0x22,32);
 ((uint16_t*)(test_palette+0x200))[1]=0x001f;((uint16_t*)(test_palette+0x200))[2]=0x03e0;
 AddSpritesToOamBuffer();upload();DrawSprites(&row,0,false);assert(row.spriteLayers[0][10]==0x801f);
 sSpriteOrder[0]=1;sSpriteOrder[1]=0;memset(&row,0,sizeof(row));
 AddSpritesToOamBuffer();upload();DrawSprites(&row,0,false);assert(row.spriteLayers[0][10]==0x83e0);
 return 0;
}
"""
  code=pre+helpers+''.join(function(sprite,n) for n in ('AddSpriteToOamBuffer','AddSpritesToOamBuffer'))+function(renderer,'NativeTileBankOamOrder')+function(renderer,'DrawSprites')+body
  self.compile_run(code)

 def test_native_order_merges_all_capacity_boundaries_and_fails_closed(self):
  src=(ROOT/'src/platform/gba_easy_draw.c').read_text()
  body=r"""
int main(void){
 struct OamData *o=(struct OamData*)OAM;u8 order[192];
 for(unsigned n=0;n<191;n++){
  unsigned start=n<128?128:n, max=191-start;
  if(max>63)max=63;
  for(unsigned count=1;count<=max;count++){
   memset(OAM,0,sizeof(OAM));
   o[191].x=511;o[191].y=255;o[191].shape=3;o[191].size=3;o[191].tileNum=1023;o[191].paletteNum=15;o[191].affineMode=2;o[191].affineParam=0x4000|(count<<8)|n;
   for(unsigned e=0;e<count;e++)o[start+e].affineParam=0x8000|(e*n/count);
   unsigned size=NativeTileBankOamOrder(order);assert(size==n+count);
   unsigned normal=0,extra=0;
   for(unsigned k=0;k<size;k++){
    if(extra<count && (o[start+extra].affineParam&255)<=normal)assert(order[k]==start+extra++);
    else assert(order[k]==normal++);
   }
   assert(normal==n && extra==count);
   o[start].affineParam=0x1234;assert(NativeTileBankOamOrder(order)==192);
   for(unsigned k=0;k<192;k++)assert(order[k]==k);
  }
 }
 return 0;
}
"""
  self.compile_run(RENDER_PRE+function(src,'NativeTileBankOamOrder')+body,['-DWORLD_NATIVE_TILEBANK=1'])

if __name__=='__main__':unittest.main()
