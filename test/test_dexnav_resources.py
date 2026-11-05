"""Compile the production resource broker; stubs model the native allocator, not gameplay."""
from pathlib import Path
import struct, subprocess, tempfile, unittest
from test_dexnav_lifecycle import function

ROOT = Path(__file__).resolve().parents[1]

class DexNavResources(unittest.TestCase):
    def test_one_free_slot_and_foreign_collision_rollback(self):
        source = (ROOT / 'src/platform/dexnav_native.c').read_text()
        state = source[source.index('static u16 sBgPalette'):source.index('static u8 sIconCount')]
        names = ['PaletteInUse', 'UsedColors', 'PackFieldHud', 'AcquireFieldPalette', 'DexNavNative_AcquireFieldResources', 'DexNavNative_ReleaseFieldResources', 'UseEffectPalette']
        bodies = '\n'.join(function(source, n) for n in names)
        def asset(name, path, kind='u8'):
            raw = (ROOT/'build/assets/graphics'/path).read_bytes()
            values = struct.unpack('<' + ('H' if kind == 'u16' else 'B') * (len(raw)//(2 if kind == 'u16' else 1)), raw)
            return 'static const '+kind+' '+name+'[]={'+','.join(map(str,values))+'};\n'
        assets = asset('icon', 'pokemon/icon_palettes/icon_palette_2.pal.gbapal', 'u16')
        assets += asset('iconTiles', 'pokemon/poochyena/icon.png.4bpp')
        assets += asset('gDexNavNative_HeldItemPalette', 'party_menu/hold_icons.png.gbapal', 'u16')
        assets += asset('sHeldItemGfx', 'party_menu/hold_icons.png.4bpp')
        assets += asset('sHudStar', 'dexnav/star.png.4bpp')
        assets += asset('sHudOwned', 'dexnav/owned_icon.png.4bpp')
        assets += asset('nativeEffect', 'field_effects/palettes/general_1.pal.gbapal', 'u16')
        c = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32; typedef u8 bool8;
#define TRUE 1
#define FALSE 0
#define HELD_ITEM_TAG 0xD750
#define OWNED_ICON_TAG 0xD751
#define HIDDEN_SEARCH_TAG 0xD752
#define HIDDEN_MON_ICON_TAG 0xD753
#define LIT_STAR_TILE_TAG 0xD754
#define MAX_SPRITES 64
#define TAG_NONE 0xFFFF
#define SPECIES_NONE 0
#define NUM_SPECIES 412
#define ARRAY_COUNT(a) (sizeof(a)/sizeof((a)[0]))
#define BG_PLTT_ID(n) ((n)*16)
#define OBJ_PLTT_ID(n) (256+(n)*16)
#define PLTT_SIZE_4BPP 32
#define CpuCopy16(a,b,n) memcpy(b,a,n)
static u16 gPlttBufferUnfaded[512],gPlttBufferFaded[512],tags[16];
static struct {bool8 inUse;struct {u8 paletteNum;}oam;} gSprites[MAX_SPRITES];
static bool8 sFailed;
''' + assets + r'''
static struct {u16 paletteTag;}sEffectTemplate;
static const u8 *GetMonIconPtr(u16 species,u32 personality,bool8 normal){(void)species;(void)personality;(void)normal;return iconTiles;}
static const u16 *GetValidMonIconPalettePtr(u16 species){(void)species;return icon;}
static u16 GetSpriteTileStartByTag(u16 tag){(void)tag;return 0xFFFF;}
static u8 IndexOfSpritePaletteTag(u16 tag){for(u8 i=0;i<16;i++)if(tags[i]==tag)return i;return 0xFF;}
static u8 AllocSpritePalette(u16 tag){u8 i=IndexOfSpritePaletteTag(tag);if(i!=0xFF)return i;for(i=12;i<16;i++)if(tags[i]==0xFFFF){tags[i]=tag;return i;}return 0xFF;}
static void FreeSpritePaletteByTag(u16 tag){u8 i=IndexOfSpritePaletteTag(tag);assert(i!=0xFF);tags[i]=0xFFFF;}
static void LoadPalette(const void *p,u16 dst,u16 size){memcpy(gPlttBufferUnfaded+dst,p,size);memcpy(gPlttBufferFaded+dst,p,size);}
static void DexNavNative_FreeIcons(void){}
static void FreeSpriteTilesByTag(u16 tag){(void)tag;}
void DexNavNative_ReleaseFieldResources(void);
''' + state + bodies + r'''
static void field(void){for(int i=0;i<16;i++)tags[i]=0xFFFF;tags[12]=0x1200;tags[13]=0x1201;tags[14]=0x1005;for(int i=0;i<512;i++){gPlttBufferUnfaded[i]=i;gPlttBufferFaded[i]=i+500;}}
int main(void){
 u16 before[512],faded[512];field();LoadPalette(nativeEffect,OBJ_PLTT_ID(14),32);memcpy(before,gPlttBufferUnfaded,sizeof before);memcpy(faded,gPlttBufferFaded,sizeof faded);
 assert(DexNavNative_AcquireFieldResources(1, TRUE, FALSE));
 assert(sSharedHud && sFieldPaletteSlots[0]==15 && sFieldPaletteSlots[1]==0xFF);
 for(unsigned i=0;i<sizeof(sFieldIcon);i++){
  unsigned a=iconTiles[i],b=sFieldIcon[i];
  assert(((a&15)==0)==((b&15)==0));assert(((a>>4)==0)==((b>>4)==0));
  if(a&15)assert(icon[a&15]==gPlttBufferUnfaded[OBJ_PLTT_ID(15)+(b&15)]);
  if(a>>4)assert(icon[a>>4]==gPlttBufferUnfaded[OBJ_PLTT_ID(15)+(b>>4)]);
 }
 u16 hudMask=UsedColors(sHeldItemGfx,32)|UsedColors(sHudStar,sizeof sHudStar)|UsedColors(sHudOwned,sizeof sHudOwned);
 for(unsigned i=1;i<16;i++)if(hudMask&(1<<i))assert(gPlttBufferUnfaded[OBJ_PLTT_ID(15)+i]==gDexNavNative_HeldItemPalette[i]);
 assert(UseEffectPalette(0x1005,nativeEffect));
 assert(sEffectTemplate.paletteTag==0x1005);
 assert(tags[12]==0x1200 && tags[13]==0x1201 && tags[14]==0x1005);
 assert(!memcmp(before,gPlttBufferUnfaded,OBJ_PLTT_ID(15)*2));
 DexNavNative_ReleaseFieldResources();DexNavNative_ReleaseFieldResources();
 assert(tags[15]==0xFFFF);assert(!memcmp(before,gPlttBufferUnfaded,sizeof before));assert(!memcmp(faded,gPlttBufferFaded,sizeof faded));
 assert(DexNavNative_AcquireFieldResources(1, TRUE, FALSE));DexNavNative_ReleaseFieldResources();
 // A native-tag collision with wrong colors must fail, not recolor foreign art.
 assert(DexNavNative_AcquireFieldResources(1, TRUE, FALSE));
 assert(!UseEffectPalette(0x1200,nativeEffect));DexNavNative_ReleaseFieldResources();
 assert(!memcmp(before,gPlttBufferUnfaded,sizeof before));
 // TAG_NONE may resolve to a free bank with matching stale colors, never borrow it.
 tags[13]=0xFFFF;LoadPalette(nativeEffect,OBJ_PLTT_ID(13),32);
 assert(DexNavNative_AcquireFieldResources(1, TRUE, FALSE));
 assert(UseEffectPalette(TAG_NONE,nativeEffect));
 assert(sEffectTemplate.paletteTag==EFFECT_PALETTE_TAG && sFieldPaletteSlots[2]==15);
 DexNavNative_ReleaseFieldResources();assert(tags[15]==0xFFFF && tags[13]==0xFFFF);
 tags[13]=0x1201;LoadPalette(before+OBJ_PLTT_ID(13),OBJ_PLTT_ID(13),32);
 memcpy(gPlttBufferFaded,faded,sizeof faded);
 assert(DexNavNative_AcquireFieldResources(1, TRUE, FALSE));
 assert(!UseEffectPalette(TAG_NONE,nativeEffect));DexNavNative_ReleaseFieldResources();
 // Palette ownership lost on a reset: do not restore over or free its new owner.
 assert(DexNavNative_AcquireFieldResources(1, TRUE, FALSE));
 tags[15]=0x7777;gPlttBufferUnfaded[OBJ_PLTT_ID(15)]=1234;
 DexNavNative_ReleaseFieldResources();assert(tags[15]==0x7777 && gPlttBufferUnfaded[OBJ_PLTT_ID(15)]==1234);
 tags[15]=0xFFFF;LoadPalette(before+OBJ_PLTT_ID(15),OBJ_PLTT_ID(15),32);memcpy(gPlttBufferFaded,faded,sizeof faded);
 tags[15]=ICON_PALETTE_TAG;assert(!DexNavNative_AcquireFieldResources(1, TRUE, FALSE));DexNavNative_ReleaseFieldResources();assert(tags[15]==ICON_PALETTE_TAG);
 tags[15]=0xFFFF;gSprites[0].inUse=TRUE;gSprites[0].oam.paletteNum=15;
 assert(!DexNavNative_AcquireFieldResources(1, TRUE, FALSE));assert(tags[15]==0xFFFF);assert(!memcmp(before,gPlttBufferUnfaded,sizeof before));
 return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='dexnav-resources-') as tmp:
            p = Path(tmp)
            (p/'test.c').write_text(c)
            subprocess.run(['cc','-std=gnu99','-Wall','-Werror',str(p/'test.c'),'-o',str(p/'test')],check=True,capture_output=True,text=True)
            result = subprocess.run([str(p/'test')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)

if __name__ == '__main__':
    unittest.main()
